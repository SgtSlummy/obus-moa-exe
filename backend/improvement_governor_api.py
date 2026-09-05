"""FastAPI surface for the human-gated Improvement Governor."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import sqlite3
from typing import Annotated, Any, Mapping
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Header
from fastapi.responses import JSONResponse

from .improvement_governor import (
    EvidenceUnavailableError,
    GovernorError,
    ImprovementGovernor,
    InvalidTransitionError,
    JournalIntegrityError,
    LoopNotFoundError,
)

router = APIRouter(prefix="/api/improvement/governor", tags=["improvement-governor"])

_IDEMPOTENCY_KEY_MAX_LENGTH = 256
_IDEMPOTENCY_REQUEST_FINGERPRINT = sha256(
    b"improvement-governor:start-loop:v1"
).hexdigest()
_IDEMPOTENCY_COLUMNS = (
    "key_digest",
    "request_fingerprint",
    "state",
    "before_loop_count",
    "before_active_loop_id",
    "loop_id",
)
_CANDIDATE_RUN_COLUMNS = (
    "attempt_key_digest",
    "loop_id",
    "candidate_kind",
    "state",
    "error_code",
    "error_message",
)


class IdempotencyConflictError(GovernorError):
    code = "idempotency_conflict"


class InvalidIdempotencyKeyError(GovernorError):
    code = "invalid_idempotency_key"


@dataclass(frozen=True, slots=True)
class GovernorInitializationFailure:
    message: str


@lru_cache(maxsize=1)
def _cached_improvement_governor() -> ImprovementGovernor:
    return ImprovementGovernor()


def get_improvement_governor() -> ImprovementGovernor | GovernorInitializationFailure:
    """Resolve the cached governor without letting dependency failures bypass the API envelope."""

    try:
        return _cached_improvement_governor()
    except JournalIntegrityError as error:
        return GovernorInitializationFailure(str(error))
    except OSError:
        return GovernorInitializationFailure("improvement journal path is unavailable")


def _dependency_failure_response(
    governor: ImprovementGovernor | GovernorInitializationFailure,
) -> JSONResponse | None:
    if not isinstance(governor, GovernorInitializationFailure):
        return None
    return JSONResponse(
        status_code=409,
        content={
            **ImprovementGovernor.fail_closed_status(governor.message),
            "retryable": False,
        },
    )


def _error_response(governor: ImprovementGovernor, error: GovernorError) -> JSONResponse:
    if isinstance(error, JournalIntegrityError):
        body = governor.fail_closed_status(str(error))
        status_code = 409
    else:
        try:
            body = governor.status()
        except JournalIntegrityError as integrity_error:
            body = governor.fail_closed_status(str(integrity_error))
            status_code = 409
        else:
            body["error"] = {"code": error.code, "message": str(error)}
            if isinstance(error, LoopNotFoundError):
                status_code = 404
            elif isinstance(error, (EvidenceUnavailableError, InvalidIdempotencyKeyError)):
                status_code = 422
            elif isinstance(error, (InvalidTransitionError, IdempotencyConflictError)):
                status_code = 409
            else:
                status_code = 500
    if 400 <= status_code < 500:
        body["retryable"] = False
        body.pop("retry_key", None)
    return JSONResponse(status_code=status_code, content=body)


def _normalize_idempotency_key(value: Any, *, source: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidIdempotencyKeyError(f"{source} idempotency key must be a string")
    key = value.strip()
    if not key:
        raise InvalidIdempotencyKeyError(f"{source} idempotency key must not be empty")
    if len(key) > _IDEMPOTENCY_KEY_MAX_LENGTH:
        raise InvalidIdempotencyKeyError(
            f"{source} idempotency key exceeds {_IDEMPOTENCY_KEY_MAX_LENGTH} characters"
        )
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in key):
        raise InvalidIdempotencyKeyError(
            f"{source} idempotency key contains control characters"
        )
    return key


def _resolve_start_idempotency_key(
    payload: Mapping[str, Any] | None,
    header_value: str | None,
) -> str | None:
    body_value: Any = None
    if payload is not None:
        unexpected = sorted(set(payload) - {"idempotency_key"})
        if unexpected:
            raise InvalidIdempotencyKeyError(
                "loop start body accepts only the idempotency_key field"
            )
        body_value = payload.get("idempotency_key")
    header_key = _normalize_idempotency_key(header_value, source="header")
    body_key = _normalize_idempotency_key(body_value, source="body")
    if header_key is not None and body_key is not None and header_key != body_key:
        raise IdempotencyConflictError(
            "Idempotency-Key header conflicts with body idempotency_key"
        )
    return header_key or body_key


def _status_loop_count(status: Mapping[str, Any]) -> int:
    journal = status.get("journal")
    if not isinstance(journal, Mapping) or journal.get("verified") is not True:
        raise JournalIntegrityError("cannot verify idempotency against governor journal")
    count = journal.get("loop_count")
    if type(count) is not int or count < 0:
        raise JournalIntegrityError("governor journal returned an invalid loop count")
    return count


def _status_loop_id(status: Mapping[str, Any]) -> str | None:
    for field in ("active_loop", "latest_loop"):
        loop = status.get(field)
        if isinstance(loop, Mapping):
            loop_id = loop.get("loop_id")
            if isinstance(loop_id, str) and loop_id:
                return loop_id
    return None


def _upgrade_candidate_run_state_schema(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'candidate_run_requests'"
    ).fetchone()
    if row is None or "terminal_failed" in str(row[0]):
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute("DROP INDEX IF EXISTS one_active_candidate_run_per_loop")
        connection.execute(
            "ALTER TABLE candidate_run_requests RENAME TO candidate_run_requests_legacy"
        )
        connection.execute(
            """
            CREATE TABLE candidate_run_requests (
                attempt_key_digest TEXT PRIMARY KEY,
                loop_id TEXT NOT NULL,
                candidate_kind TEXT NOT NULL,
                state TEXT NOT NULL CHECK(
                    state IN ('pending', 'completed', 'retryable_failed', 'terminal_failed')
                ),
                error_code TEXT,
                error_message TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO candidate_run_requests(
                attempt_key_digest, loop_id, candidate_kind, state, error_code, error_message
            )
            SELECT attempt_key_digest, loop_id, candidate_kind, state, error_code, error_message
            FROM candidate_run_requests_legacy
            """
        )
        connection.execute("DROP TABLE candidate_run_requests_legacy")
        connection.commit()
    except sqlite3.DatabaseError:
        connection.rollback()
        raise


def _idempotency_connection(governor: ImprovementGovernor) -> sqlite3.Connection:
    path = governor.journal_path.with_name(
        governor.journal_path.name + ".idempotency.sqlite3"
    )
    connection: sqlite3.Connection | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        if quick_check is None or quick_check[0] != "ok":
            raise JournalIntegrityError("improvement idempotency journal failed integrity check")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS loop_start_requests (
                key_digest TEXT PRIMARY KEY,
                request_fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('pending', 'completed')),
                before_loop_count INTEGER NOT NULL CHECK(before_loop_count >= 0),
                before_active_loop_id TEXT,
                loop_id TEXT
            )
            """
        )
        columns = tuple(
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(loop_start_requests)"
            ).fetchall()
        )
        if columns != _IDEMPOTENCY_COLUMNS:
            raise JournalIntegrityError("improvement idempotency journal schema mismatch")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_run_requests (
                attempt_key_digest TEXT PRIMARY KEY,
                loop_id TEXT NOT NULL,
                candidate_kind TEXT NOT NULL,
                state TEXT NOT NULL CHECK(
                    state IN ('pending', 'completed', 'retryable_failed', 'terminal_failed')
                ),
                error_code TEXT,
                error_message TEXT
            )
            """
        )
        _upgrade_candidate_run_state_schema(connection)
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_candidate_run_per_loop
            ON candidate_run_requests(loop_id)
            WHERE state IN ('pending', 'completed', 'terminal_failed')
            """
        )
        candidate_columns = tuple(
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(candidate_run_requests)"
            ).fetchall()
        )
        if candidate_columns != _CANDIDATE_RUN_COLUMNS:
            raise JournalIntegrityError("candidate-run idempotency journal schema mismatch")
        return connection
    except GovernorError:
        if connection is not None:
            connection.close()
        raise
    except (OSError, sqlite3.DatabaseError) as error:
        if connection is not None:
            connection.close()
        raise JournalIntegrityError("improvement idempotency journal unavailable") from error


