"""Deterministic, human-gated improvement-loop journal.

The governor records evidence and transitions only. It does not mutate code or model
state, authorize promotion, or move an active runtime pointer.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64
JOURNAL_SCHEMA_VERSION = "1"
JOURNAL_FILENAME = "improvement-governor.sqlite3"
HASH_ALGORITHM = "sha256"
CANONICALIZATION = "json-sort-keys-v1"
AUTHORIZATION_KEY_ENV = "OBUS_IMPROVEMENT_GOVERNOR_AUTH_KEY"
AUTHORIZATION_MAC_ALGORITHM = "hmac-sha256"
_AUTHORIZATION_REQUIRED_STAGES = frozenset({"canary", "promoted"})

LIFECYCLE_STAGES = (
    "observed",
    "proposed",
    "sandboxed",
    "evaluated",
    "awaiting_authorization",
    "rejected",
    "inconclusive",
    "canary",
    "retained",
    "promoted",
    "rolled_back",
    "aborted",
)
ACTIVE_STAGES = frozenset(
    {
        "observed",
        "proposed",
        "sandboxed",
        "evaluated",
        "awaiting_authorization",
        "canary",
    }
)
TERMINAL_STAGES = frozenset(
    {"rejected", "inconclusive", "retained", "promoted", "rolled_back", "aborted"}
)
_ALLOWED_TRANSITIONS = {
    None: frozenset({"observed"}),
    "observed": frozenset({"proposed", "rolled_back", "aborted"}),
    "proposed": frozenset({"sandboxed", "rolled_back", "aborted"}),
    "sandboxed": frozenset({"evaluated", "rolled_back", "aborted"}),
    "evaluated": frozenset(
        {"awaiting_authorization", "rejected", "inconclusive", "rolled_back", "aborted"}
    ),
    "awaiting_authorization": frozenset({"canary", "rolled_back", "aborted"}),
    "canary": frozenset({"retained", "promoted", "rolled_back", "aborted"}),
}

_SCHEMA_DEFINITIONS = (
    (
        "table",
        "journal_meta",
        "journal_meta",
        """
        CREATE TABLE journal_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """,
    ),
    (
        "table",
        "improvement_events",
        "improvement_events",
        """
        CREATE TABLE improvement_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            loop_id TEXT NOT NULL,
            event_index INTEGER NOT NULL CHECK(event_index >= 0),
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL CHECK(length(previous_hash) = 64),
            event_hash TEXT NOT NULL CHECK(length(event_hash) = 64),
            UNIQUE(loop_id, event_index)
        )
        """,
    ),
    (
        "trigger",
        "improvement_events_no_update",
        "improvement_events",
        """
        CREATE TRIGGER improvement_events_no_update
        BEFORE UPDATE ON improvement_events
        BEGIN
            SELECT RAISE(ABORT, 'improvement journal is append-only');
        END
        """,
    ),
    (
        "trigger",
        "improvement_events_no_delete",
        "improvement_events",
        """
        CREATE TRIGGER improvement_events_no_delete
        BEFORE DELETE ON improvement_events
        BEGIN
            SELECT RAISE(ABORT, 'improvement journal is append-only');
        END
        """,
    ),
)


class GovernorError(RuntimeError):
    """Base class for fail-closed governor errors."""

    code = "governor_error"


class JournalIntegrityError(GovernorError):
    """The persisted event history cannot be trusted."""

    code = "journal_integrity_error"


class EvidenceUnavailableError(GovernorError):
    """Required baseline or screening evidence is unavailable or malformed."""

    code = "evidence_unavailable"


class LoopNotFoundError(GovernorError):
    """The requested loop does not exist in the verified journal."""

    code = "loop_not_found"


class InvalidTransitionError(GovernorError):
    """The requested operation is not valid for the current stage."""

    code = "invalid_transition"


def canonical_json(value: Any) -> str:
    """Return the sole JSON representation accepted by the journal."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def document_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_schema_sql(sql: str) -> str:
    return " ".join(sql.strip().rstrip(";").split()).casefold()


def _schema_fingerprint(
    definitions: Sequence[tuple[str, str, str, str]],
) -> str:
    material = {
        f"{object_type}:{name}": {
            "table": table_name,
            "sql": _normalize_schema_sql(sql),
        }
        for object_type, name, table_name, sql in definitions
    }
    return document_digest(material)


_EXPECTED_SCHEMA_FINGERPRINT = _schema_fingerprint(_SCHEMA_DEFINITIONS)


def _authorization_key_bytes(value: str | bytes | None) -> bytes | None:
    configured: str | bytes = (
        os.getenv(AUTHORIZATION_KEY_ENV, "") if value is None else value
    )
    if configured == "" or configured == b"":
        return None
    if isinstance(configured, str):
        key = configured.encode("utf-8")
    elif isinstance(configured, bytes):
        key = configured
    else:
        raise EvidenceUnavailableError("human authorization key must be text or bytes")
    if len(key) < 32:
        raise EvidenceUnavailableError("human authorization key must contain at least 32 bytes")
    return key


def default_journal_path() -> Path:
    """Resolve the journal under Obus's established receipt-data convention."""

    override = os.getenv("OBUS_IMPROVEMENT_GOVERNOR_DB", "").strip()
    if override:
        return Path(override).expanduser()

    from .improvement_baseline import receipt_directory

    return Path(receipt_directory()) / JOURNAL_FILENAME


def _default_status_provider() -> Mapping[str, Any]:
    from .improvement_baseline import baseline_status

    return baseline_status()