def _reserve_idempotency_key(
    governor: ImprovementGovernor,
    key: str,
    before_status: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    key_digest = sha256(key.encode("utf-8")).hexdigest()
    before_loop_count = _status_loop_count(before_status)
    active_loop = before_status.get("active_loop")
    before_active_loop_id = (
        active_loop.get("loop_id") if isinstance(active_loop, Mapping) else None
    )
    connection = _idempotency_connection(governor)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM loop_start_requests WHERE key_digest = ?",
            (key_digest,),
        ).fetchone()
        if row is not None:
            record = dict(row)
            if record["request_fingerprint"] != _IDEMPOTENCY_REQUEST_FINGERPRINT:
                raise IdempotencyConflictError(
                    "idempotency key was already used for a different request"
                )
            connection.commit()
            return record, False
        record = {
            "key_digest": key_digest,
            "request_fingerprint": _IDEMPOTENCY_REQUEST_FINGERPRINT,
            "state": "pending",
            "before_loop_count": before_loop_count,
            "before_active_loop_id": before_active_loop_id,
            "loop_id": None,
        }
        connection.execute(
            """
            INSERT INTO loop_start_requests(
                key_digest,
                request_fingerprint,
                state,
                before_loop_count,
                before_active_loop_id,
                loop_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            tuple(record[column] for column in _IDEMPOTENCY_COLUMNS),
        )
        connection.commit()
        return record, True
    except GovernorError:
        connection.rollback()
        raise
    except sqlite3.DatabaseError as error:
        connection.rollback()
        raise JournalIntegrityError("could not reserve improvement idempotency key") from error
    finally:
        connection.close()


def _complete_idempotency_key(
    governor: ImprovementGovernor,
    record: Mapping[str, Any],
    loop_id: str,
) -> None:
    connection = _idempotency_connection(governor)
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT * FROM loop_start_requests WHERE key_digest = ?",
            (record["key_digest"],),
        ).fetchone()
        if current is None:
            raise JournalIntegrityError("reserved idempotency key disappeared")
        if current["request_fingerprint"] != _IDEMPOTENCY_REQUEST_FINGERPRINT:
            raise IdempotencyConflictError(
                "idempotency key was already used for a different request"
            )
        if current["state"] == "completed" and current["loop_id"] != loop_id:
            raise JournalIntegrityError("idempotency key resolved to multiple loops")
        connection.execute(
            """
            UPDATE loop_start_requests
            SET state = 'completed', loop_id = ?
            WHERE key_digest = ?
            """,
            (loop_id, record["key_digest"]),
        )
        connection.commit()
    except GovernorError:
        connection.rollback()
        raise
    except sqlite3.DatabaseError as error:
        connection.rollback()
        raise JournalIntegrityError("could not complete improvement idempotency key") from error
    finally:
        connection.close()


def _start_loop_idempotently(
    governor: ImprovementGovernor,
    key: str,
) -> tuple[dict[str, Any], bool]:
    before_status = governor.status()
    record, created = _reserve_idempotency_key(governor, key, before_status)
    if not created:
        current_status = governor.status()
        if record["state"] == "completed":
            return current_status, True
        current_loop_count = _status_loop_count(current_status)
        before_loop_count = int(record["before_loop_count"])
        if current_loop_count < before_loop_count:
            raise JournalIntegrityError("governor loop count moved backwards")
        if current_loop_count > before_loop_count or record["before_active_loop_id"]:
            loop_id = _status_loop_id(current_status) or record["before_active_loop_id"]
            if not isinstance(loop_id, str) or not loop_id:
                raise JournalIntegrityError("could not recover idempotent loop start")
            _complete_idempotency_key(governor, record, loop_id)
            return current_status, True

    result = governor.start_loop()
    loop_id = _status_loop_id(result)
    if loop_id is None:
        raise JournalIntegrityError("loop start returned no identifiable loop")
    _complete_idempotency_key(governor, record, loop_id)
    return result, not created


@router.get("")
def governor_status(
    governor: Annotated[
        ImprovementGovernor | GovernorInitializationFailure,
        Depends(get_improvement_governor),
    ],
) -> Any:
    dependency_error = _dependency_failure_response(governor)
    if dependency_error is not None:
        return dependency_error
    try:
        return governor.status()
    except GovernorError as error:
        return _error_response(governor, error)


@router.post("/loops")
def start_improvement_loop(
    governor: Annotated[
        ImprovementGovernor | GovernorInitializationFailure,
        Depends(get_improvement_governor),
    ],
    payload: Annotated[dict[str, Any] | None, Body()] = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
) -> Any:
    dependency_error = _dependency_failure_response(governor)
    if dependency_error is not None:
        return dependency_error
    try:
        key = _resolve_start_idempotency_key(payload, idempotency_key)
        if key is None:
            return governor.start_loop()
        result, replayed = _start_loop_idempotently(governor, key)
        return JSONResponse(
            status_code=200,
            content=result,
            headers={
                "Idempotency-Key": key,
                "Idempotency-Replayed": "true" if replayed else "false",
            },
        )
    except GovernorError as error:
        return _error_response(governor, error)


def _candidate_loop(
    status: Mapping[str, Any], loop_id: str
) -> Mapping[str, Any] | None:
    for field in ("active_loop", "latest_loop"):
        loop = status.get(field)
        if isinstance(loop, Mapping) and loop.get("loop_id") == loop_id:
            return loop
    return None


def _candidate_attempt_key(loop_id: str, retry_key: Any) -> str:
    canonical = f"candidate-run:{loop_id}"
    if retry_key is None:
        return canonical
    normalized = _normalize_idempotency_key(retry_key, source="body retry_key")
    if normalized is None:
        return canonical
    return f"{canonical}:retry:{normalized}"


def _completed_candidate_run(
    governor: ImprovementGovernor,
    *,
    loop_id: str,
    candidate_kind: str,
    retry_key: str | None = None,
) -> dict[str, Any] | None:
    attempt_key_digest = sha256(
        _candidate_attempt_key(loop_id, retry_key).encode("utf-8")
    ).hexdigest()
    connection = _idempotency_connection(governor)
    try:
        row = connection.execute(
            """
            SELECT * FROM candidate_run_requests
            WHERE loop_id = ? AND candidate_kind = ?
              AND (
                state IN ('pending', 'completed', 'terminal_failed')
                OR (state = 'retryable_failed' AND attempt_key_digest = ?)
              )
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (loop_id, candidate_kind, attempt_key_digest),
        ).fetchone()
        return dict(row) if row is not None else None
    except sqlite3.DatabaseError as error:
        raise JournalIntegrityError(
            "could not read completed candidate execution"
        ) from error
    finally:
        connection.close()