def _default_receipt_evaluator(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    from .improvement_evaluation import evaluate_improvement_screening_receipt

    return evaluate_improvement_screening_receipt(receipt)


def _json_snapshot(value: Any, *, label: str) -> Any:
    try:
        return json.loads(canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise EvidenceUnavailableError(f"{label} is not canonical-JSON-compatible") from exc


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _direction_for(path: str) -> str:
    lowered = path.lower()
    if any(token in lowered for token in ("latency", "error", "failure", "cost", "loss")):
        return "minimize"
    return "maximize"


def _select_highest_gap(baseline: Mapping[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    def add_candidate(
        *,
        path: str,
        value: float | None,
        target: float | None,
        gap: float,
        direction: str,
    ) -> None:
        if not _is_number(gap):
            return
        candidates.append(
            {
                "path": path,
                "value": value,
                "target": target,
                "gap": max(0.0, float(gap)),
                "direction": direction,
            }
        )

    def visit(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, Mapping):
            # Historical, incomplete, or unverifiable measurements are diagnostics,
            # not eligible priorities for an autonomous improvement loop.
            ineligible_evidence = (
                node.get("measurement_valid") is False
                or node.get("baseline_replayable") is False
                or node.get("comparable") is False
                or node.get("integrity_verified") is False
                or node.get("attestation_verified") is False
                or node.get("stale") is True
                or node.get("tampered") is True
                or node.get("untrusted") is True
            )
            if ineligible_evidence:
                return

            value = node.get("value")
            target = node.get("target")
            direction = str(node.get("direction") or _direction_for(".".join(path))).lower()
            if _is_number(value) and _is_number(target):
                gap = float(value) - float(target)
                if direction != "minimize":
                    gap = -gap
                add_candidate(
                    path=".".join(path) or "baseline",
                    value=value,
                    target=target,
                    gap=gap,
                    direction=direction,
                )

            explicit_gap = node.get("gap")
            if _is_number(explicit_gap):
                add_candidate(
                    path=".".join((*path, "gap")),
                    value=value if _is_number(value) else None,
                    target=target if _is_number(target) else None,
                    gap=explicit_gap,
                    direction=direction,
                )

            for key in sorted(node, key=str):
                if key in {"value", "target", "direction", "gap"}:
                    continue
                child = node[key]
                child_path = (*path, str(key))
                if _is_number(child):
                    lowered = str(key).lower()
                    if any(token in lowered for token in ("gap", "deficit")):
                        add_candidate(
                            path=".".join(child_path),
                            value=None,
                            target=None,
                            gap=child,
                            direction=_direction_for(".".join(child_path)),
                        )
                    elif any(
                        token in lowered
                        for token in ("score", "accuracy", "success_rate", "pass_rate", "coverage")
                    ):
                        numeric = float(child)
                        inferred_target = 1.0 if 0.0 <= numeric <= 1.0 else 100.0
                        if numeric <= inferred_target:
                            add_candidate(
                                path=".".join(child_path),
                                value=child,
                                target=inferred_target,
                                gap=inferred_target - numeric,
                                direction="maximize",
                            )
                else:
                    visit(child, child_path)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for index, child in enumerate(node):
                visit(child, (*path, str(index)))

    visit(baseline, ())
    if not candidates:
        return {
            "path": "baseline",
            "value": None,
            "target": None,
            "gap": None,
            "direction": "measure",
        }
    candidates.sort(key=lambda item: (-float(item["gap"]), item["path"]))
    return candidates[0]


def _stable_checkpoint(
    baseline: Mapping[str, Any], baseline_digest: str
) -> dict[str, Any]:
    source = "measured_baseline"
    reference: Any = None
    for key in ("stable_checkpoint", "active_checkpoint", "checkpoint", "report_digest"):
        if baseline.get(key) not in (None, "", {}):
            source = key
            reference = baseline[key]
            break
    material: dict[str, Any] = {
        "source": source,
        "baseline_digest": baseline_digest,
    }
    if reference is not None:
        material["reference_digest"] = document_digest(reference)
    return {
        **material,
        "checkpoint_digest": document_digest(material),
        "retained": True,
    }


def _event_hash(
    *,
    loop_id: str,
    event_index: int,
    event_type: str,
    payload: Mapping[str, Any],
    previous_hash: str,
) -> str:
    return document_digest(
        {
            "event_index": event_index,
            "event_type": event_type,
            "loop_id": loop_id,
            "payload": payload,
            "previous_hash": previous_hash,
        }
    )


def _authorization_mac(
    key: bytes,
    *,
    loop_id: str,
    event_index: int,
    event_type: str,
    payload: Mapping[str, Any],
    previous_hash: str,
) -> str:
    payload_snapshot = json.loads(canonical_json(dict(payload)))
    authorization = payload_snapshot.get("human_authorization")
    if not isinstance(authorization, dict):
        raise ValueError("human authorization evidence must be an object")
    unsigned_authorization = dict(authorization)
    unsigned_authorization.pop("mac", None)
    payload_snapshot["human_authorization"] = unsigned_authorization
    material = {
        "algorithm": AUTHORIZATION_MAC_ALGORITHM,
        "event_index": event_index,
        "event_type": event_type,
        "loop_id": loop_id,
        "payload": payload_snapshot,
        "previous_hash": previous_hash,
    }
    return hmac.new(
        key,
        canonical_json(material).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _screening_stage(evaluation: Mapping[str, Any]) -> str:
    status_values = [
        evaluation.get("overall_status"),
        evaluation.get("status"),
        evaluation.get("result"),
        evaluation.get("qualification"),
    ]
    status = " ".join(str(value).lower() for value in status_values if value is not None)
    if any(token in status for token in ("incomplete", "inconclusive", "insufficient", "not_evaluated")):
        return "inconclusive"
    if any(token in status for token in ("fail", "reject", "invalid", "tamper", "mismatch")):
        return "rejected"
    if any(token in status for token in ("pass", "qualified", "success")):
        return "awaiting_authorization"

    if evaluation.get("complete") is False or evaluation.get("evidence_complete") is False:
        return "inconclusive"
    pass_flags = (
        evaluation.get("passed"),
        evaluation.get("all_checks_passed"),
        evaluation.get("submitted_receipt_checks_passed"),
    )
    if any(flag is True for flag in pass_flags):
        return "awaiting_authorization"
    if any(flag is False for flag in pass_flags):
        return "rejected"
    return "inconclusive"


def _warm_runtime_candidate_artifact_digest() -> str:
    """Digest the concrete warm-runtime implementation selected by this candidate."""

    try:
        artifact = Path(__file__).with_name("main.py").read_bytes()
    except OSError as exc:
        raise EvidenceUnavailableError(
            "warm-runtime candidate artifact backend/main.py is unavailable"
        ) from exc
    return hashlib.sha256(artifact).hexdigest()


def _warm_runtime_baseline_artifact() -> dict[str, Any]:
    """Capture immutable Git provenance before admitting a paired improvement loop."""

    try:
        from .improvement_candidate import load_warm_runtime_baseline_artifact

        artifact = load_warm_runtime_baseline_artifact()
    except Exception as exc:
        raise EvidenceUnavailableError(
            "warm-runtime baseline artifact backend/main.py is unavailable"
        ) from exc
    snapshot = _json_snapshot(artifact, label="warm-runtime baseline artifact")
    if not isinstance(snapshot, dict):
        raise EvidenceUnavailableError("warm-runtime baseline artifact is malformed")
    digest = snapshot.get("artifact_digest")
    revision = snapshot.get("source_revision")
    if (
        set(snapshot) != {"artifact_path", "source_revision", "artifact_digest"}
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest.lower())
        or not isinstance(revision, str)
        or len(revision) not in {40, 64}
        or revision != revision.lower()
        or any(character not in "0123456789abcdef" for character in revision)
        or snapshot.get("artifact_path") != "backend/main.py"
    ):
        raise EvidenceUnavailableError("warm-runtime baseline artifact metadata is malformed")
    return snapshot


class ImprovementGovernor:
    """Append-only controller for one bounded, human-gated improvement loop."""

    def __init__(
        self,
        journal_path: str | os.PathLike[str] | None = None,
        *,
        status_provider: Callable[[], Mapping[str, Any]] | None = None,
        receipt_evaluator: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
        authorization_key: str | bytes | None = None,
    ) -> None:
        self.journal_path = Path(journal_path) if journal_path is not None else default_journal_path()
        self._status_provider = status_provider or _default_status_provider
        self._receipt_evaluator = receipt_evaluator or _default_receipt_evaluator
        self._authorization_key = _authorization_key_bytes(authorization_key)
        self._initialize_journal()

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.journal_path), timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _existing_connection(self) -> sqlite3.Connection:
        if not self.journal_path.is_file():
            raise JournalIntegrityError("improvement journal is missing")
        try:
            uri = f"{self.journal_path.resolve().as_uri()}?mode=rw"
            connection = sqlite3.connect(uri, uri=True, timeout=5.0, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            return connection
        except (OSError, sqlite3.DatabaseError) as exc:
            raise JournalIntegrityError("improvement journal cannot be opened") from exc

    def _initialize_journal(self) -> None:
        connection: sqlite3.Connection | None = None
        try:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            connection = self._new_connection()
            connection.execute("BEGIN IMMEDIATE")
            existing_object = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                  AND type IN ('table', 'trigger', 'index', 'view')
                LIMIT 1
                """
            ).fetchone()
            if existing_object is None:
                for _, _, _, statement in _SCHEMA_DEFINITIONS:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO journal_meta(key, value) VALUES ('schema_version', ?)",
                    (JOURNAL_SCHEMA_VERSION,),
                )
            self._validate_and_replay(connection)
            connection.commit()
        except GovernorError:
            if connection is not None and connection.in_transaction:
                connection.rollback()
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            if connection is not None and connection.in_transaction:
                connection.rollback()
            raise JournalIntegrityError("improvement journal initialization failed") from exc
        finally:
            if connection is not None:
                connection.close()

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        if quick_check is None or quick_check[0] != "ok":
            raise JournalIntegrityError("SQLite integrity check failed")
        rows = connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
              AND type IN ('table', 'trigger', 'index', 'view')
            ORDER BY type, name
            """
        ).fetchall()
        if any(row["sql"] is None for row in rows):
            raise JournalIntegrityError("improvement journal schema definition is incomplete")
        actual_definitions = tuple(
            (row["type"], row["name"], row["tbl_name"], row["sql"])
            for row in rows
        )
        expected_objects = {
            (object_type, name, table_name)
            for object_type, name, table_name, _ in _SCHEMA_DEFINITIONS
        }
        actual_objects = {
            (object_type, name, table_name)
            for object_type, name, table_name, _ in actual_definitions
        }
        if actual_objects != expected_objects:
            raise JournalIntegrityError("improvement journal schema objects do not match")
        actual_fingerprint = _schema_fingerprint(actual_definitions)
        if not hmac.compare_digest(actual_fingerprint, _EXPECTED_SCHEMA_FINGERPRINT):
            raise JournalIntegrityError("improvement journal schema fingerprint mismatch")
        row = connection.execute(
            "SELECT value FROM journal_meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None or row["value"] != JOURNAL_SCHEMA_VERSION:
            raise JournalIntegrityError("unsupported improvement journal schema")

    def _verify_human_authorization(
        self,
        *,
        loop_id: str,
        event_index: int,
        event_type: str,
        payload: Mapping[str, Any],
        previous_hash: str,
    ) -> None:
        if event_type not in _AUTHORIZATION_REQUIRED_STAGES:
            return
        authorization = payload.get("human_authorization")
        if not isinstance(authorization, Mapping):
            raise JournalIntegrityError(
                f"{event_type} event lacks human authorization evidence"
            )
        if authorization.get("kind") != "human":
            raise JournalIntegrityError(
                f"{event_type} event has invalid human authorization kind"
            )
        for field in ("authorization_id", "authorized_by", "mac"):
            value = authorization.get(field)
            if not isinstance(value, str) or not value.strip():
                raise JournalIntegrityError(
                    f"{event_type} event has malformed human authorization evidence"
                )
        if self._authorization_key is None:
            raise JournalIntegrityError(
                f"{event_type} event cannot be verified without the operator authorization key"
            )
        try:
            expected_mac = _authorization_mac(
                self._authorization_key,
                loop_id=loop_id,
                event_index=event_index,
                event_type=event_type,
                payload=payload,
                previous_hash=previous_hash,
            )
        except (TypeError, ValueError) as exc:
            raise JournalIntegrityError(
                f"{event_type} event has malformed human authorization evidence"
            ) from exc
        if not hmac.compare_digest(authorization["mac"], expected_mac):
            raise JournalIntegrityError(
                f"{event_type} event has invalid human authorization MAC"
            )

        final_receipt = payload.get("final_receipt")
        final_receipt_digest = payload.get("final_receipt_digest")
        recorded_evaluation = payload.get("final_evaluation")
        final_evaluation_digest = payload.get("final_evaluation_digest")
        if (
            not isinstance(final_receipt, Mapping)
            or not isinstance(final_receipt_digest, str)
            or document_digest(final_receipt) != final_receipt_digest
            or not isinstance(recorded_evaluation, Mapping)
            or not isinstance(final_evaluation_digest, str)
            or document_digest(recorded_evaluation) != final_evaluation_digest
        ):
            raise JournalIntegrityError(
                f"{event_type} event lacks digest-bound final-policy evidence"
            )
        try:
            from .improvement_evaluation import evaluate_improvement_receipt

            verified_evaluation = evaluate_improvement_receipt(final_receipt)
        except Exception as exc:
            raise JournalIntegrityError(
                f"{event_type} final-policy evidence cannot be evaluated"
            ) from exc
        if (
            dict(verified_evaluation) != dict(recorded_evaluation)
            or verified_evaluation.get("overall_status") != "pass"
            or verified_evaluation.get("promotion_authorized") is not True
        ):
            raise JournalIntegrityError(
                f"{event_type} final-policy evidence does not authorize promotion"
            )

    def _validate_and_replay(self, connection: sqlite3.Connection) -> dict[str, Any]:
        self._validate_schema(connection)
        rows = connection.execute(
            """
            SELECT event_id, loop_id, event_index, event_type, payload_json,
                   previous_hash, event_hash
            FROM improvement_events
            ORDER BY event_id
            """
        ).fetchall()
        loops: dict[str, dict[str, Any]] = {}
        active_ids: set[str] = set()
        for row in rows:
            loop_id = row["loop_id"]
            loop = loops.setdefault(
                loop_id,
                {
                    "loop_id": loop_id,
                    "stage": None,
                    "events": [],
                    "head_hash": GENESIS_HASH,
                    "first_event_id": row["event_id"],
                    "last_event_id": row["event_id"],
                },
            )
            expected_index = len(loop["events"])
            if row["event_index"] != expected_index:
                raise JournalIntegrityError(f"non-monotonic event index for loop {loop_id}")
            if row["previous_hash"] != loop["head_hash"]:
                raise JournalIntegrityError(f"broken previous hash for loop {loop_id}")
            try:
                payload = json.loads(row["payload_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise JournalIntegrityError(f"invalid event JSON for loop {loop_id}") from exc
            if not isinstance(payload, dict) or canonical_json(payload) != row["payload_json"]:
                raise JournalIntegrityError(f"non-canonical event JSON for loop {loop_id}")
            replay_payload = payload
            if row["event_type"] == "evaluated":
                verification_record = payload.get("verification_record")
                receipt_digest = payload.get("receipt_digest")
                evaluation = payload.get("evaluation")
                if verification_record is None:
                    legacy_fragments = (
                        payload.get("attestation_digest"),
                        payload.get("evidence_summary"),
                    )
                    legacy_outcome = payload.get("screening_outcome")
                    if (
                        any(fragment is not None for fragment in legacy_fragments)
                        or not isinstance(evaluation, Mapping)
                        or evaluation.get("schema_version") != 1
                        or not isinstance(receipt_digest, str)
                        or evaluation.get("receipt_digest") != receipt_digest
                        or evaluation.get("promotion_authorized") is not False
                        or payload.get("promotion_authorized") is not False
                        or legacy_outcome not in {"inconclusive", "rejected"}
                    ):
                        raise JournalIntegrityError(
                            f"legacy evaluated evidence invariant mismatch for loop {loop_id}"
                        )
                    replay_payload = dict(payload)
                    replay_evaluation = dict(evaluation)
                    replay_evaluation["evidence_verification"] = {
                        "schema_version": 1,
                        "status": "legacy-unverifiable",
                        "reason": "receipt_and_attestation_were_not_persisted",
                        "promotion_ready": False,
                    }
                    replay_payload["evaluation"] = replay_evaluation
                else:
                    if (
                        not isinstance(verification_record, Mapping)
                        or not isinstance(receipt_digest, str)
                        or document_digest(verification_record) != receipt_digest
                    ):
                        raise JournalIntegrityError(
                            f"evaluated receipt digest mismatch for loop {loop_id}"
                        )
                    proposed_event = next(
                        (
                            event for event in loop["events"]
                            if event["stage"] == "proposed"
                        ),
                        None,
                    )
                    lineage = (
                        proposed_event["payload"].get("candidate_lineage")
                        if proposed_event is not None
                        else None
                    )
                    legacy_lineage = (
                        isinstance(lineage, Mapping)
                        and set(lineage) == {
                            "parent_checkpoint_digest", "candidate_digest",
                            "candidate_kind", "artifact_path",
                        }
                    )
                    try:
                        if legacy_lineage:
                            expected_summary, expected_attestation_digest = (
                                self._legacy_rejected_screening_evidence(
                                    loop, verification_record, payload
                                )
                            )
                        else:
                            expected_summary, expected_attestation_digest = (
                                self._candidate_screening_evidence(
                                    loop, verification_record
                                )
                            )
                    except GovernorError as exc:
                        raise JournalIntegrityError(
                            f"evaluated receipt re-verification failed for loop {loop_id}"
                        ) from exc
                    if (
                        payload.get("evidence_summary") != expected_summary
                        or payload.get("attestation_digest")
                        != expected_attestation_digest
                    ):
                        raise JournalIntegrityError(
                            f"evaluated attestation mismatch for loop {loop_id}"
                        )
                    if legacy_lineage:
                        replay_payload = dict(payload)
                        replay_evaluation = dict(evaluation)
                        replay_evaluation["evidence_verification"] = {
                            "schema_version": 1,
                            "status": "legacy-unverifiable",
                            "reason": "immutable_git_baseline_was_not_recorded",
                            "evidence_contract_version": 1,
                            "promotion_ready": False,
                        }
                        replay_payload["evaluation"] = replay_evaluation
            if (
                row["event_type"] in _AUTHORIZATION_REQUIRED_STAGES
                and isinstance(payload.get("final_receipt"), Mapping)
            ):
                final_receipt = payload["final_receipt"]
                final_candidate = final_receipt.get("candidate")
                observed_event = next(
                    (item for item in loop["events"] if item["stage"] == "observed"), None
                )
                proposed_event = next(
                    (item for item in loop["events"] if item["stage"] == "proposed"), None
                )
                lineage = (
                    proposed_event["payload"].get("candidate_lineage")
                    if proposed_event is not None
                    else None
                )
                if (
                    not isinstance(final_candidate, Mapping)
                    or observed_event is None
                    or not isinstance(lineage, Mapping)
                    or final_candidate.get("proposal_id") != loop_id
                    or final_candidate.get("baseline_digest")
                    != observed_event["payload"].get("baseline_digest")
                    or final_candidate.get("candidate_digest") != lineage.get("candidate_digest")
                ):
                    raise JournalIntegrityError(
                        f"{row['event_type']} final receipt is not bound to loop {loop_id}"
                    )
            expected_hash = _event_hash(
                loop_id=loop_id,
                event_index=row["event_index"],
                event_type=row["event_type"],
                payload=payload,
                previous_hash=row["previous_hash"],
            )
            if row["event_hash"] != expected_hash:
                raise JournalIntegrityError(f"event hash mismatch for loop {loop_id}")
            previous_stage = loop["stage"]
            allowed = _ALLOWED_TRANSITIONS.get(previous_stage, frozenset())
            if row["event_type"] not in allowed:
                raise JournalIntegrityError(
                    f"invalid recorded transition {previous_stage!r} -> {row['event_type']!r}"
                )
            self._verify_human_authorization(
                loop_id=loop_id,
                event_index=row["event_index"],
                event_type=row["event_type"],
                payload=payload,
                previous_hash=row["previous_hash"],
            )
            loop["stage"] = row["event_type"]
            loop["head_hash"] = row["event_hash"]
            loop["last_event_id"] = row["event_id"]
            loop["events"].append(
                {
                    "event_id": row["event_id"],
                    "event_index": row["event_index"],
                    "stage": row["event_type"],
                    "payload": replay_payload,
                    "event_hash": row["event_hash"],
                }
            )
            if loop["stage"] in ACTIVE_STAGES:
                active_ids.add(loop_id)
            else:
                active_ids.discard(loop_id)
            if len(active_ids) > 1:
                raise JournalIntegrityError("journal records more than one active improvement loop")
        return {"loops": loops, "event_count": len(rows)}

    def _read_replay(self) -> dict[str, Any]:
        try:
            connection = self._existing_connection()
            try:
                connection.execute("BEGIN")
                replay = self._validate_and_replay(connection)
                connection.commit()
                return replay
            finally:
                connection.close()
        except GovernorError:
            raise
        except sqlite3.DatabaseError as exc:
            raise JournalIntegrityError("improvement journal read failed") from exc

    def _baseline_snapshot(self) -> dict[str, Any]:
        try:
            baseline = self._status_provider()
        except Exception as exc:
            raise EvidenceUnavailableError("measured baseline status is unavailable") from exc
        if not isinstance(baseline, Mapping):
            raise EvidenceUnavailableError("measured baseline status must be an object")
        snapshot = _json_snapshot(dict(baseline), label="measured baseline status")
        if not isinstance(snapshot, dict):
            raise EvidenceUnavailableError("measured baseline status must be an object")
        return snapshot

    @staticmethod
    def _active_loop(replay: Mapping[str, Any]) -> dict[str, Any] | None:
        active = [
            loop
            for loop in replay["loops"].values()
            if loop["stage"] in ACTIVE_STAGES
        ]
        if len(active) > 1:
            raise JournalIntegrityError("journal records more than one active improvement loop")
        return active[0] if active else None

    @staticmethod
    def _latest_loop(replay: Mapping[str, Any]) -> dict[str, Any] | None:
        loops = list(replay["loops"].values())
        return max(loops, key=lambda loop: loop["last_event_id"]) if loops else None

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        *,
        loop_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        previous_stage: str | None,
        previous_hash: str,
        event_index: int,
    ) -> tuple[str, str]:
        if event_type not in _ALLOWED_TRANSITIONS.get(previous_stage, frozenset()):
            raise InvalidTransitionError(
                f"transition {previous_stage!r} -> {event_type!r} is not permitted"
            )
        self._verify_human_authorization(
            loop_id=loop_id,
            event_index=event_index,
            event_type=event_type,
            payload=payload,
            previous_hash=previous_hash,
        )
        payload_json = canonical_json(payload)
        event_hash = _event_hash(
            loop_id=loop_id,
            event_index=event_index,
            event_type=event_type,
            payload=payload,
            previous_hash=previous_hash,
        )
        connection.execute(
            """
            INSERT INTO improvement_events(
                loop_id, event_index, event_type, payload_json, previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (loop_id, event_index, event_type, payload_json, previous_hash, event_hash),
        )
        return event_type, event_hash

    def _status_from_replay(self, replay: Mapping[str, Any]) -> dict[str, Any]:
        active = self._active_loop(replay)
        latest = self._latest_loop(replay)
        active_view = self._loop_view(active) if active else None
        latest_view = self._loop_view(latest) if latest else None
        selected = active_view or latest_view
        state = selected["stage"] if selected else "idle"
        checkpoint = (
            selected["stable_checkpoint"]
            if selected
            else {
                "checkpoint_digest": None,
                "source": "not_recorded",
                "baseline_digest": None,
                "retained": True,
            }
        )
        if state == "idle":
            next_action = "start_loop"
        elif state == "sandboxed":
            next_action = "screen_candidate"
        elif state == "awaiting_authorization":
            next_action = "await_human_authorization"
        elif state in TERMINAL_STAGES:
            next_action = "start_new_loop"
        else:
            next_action = "none"
        heads = {
            loop_id: replay["loops"][loop_id]["head_hash"]
            for loop_id in sorted(replay["loops"])
        }
        return {
            "state": state,
            "active_loop": active_view,
            "latest_loop": latest_view,
            "journal": {
                "verified": True,
                "integrity": "verified",
                "event_count": replay["event_count"],
                "loop_count": len(replay["loops"]),
                "heads": heads,
                "hash_algorithm": HASH_ALGORITHM,
                "canonicalization": CANONICALIZATION,
            },
            "lifecycle": self._lifecycle(latest),
            "next_action": next_action,
            "human_authorization_required": True,
            "autonomous_promotion_permitted": False,
            "promotion_authorized": False,
            "stable_checkpoint": checkpoint,
        }

    @staticmethod
    def _loop_view(loop: Mapping[str, Any]) -> dict[str, Any]:
        by_stage = {event["stage"]: event for event in loop["events"]}
        observed = by_stage["observed"]["payload"]
        proposed = by_stage.get("proposed", {}).get("payload", {})
        evaluated = by_stage.get("evaluated", {}).get("payload")
        screening = None
        if evaluated is not None:
            screening = {
                "receipt_digest": evaluated["receipt_digest"],
                "attestation_digest": evaluated.get("attestation_digest"),
                "evaluation_status": evaluated["evaluation_status"],
                "outcome": evaluated["screening_outcome"],
                "promotion_authorized": False,
                "evidence": evaluated["evaluation"],
                "evidence_summary": evaluated.get("evidence_summary"),
                "receipt_replay_verified": (
                    isinstance(evaluated.get("verification_record"), Mapping)
                    and document_digest(evaluated["verification_record"])
                    == evaluated["receipt_digest"]
                    and not (
                        isinstance(evaluated.get("evaluation"), Mapping)
                        and isinstance(
                            evaluated["evaluation"].get("evidence_verification"),
                            Mapping,
                        )
                        and evaluated["evaluation"]["evidence_verification"].get(
                            "status"
                        ) == "legacy-unverifiable"
                    )
                ),
            }
        return {
            "loop_id": loop["loop_id"],
            "stage": loop["stage"],
            "objective": observed["objective"],
            "baseline_digest": observed["baseline_digest"],
            "candidate_lineage": proposed.get("candidate_lineage"),
            "stable_checkpoint": observed["stable_checkpoint"],
            "screening": screening,
        }

    @staticmethod
    def _lifecycle(loop: Mapping[str, Any] | None) -> list[dict[str, Any]]:
        events = {event["stage"]: event["event_index"] for event in loop["events"]} if loop else {}
        current = loop["stage"] if loop else None
        items: list[dict[str, Any]] = []
        for stage in LIFECYCLE_STAGES:
            if stage == current:
                status = "current"
            elif stage in events:
                status = "completed"
            else:
                status = "pending"
            items.append(
                {"stage": stage, "status": status, "event_index": events.get(stage)}
            )
        return items

    def status(self) -> dict[str, Any]:
        """Validate the complete chain and return the derived governor state."""

        status = self._status_from_replay(self._read_replay())
        if status["active_loop"] is not None:
            return status
        try:
            baseline = self._baseline_snapshot()
        except EvidenceUnavailableError as exc:
            status["next_action"] = "selection_required"
            status["improvement_selection"] = {
                "task_selection_permitted": False,
                "reason": "selection_evidence_unavailable",
                "message": str(exc),
            }
            return status
        comparison = baseline.get("comparison")
        learning_objective = (
            comparison.get("learning_objective")
            if isinstance(comparison, Mapping)
            else None
        )
        candidate_kind = "ollama-warm-residency-v1"
        objective = {
            "path": "Qwen warm-runtime reliability acceptance contract",
            "direction": "verified context",
            "target": 65_536,
            "metric": "model context tokens",
        }
        expected_selection = {
            "candidate_kind": candidate_kind,
            "objective": objective,
        }
        candidate_selection = (
            learning_objective.get("candidate_selection")
            if isinstance(learning_objective, Mapping)
            else None
        )
        if (
            isinstance(learning_objective, Mapping)
            and learning_objective.get("task_selection_permitted") is False
        ):
            status["next_action"] = "no_measured_local_deficit"
            status["improvement_selection"] = {
                "task_selection_permitted": False,
                "reason": learning_objective.get(
                    "status", "no_measured_local_deficit"
                ),
                "message": (
                    "No new loop is offered because the measured baseline "
                    "reports no local deficit."
                ),
            }
        elif candidate_selection != expected_selection:
            status["next_action"] = "selection_required"
            status["improvement_selection"] = {
                "task_selection_permitted": False,
                "reason": "candidate_not_selected",
                "message": (
                    "No new loop is offered because the measured baseline does not "
                    "explicitly select the warm-residency candidate."
                ),
            }
        return status

    def start_loop(self) -> dict[str, Any]:
        """Start one server-derived loop, or return the existing active loop."""

        replay = self._read_replay()
        if self._active_loop(replay) is not None:
            return self._status_from_replay(replay)

        candidate_kind = "ollama-warm-residency-v1"
        objective = {
            "path": "Qwen warm-runtime reliability acceptance contract",
            "direction": "verified context",
            "target": 65_536,
            "metric": "model context tokens",
            "candidate_kind": candidate_kind,
            "evidence_required": "authenticated screening receipt",
            "acceptance": {
                "context_window": 65_536,
                "keep_alive": -1,
                "minimum_verification_checks": 3,
            },
        }
        baseline = self._baseline_snapshot()
        comparison = baseline.get("comparison")
        learning_objective = (
            comparison.get("learning_objective")
            if isinstance(comparison, Mapping)
            else None
        )
        if (
            isinstance(learning_objective, Mapping)
            and learning_objective.get("task_selection_permitted") is False
        ):
            raise EvidenceUnavailableError(
                "measured baseline does not permit automatic task selection"
            )
        expected_selection = {
            "candidate_kind": candidate_kind,
            "objective": {
                key: objective[key]
                for key in ("path", "direction", "target", "metric")
            },
        }
        candidate_selection = (
            learning_objective.get("candidate_selection")
            if isinstance(learning_objective, Mapping)
            else None
        )
        if candidate_selection != expected_selection:
            raise EvidenceUnavailableError(
                "measured baseline does not explicitly select the warm-residency candidate"
            )
        baseline_digest = document_digest(baseline)
        stable_checkpoint = _stable_checkpoint(baseline, baseline_digest)
        baseline_artifact = _warm_runtime_baseline_artifact()
        baseline_artifact_digest = baseline_artifact["artifact_digest"]
        baseline_source_revision = baseline_artifact["source_revision"]
        artifact_digest = _warm_runtime_candidate_artifact_digest()
        candidate_lineage = {
            "evidence_contract_version": 2,
            "parent_checkpoint_digest": stable_checkpoint["checkpoint_digest"],
            "baseline_source_revision": baseline_source_revision,
            "baseline_artifact_digest": baseline_artifact_digest,
            "baseline_artifact": baseline_artifact,
            "candidate_digest": artifact_digest,
            "candidate_kind": "ollama-warm-residency-v1",
            "artifact_path": "backend/main.py",
        }

        connection = self._existing_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._validate_and_replay(connection)
            active = self._active_loop(replay)
            if active is not None:
                connection.commit()
                return self._status_from_replay(replay)
            generation = len(replay["loops"]) + 1
            loop_id = "loop-" + document_digest(
                {
                    "evidence_contract_version": 2,
                    "baseline_source_revision": baseline_source_revision,
                    "baseline_artifact_digest": baseline_artifact_digest,
                    "candidate_digest": candidate_lineage["candidate_digest"],
                    "generation": generation,
                    "parent_checkpoint_digest": candidate_lineage[
                        "parent_checkpoint_digest"
                    ],
                }
            )[:24]
            stage: str | None = None
            head = GENESIS_HASH
            stage, head = self._insert_event(
                connection,
                loop_id=loop_id,
                event_type="observed",
                payload={
                    "baseline": baseline,
                    "baseline_digest": baseline_digest,
                    "evidence_contract_version": 2,
                    "baseline_source_revision": baseline_source_revision,
                    "baseline_artifact_digest": baseline_artifact_digest,
                    "objective": objective,
                    "stable_checkpoint": stable_checkpoint,
                },
                previous_stage=stage,
                previous_hash=head,
                event_index=0,
            )
            stage, head = self._insert_event(
                connection,
                loop_id=loop_id,
                event_type="proposed",
                payload={
                    "candidate_lineage": candidate_lineage,
                    "objective": objective,
                    "runtime_mutation_performed": False,
                },
                previous_stage=stage,
                previous_hash=head,
                event_index=1,
            )
            self._insert_event(
                connection,
                loop_id=loop_id,
                event_type="sandboxed",
                payload={
                    "candidate_lineage": candidate_lineage,
                    "sandbox_kind": "fixed_docker_candidate_pending_evidence",
                    "runtime_mutation_performed": False,
                    "stable_checkpoint": stable_checkpoint,
                },
                previous_stage=stage,
                previous_hash=head,
                event_index=2,
            )
            connection.commit()
        except GovernorError:
            connection.rollback()
            raise
        except sqlite3.DatabaseError as exc:
            connection.rollback()
            raise JournalIntegrityError("could not append improvement-loop start") from exc
        finally:
            connection.close()
        return self.status()

    @staticmethod
    def _legacy_rejected_screening_evidence(
        loop: Mapping[str, Any],
        receipt: Mapping[str, Any],
        evaluated_payload: Mapping[str, Any],
    ) -> tuple[dict[str, Any], str]:
        """Verify one pre-paired receipt only as non-promotable historical evidence."""

        events = {event["stage"]: event["payload"] for event in loop["events"]}
        observed = events.get("observed")
        proposed = events.get("proposed")
        extension = receipt.get("_obus_candidate")
        candidate = receipt.get("candidate")
        evaluation = evaluated_payload.get("evaluation")
        governance = receipt.get("governance")
        if not all(
            isinstance(item, Mapping)
            for item in (
                observed, proposed, extension, candidate, evaluation, governance,
            )
        ):
            raise EvidenceUnavailableError("legacy screening receipt is malformed")
        lineage = proposed.get("candidate_lineage")
        binding = extension.get("binding")
        evidence = extension.get("evidence_summary")
        attestation = extension.get("attestation")
        if not all(
            isinstance(item, Mapping)
            for item in (lineage, binding, evidence, attestation)
        ):
            raise EvidenceUnavailableError("legacy screening evidence is malformed")

        legacy_lineage_fields = {
            "parent_checkpoint_digest", "candidate_digest", "candidate_kind",
            "artifact_path",
        }
        paired_fields = {
            "evidence_contract_version", "baseline_source_revision",
            "baseline_artifact_digest", "baseline_artifact",
            "baseline_probe_runs", "baseline_manifest",
            "baseline_manifest_digest", "candidate_manifest",
            "candidate_manifest_digest", "harness_manifest",
            "harness_manifest_digest",
        }
        if set(lineage) != legacy_lineage_fields or any(
            field in container
            for container in (observed, binding, candidate, evidence, extension)
            for field in paired_fields
        ):
            raise EvidenceUnavailableError(
                "legacy screening fallback cannot accept paired-baseline evidence"
            )
        if (
            receipt.get("schema_version") != 2
            or receipt.get("receipt_kind")
            != "obus-infrastructure-reliability-screening-v1"
            or evaluated_payload.get("promotion_authorized") is not False
            or evaluation.get("promotion_authorized") is not False
            or evaluated_payload.get("screening_outcome")
            not in {"rejected", "inconclusive"}
            or evaluation.get("overall_status") not in {"fail", "incomplete"}
            or evaluated_payload.get("evaluation_status")
            != evaluation.get("overall_status")
            or candidate.get("self_promotion_requested") is not False
            or governance.get("autonomous_promotion_permitted") is not False
            or governance.get("human_authorization") != {"status": "pending"}
        ):
            raise EvidenceUnavailableError(
                "legacy screening receipt is not a recognized non-promotable result"
            )

        expected = {
            "proposal_id": loop["loop_id"],
            "baseline_digest": observed.get("baseline_digest"),
            "candidate_digest": lineage.get("candidate_digest"),
        }
        if dict(binding) != expected or any(
            candidate.get(field) != value for field, value in expected.items()
        ):
            raise EvidenceUnavailableError(
                "legacy screening receipt is not bound to its historical loop"
            )
        if (
            lineage.get("candidate_kind") != "ollama-warm-residency-v1"
            or lineage.get("artifact_path") != "backend/main.py"
            or extension.get("candidate_kind") != lineage.get("candidate_kind")
            or candidate.get("candidate_kind") != lineage.get("candidate_kind")
            or candidate.get("artifact_path") != lineage.get("artifact_path")
            or candidate.get("objective") != observed.get("objective")
            or candidate.get("source_digest") != expected["candidate_digest"]
            or evidence.get("candidate_digest") != expected["candidate_digest"]
            or evidence.get("source_digest") != expected["candidate_digest"]
            or evidence.get("candidate_kind") != lineage.get("candidate_kind")
            or evidence.get("artifact_path") != lineage.get("artifact_path")
            or evidence.get("objective") != observed.get("objective")
        ):
            raise EvidenceUnavailableError(
                "legacy screening evidence does not match its historical candidate"
            )
        for digest in (
            expected["baseline_digest"], expected["candidate_digest"],
            candidate.get("diff_digest"), evidence.get("diff_digest"),
            evidence.get("image_digest"), evidence.get("test_digest"),
            evidence.get("evaluator_digest"), evidence.get("command_digest"),
            evidence.get("output_digest"), evidence.get("comparison_digest"),
            evidence.get("residency_observation_digest"),
        ):
            if not (
                isinstance(digest, str)
                and len(digest) == 64
                and all(character in "0123456789abcdef" for character in digest.lower())
            ):
                raise EvidenceUnavailableError("legacy screening digest is malformed")

        legacy_safe_fields = (
            "invocation_id", "candidate_kind", "objective", "artifact_path",
            "candidate_digest", "source_digest", "diff_digest", "diff_bytes",
            "sandbox_kind", "image_digest", "executed_image_ref", "probe_runs",
            "probe_passes", "model", "requested_context", "observed_context",
            "residency_verified", "test_digest", "evaluator_digest",
            "command_digest", "output_digest", "comparison", "comparison_digest",
            "residency_observation_digest",
        )
        if any(field not in evidence for field in legacy_safe_fields):
            raise EvidenceUnavailableError("legacy screening evidence schema is incomplete")
        summary = {field: evidence[field] for field in legacy_safe_fields}

        attestation_digest = attestation.get("attestation_digest")
        statement = attestation.get("statement")
        if (
            not isinstance(attestation_digest, str)
            or len(attestation_digest) != 64
            or document_digest(
                {key: value for key, value in attestation.items() if key != "attestation_digest"}
            )
            != attestation_digest
            or not isinstance(statement, Mapping)
            or attestation.get("statement_digest") != document_digest(statement)
            or statement.get("subject")
            != [{
                "name": "backend/main.py",
                "digest": {"sha256": expected["candidate_digest"]},
            }]
            or not isinstance(statement.get("predicate"), Mapping)
            or statement["predicate"].get("binding") != binding
            or statement["predicate"].get("evidence") != evidence
        ):
            raise EvidenceUnavailableError(
                "legacy screening attestation does not bind its historical evidence"
            )
        return _json_snapshot(
            summary, label="legacy candidate evidence summary"
        ), attestation_digest

    @staticmethod
    def _candidate_screening_evidence(
        loop: Mapping[str, Any], receipt: Mapping[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Bind trusted candidate evidence to the exact active loop."""

        events = {event["stage"]: event["payload"] for event in loop["events"]}
        observed = events.get("observed")
        proposed = events.get("proposed")
        extension = receipt.get("_obus_candidate")
        candidate = receipt.get("candidate")
        if not all(
            isinstance(item, Mapping)
            for item in (observed, proposed, extension, candidate)
        ):
            raise EvidenceUnavailableError("screening receipt lacks trusted candidate binding")
        lineage = proposed.get("candidate_lineage")
        binding = extension.get("binding")
        if not isinstance(lineage, Mapping) or not isinstance(binding, Mapping):
            raise EvidenceUnavailableError("screening receipt has malformed candidate binding")
        baseline_artifact = lineage.get("baseline_artifact")
        if (
            not isinstance(baseline_artifact, Mapping)
            or baseline_artifact.get("source_revision")
            != lineage.get("baseline_source_revision")
            or observed.get("baseline_source_revision")
            != lineage.get("baseline_source_revision")
            or baseline_artifact.get("artifact_digest")
            != lineage.get("baseline_artifact_digest")
            or observed.get("baseline_artifact_digest")
            != lineage.get("baseline_artifact_digest")
        ):
            raise EvidenceUnavailableError(
                "screening loop lacks its immutable Git baseline provenance"
            )
        expected = {
            "proposal_id": loop["loop_id"],
            "baseline_digest": observed.get("baseline_digest"),
            "baseline_source_revision": lineage.get("baseline_source_revision"),
            "baseline_artifact_digest": lineage.get("baseline_artifact_digest"),
            "candidate_digest": lineage.get("candidate_digest"),
        }
        if dict(binding) != expected or any(
            candidate.get(field) != value for field, value in expected.items()
        ):
            raise EvidenceUnavailableError(
                "screening receipt is not bound to the selected improvement loop"
            )
        expected_contract_version = lineage.get("evidence_contract_version")
        if (
            expected_contract_version not in {None, 2}
            or (
                expected_contract_version == 2
                and candidate.get("evidence_contract_version") != 2
            )
        ):
            raise EvidenceUnavailableError(
                "screening receipt has an unsupported evidence contract"
            )
        expected_kind = lineage.get("candidate_kind")
        expected_artifact = lineage.get("artifact_path")
        if (
            expected_kind != "ollama-warm-residency-v1"
            or extension.get("candidate_kind") != expected_kind
            or candidate.get("candidate_kind") != expected_kind
        ):
            raise EvidenceUnavailableError("screening receipt has an unsupported candidate kind")
        if expected_artifact != "backend/main.py" or candidate.get("artifact_path") != expected_artifact:
            raise EvidenceUnavailableError("screening receipt is not bound to the warm-runtime artifact")
        if candidate.get("objective") != observed.get("objective"):
            raise EvidenceUnavailableError("screening receipt objective does not match the selected loop")
        evidence = extension.get("evidence_summary")
        attestation = extension.get("attestation")
        if not isinstance(evidence, Mapping) or not isinstance(attestation, Mapping):
            raise EvidenceUnavailableError("screening receipt lacks trusted evidence")
        if (
            (
                expected_contract_version == 2
                and evidence.get("evidence_contract_version") != 2
            )
            or evidence.get("objective") != observed.get("objective")
            or evidence.get("artifact_path") != expected_artifact
            or evidence.get("baseline_source_revision")
            != expected["baseline_source_revision"]
            or evidence.get("baseline_artifact_digest")
            != expected["baseline_artifact_digest"]
            or evidence.get("candidate_digest") != expected["candidate_digest"]
            or evidence.get("source_digest") != expected["candidate_digest"]
            or candidate.get("source_digest") != expected["candidate_digest"]
        ):
            raise EvidenceUnavailableError(
                "screening receipt evidence is not bound to the active loop artifact"
            )
        attestation_digest = attestation.get("attestation_digest")
        if not (
            isinstance(attestation_digest, str)
            and len(attestation_digest) == 64
            and all(character in "0123456789abcdef" for character in attestation_digest.lower())
        ):
            raise EvidenceUnavailableError("screening receipt has malformed attestation evidence")
        safe_fields = (
            "invocation_id", "evidence_contract_version", "candidate_kind",
            "objective", "artifact_path", "baseline_source_revision",
            "baseline_artifact_digest",
            "candidate_digest", "source_digest",
            "diff_digest", "diff_bytes", "sandbox_kind", "image_digest",
            "executed_image_ref", "baseline_probe_runs", "baseline_probe_passes",
            "probe_runs", "probe_passes", "model", "requested_context",
            "observed_context", "residency_verified", "test_digest",
            "evaluator_digest", "baseline_command_digest", "command_digest",
            "baseline_output_digest", "output_digest", "harness_manifest_digest",
            "baseline_manifest_digest", "candidate_manifest_digest", "comparison",
            "comparison_digest", "residency_observation_digest",
        )
        summary = {field: evidence.get(field) for field in safe_fields}
        return _json_snapshot(summary, label="candidate evidence summary"), attestation_digest

    def screen(self, loop_id: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
        """Record receipt screening without granting authorization or promotion."""

        replay = self._read_replay()
        loop = replay["loops"].get(loop_id)
        if loop is None:
            raise LoopNotFoundError(f"unknown improvement loop: {loop_id}")
        if loop["stage"] in {"awaiting_authorization", "rejected", "inconclusive"}:
            return self._status_from_replay(replay)
        if loop["stage"] != "sandboxed":
            raise InvalidTransitionError(
                f"loop {loop_id} cannot be screened from stage {loop['stage']}"
            )
        if not isinstance(receipt, Mapping):
            raise EvidenceUnavailableError("screening receipt must be an object")
        receipt_snapshot = _json_snapshot(dict(receipt), label="screening receipt")
        receipt_digest = document_digest(receipt_snapshot)
        evidence_summary, attestation_digest = self._candidate_screening_evidence(
            loop, receipt_snapshot
        )
        try:
            evaluation = self._receipt_evaluator(receipt_snapshot)
        except Exception as exc:
            raise EvidenceUnavailableError("screening evaluator could not evaluate receipt") from exc
        if not isinstance(evaluation, Mapping):
            raise EvidenceUnavailableError("screening evaluator returned malformed evidence")
        evaluation_snapshot = _json_snapshot(dict(evaluation), label="screening evaluation")
        screening_stage = _screening_stage(evaluation_snapshot)
        evaluation_status = str(
            evaluation_snapshot.get("overall_status")
            or evaluation_snapshot.get("status")
            or evaluation_snapshot.get("result")
            or "unknown"
        )

        connection = self._existing_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._validate_and_replay(connection)
            loop = replay["loops"].get(loop_id)
            if loop is None:
                raise LoopNotFoundError(f"unknown improvement loop: {loop_id}")
            if loop["stage"] in {"awaiting_authorization", "rejected", "inconclusive"}:
                connection.commit()
                return self._status_from_replay(replay)
            if loop["stage"] != "sandboxed":
                raise InvalidTransitionError(
                    f"loop {loop_id} cannot be screened from stage {loop['stage']}"
                )
            event_index = len(loop["events"])
            stage, head = self._insert_event(
                connection,
                loop_id=loop_id,
                event_type="evaluated",
                payload={
                    "evaluation": evaluation_snapshot,
                    "evaluation_status": evaluation_status,
                    "promotion_authorized": False,
                    "receipt_digest": receipt_digest,
                    "attestation_digest": attestation_digest,
                    "evidence_summary": evidence_summary,
                    "verification_record": receipt_snapshot,
                    "screening_outcome": screening_stage,
                },
                previous_stage=loop["stage"],
                previous_hash=loop["head_hash"],
                event_index=event_index,
            )
            reasons = {
                "awaiting_authorization": "screening_passed_human_authorization_required",
                "rejected": "screening_failed",
                "inconclusive": "screening_evidence_incomplete",
            }
            self._insert_event(
                connection,
                loop_id=loop_id,
                event_type=screening_stage,
                payload={
                    "promotion_authorized": False,
                    "reason": reasons[screening_stage],
                    "receipt_digest": receipt_digest,
                },
                previous_stage=stage,
                previous_hash=head,
                event_index=event_index + 1,
            )
            connection.commit()
        except GovernorError:
            connection.rollback()
            raise
        except sqlite3.DatabaseError as exc:
            connection.rollback()
            raise JournalIntegrityError("could not append screening result") from exc
        finally:
            connection.close()
        return self.status()

    def rollback(self, loop_id: str, reason: str) -> dict[str, Any]:
        """Defensively terminate a loop while retaining its stable checkpoint."""

        reason = reason.strip()
        if not reason:
            raise EvidenceUnavailableError("rollback reason is required")
        connection = self._existing_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._validate_and_replay(connection)
            loop = replay["loops"].get(loop_id)
            if loop is None:
                raise LoopNotFoundError(f"unknown improvement loop: {loop_id}")
            if loop["stage"] == "rolled_back":
                connection.commit()
                return self._status_from_replay(replay)
            if loop["stage"] not in ACTIVE_STAGES:
                raise InvalidTransitionError(
                    f"loop {loop_id} cannot roll back from stage {loop['stage']}"
                )
            stable_checkpoint = self._loop_view(loop)["stable_checkpoint"]
            self._insert_event(
                connection,
                loop_id=loop_id,
                event_type="rolled_back",
                payload={
                    "reason": reason,
                    "runtime_mutation_performed": False,
                    "stable_checkpoint": stable_checkpoint,
                    "stable_checkpoint_retained": True,
                },
                previous_stage=loop["stage"],
                previous_hash=loop["head_hash"],
                event_index=len(loop["events"]),
            )
            connection.commit()
        except GovernorError:
            connection.rollback()
            raise
        except sqlite3.DatabaseError as exc:
            connection.rollback()
            raise JournalIntegrityError("could not append rollback") from exc
        finally:
            connection.close()
        return self.status()

    @staticmethod
    def fail_closed_status(message: str) -> dict[str, Any]:
        """Return the mandatory response envelope without trusting journal contents."""

        return {
            "state": "integrity_error",
            "active_loop": None,
            "latest_loop": None,
            "journal": {
                "verified": False,
                "integrity": "failed",
                "event_count": None,
                "loop_count": None,
                "heads": {},
                "hash_algorithm": HASH_ALGORITHM,
                "canonicalization": CANONICALIZATION,
                "error": message,
            },
            "lifecycle": [
                {"stage": stage, "status": "pending", "event_index": None}
                for stage in LIFECYCLE_STAGES
            ],
            "next_action": "investigate_journal_integrity",
            "human_authorization_required": True,
            "autonomous_promotion_permitted": False,
            "promotion_authorized": False,
            "stable_checkpoint": {
                "checkpoint_digest": None,
                "source": "unverified",
                "baseline_digest": None,
                "retained": True,
            },
        }