def _reserve_candidate_run(
    governor: ImprovementGovernor,
    *,
    loop_id: str,
    candidate_kind: str,
    retry_key: Any,
) -> tuple[dict[str, Any], str]:
    attempt_key_digest = sha256(
        _candidate_attempt_key(loop_id, retry_key).encode("utf-8")
    ).hexdigest()
    connection = _idempotency_connection(governor)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for state in ("completed", "pending"):
            current = connection.execute(
                "SELECT * FROM candidate_run_requests WHERE loop_id = ? AND state = ?",
                (loop_id, state),
            ).fetchone()
            if current is not None:
                connection.commit()
                return dict(current), state
        existing = connection.execute(
            "SELECT * FROM candidate_run_requests WHERE attempt_key_digest = ?",
            (attempt_key_digest,),
        ).fetchone()
        if existing is not None:
            record = dict(existing)
            connection.commit()
            return record, str(record["state"])
        record = {
            "attempt_key_digest": attempt_key_digest,
            "loop_id": loop_id,
            "candidate_kind": candidate_kind,
            "state": "pending",
            "error_code": None,
            "error_message": None,
        }
        connection.execute(
            """
            INSERT INTO candidate_run_requests(
                attempt_key_digest, loop_id, candidate_kind, state, error_code, error_message
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            tuple(record[column] for column in _CANDIDATE_RUN_COLUMNS),
        )
        connection.commit()
        return record, "created"
    except GovernorError:
        connection.rollback()
        raise
    except sqlite3.DatabaseError as error:
        connection.rollback()
        raise JournalIntegrityError("could not reserve candidate execution") from error
    finally:
        connection.close()


def _set_candidate_run_state(
    governor: ImprovementGovernor,
    record: Mapping[str, Any],
    *,
    state: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    connection = _idempotency_connection(governor)
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT state FROM candidate_run_requests WHERE attempt_key_digest = ?",
            (record["attempt_key_digest"],),
        ).fetchone()
        if current is None:
            raise JournalIntegrityError("reserved candidate execution disappeared")
        if current["state"] == "completed" and state != "completed":
            raise JournalIntegrityError("completed candidate execution cannot regress")
        connection.execute(
            """
            UPDATE candidate_run_requests
            SET state = ?, error_code = ?, error_message = ?
            WHERE attempt_key_digest = ?
            """,
            (state, error_code, error_message, record["attempt_key_digest"]),
        )
        connection.commit()
    except GovernorError:
        connection.rollback()
        raise
    except sqlite3.DatabaseError as error:
        connection.rollback()
        raise JournalIntegrityError("could not update candidate execution") from error
    finally:
        connection.close()


def _candidate_execution_response(
    governor: ImprovementGovernor,
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
) -> JSONResponse:
    body = {
        **governor.status(),
        "error": {"code": code, "message": message},
        "retryable": retryable,
        "retry_key_required": retryable,
        **({"retry_key": uuid4().hex} if retryable else {}),
    }
    headers = {"Retry-After": "2"} if status_code in (409, 503) else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def _candidate_error_response(
    governor: ImprovementGovernor,
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            **governor.status(),
            "error": {"code": code, "message": message},
            "retryable": False,
        },
    )


def _public_candidate_run(result: dict[str, Any], candidate_kind: str) -> dict[str, Any]:
    persisted_loop: Mapping[str, Any] | None = None
    for field in ("active_loop", "latest_loop"):
        value = result.get(field)
        if isinstance(value, Mapping) and isinstance(value.get("screening"), Mapping):
            persisted_loop = value
            break
    if persisted_loop is None:
        return dict(result)
    screening = persisted_loop["screening"]
    return {
        **result,
        "candidate_run": {
            "candidate_kind": candidate_kind,
            "receipt_digest": screening.get("receipt_digest"),
            "attestation_digest": screening.get("attestation_digest"),
            "evidence_summary": dict(screening.get("evidence_summary", {})),
        },
    }


@router.post("/loops/{loop_id}/screen")
def screen_improvement_loop(
    loop_id: str,
    governor: Annotated[
        ImprovementGovernor | GovernorInitializationFailure,
        Depends(get_improvement_governor),
    ],
    payload: Annotated[dict[str, Any] | None, Body()] = None,
) -> Any:
    dependency_error = _dependency_failure_response(governor)
    if dependency_error is not None:
        return dependency_error
    from .improvement_candidate import CANDIDATE_KIND, CandidateRunError, run_improvement_candidate

    payload = payload or {}
    unexpected = sorted(set(payload) - {"candidate_kind", "retry_key"})
    if unexpected:
        return _candidate_error_response(
            governor,
            status_code=422,
            code="trusted_candidate_required",
            message=(
                "Client-supplied receipts and commands are not accepted. Run the fixed "
                "server-side evidence candidate instead."
            ),
        )

    candidate_kind = str(payload.get("candidate_kind", CANDIDATE_KIND)).strip()
    if candidate_kind != CANDIDATE_KIND:
        return _candidate_error_response(
            governor,
            status_code=422,
            code="unsupported_candidate",
            message="Only the fixed Ollama warm-residency candidate is permitted.",
        )

    record: dict[str, Any] | None = None
    disposition: str | None = None
    try:
        retry_key = _normalize_idempotency_key(
            payload.get("retry_key"), source="body retry_key"
        )
        status = governor.status()
        loop = _candidate_loop(status, loop_id)
        if loop is None:
            return _candidate_error_response(
                governor,
                status_code=409,
                code="active_loop_mismatch",
                message="The requested improvement loop does not exist.",
            )
        stage = loop.get("stage")
        completed_record = _completed_candidate_run(
            governor,
            loop_id=loop_id,
            candidate_kind=candidate_kind,
            retry_key=retry_key,
        )
        if completed_record is not None:
            completed_state = completed_record.get("state")
            if completed_state == "retryable_failed":
                return _candidate_execution_response(
                    governor,
                    status_code=503,
                    code=str(
                        completed_record.get("error_code")
                        or "candidate_infrastructure_unavailable"
                    ),
                    message=str(
                        completed_record.get("error_message")
                        or "Candidate infrastructure is unavailable."
                    ),
                    retryable=True,
                )
            if completed_state == "pending":
                return _candidate_execution_response(
                    governor,
                    status_code=409,
                    code="candidate_run_in_progress",
                    message="Evidence probes are already running for this loop.",
                    retryable=False,
                )
            if completed_state == "terminal_failed":
                return _candidate_execution_response(
                    governor,
                    status_code=409,
                    code=str(completed_record.get("error_code") or "candidate_contract_failed"),
                    message=str(
                        completed_record.get("error_message")
                        or "Candidate execution failed a non-retryable governor contract."
                    ),
                    retryable=False,
                )
            persisted = _public_candidate_run(status, candidate_kind)
            if "candidate_run" not in persisted:
                return _candidate_error_response(
                    governor,
                    status_code=409,
                    code="candidate_evidence_unavailable",
                    message="Completed candidate evidence is not available from governor state.",
                )
            return JSONResponse(
                status_code=200,
                content=persisted,
                headers={"Idempotency-Replayed": "true"},
            )
        if stage in {"awaiting_authorization", "inconclusive", "rejected"} and isinstance(
            loop.get("screening"), Mapping
        ):
            return JSONResponse(
                status_code=200,
                content=_public_candidate_run(status, candidate_kind),
                headers={"Idempotency-Replayed": "true"},
            )
        active_loop = status.get("active_loop")
        if (
            stage != "sandboxed"
            or not isinstance(active_loop, Mapping)
            or active_loop.get("loop_id") != loop_id
        ):
            return _candidate_error_response(
                governor,
                status_code=409,
                code="candidate_not_run_ready",
                message="Only the active sandboxed candidate can run evidence probes.",
            )

        record, disposition = _reserve_candidate_run(
            governor,
            loop_id=loop_id,
            candidate_kind=candidate_kind,
            retry_key=retry_key,
        )
        if disposition == "completed":
            persisted = _public_candidate_run(governor.status(), candidate_kind)
            return JSONResponse(
                status_code=200,
                content=persisted,
                headers={"Idempotency-Replayed": "true"},
            )
        if disposition == "pending":
            return _candidate_execution_response(
                governor,
                status_code=409,
                code="candidate_run_in_progress",
                message="Evidence probes are already running for this loop.",
                retryable=False,
            )
        if disposition == "retryable_failed":
            return _candidate_execution_response(
                governor,
                status_code=503,
                code=str(record.get("error_code") or "candidate_infrastructure_unavailable"),
                message=str(record.get("error_message") or "Candidate infrastructure is unavailable."),
                retryable=True,
            )

        if disposition == "terminal_failed":
            return _candidate_execution_response(
                governor,
                status_code=409,
                code=str(record.get("error_code") or "candidate_contract_failed"),
                message=str(
                    record.get("error_message")
                    or "Candidate execution failed a non-retryable governor contract."
                ),
                retryable=False,
            )

        current_status = governor.status()
        current_loop = _candidate_loop(current_status, loop_id)
        if current_loop is not None and current_loop.get("stage") == "awaiting_authorization":
            _set_candidate_run_state(governor, record, state="completed")
            return JSONResponse(
                status_code=200,
                content=_public_candidate_run(current_status, candidate_kind),
                headers={"Idempotency-Replayed": "true"},
            )
        if (
            current_loop is None
            or current_loop.get("stage") != "sandboxed"
            or current_status.get("active_loop") is not current_loop
        ):
            _set_candidate_run_state(
                governor,
                record,
                state="retryable_failed",
                error_code="candidate_not_run_ready",
                error_message="Candidate stage changed before evidence execution.",
            )
            return _candidate_execution_response(
                governor,
                status_code=503,
                code="candidate_not_run_ready",
                message="Candidate stage changed before evidence execution.",
                retryable=True,
            )

        runner_result = run_improvement_candidate(candidate_kind, loop=current_loop)
        screened = governor.screen(loop_id, runner_result["receipt"])
        persisted = _public_candidate_run(screened, candidate_kind)
        if "candidate_run" not in persisted:
            raise CandidateRunError("Governor did not persist candidate screening evidence")
        _set_candidate_run_state(governor, record, state="completed")
        return JSONResponse(
            status_code=200,
            content=persisted,
            headers={"Idempotency-Replayed": "false"},
        )
    except CandidateRunError as error:
        if record is not None and disposition == "created":
            _set_candidate_run_state(
                governor,
                record,
                state="retryable_failed",
                error_code="candidate_infrastructure_unavailable",
                error_message=str(error),
            )
        return _candidate_execution_response(
            governor,
            status_code=503,
            code="candidate_infrastructure_unavailable",
            message=str(error),
            retryable=True,
        )
    except GovernorError as error:
        if record is None or disposition != "created":
            return _error_response(governor, error)

        current_status = governor.status()
        current_loop = _candidate_loop(current_status, loop_id)
        if current_loop is not None and isinstance(current_loop.get("screening"), Mapping):
            _set_candidate_run_state(governor, record, state="completed")
            return _public_candidate_run(current_status, candidate_kind)

        error_response = _error_response(governor, error)
        if 400 <= error_response.status_code < 500:
            _set_candidate_run_state(
                governor,
                record,
                state="terminal_failed",
                error_code=error.code,
                error_message=str(error),
            )
            return error_response

        _set_candidate_run_state(
            governor,
            record,
            state="retryable_failed",
            error_code=error.code,
            error_message=str(error),
        )
        return _candidate_execution_response(
            governor,
            status_code=503,
            code=error.code,
            message=str(error),
            retryable=True,
        )
    except Exception:
        if record is not None and disposition == "created":
            _set_candidate_run_state(
                governor,
                record,
                state="retryable_failed",
                error_code="candidate_execution_failed",
                error_message="Candidate execution ended unexpectedly.",
            )
        return _candidate_execution_response(
            governor,
            status_code=503,
            code="candidate_execution_failed",
            message="Candidate execution ended unexpectedly. Retry the fixed candidate.",
            retryable=True,
        )


@router.post("/loops/{loop_id}/rollback")
def rollback_improvement_loop(
    loop_id: str,
    governor: Annotated[
        ImprovementGovernor | GovernorInitializationFailure,
        Depends(get_improvement_governor),
    ],
    payload: Annotated[dict[str, Any] | None, Body()] = None,
) -> Any:
    dependency_error = _dependency_failure_response(governor)
    if dependency_error is not None:
        return dependency_error
    reason = "operator_requested_via_api"
    if payload is not None and isinstance(payload.get("reason"), str):
        reason = payload["reason"]
    try:
        return governor.rollback(loop_id, reason)
    except GovernorError as error:
        return _error_response(governor, error)
