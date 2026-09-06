"""Durable, private host-generation authority for the game agent.

This module owns only authorization state: a local host control key, signed
control-plane requests, one-time nonces, idempotent operations, and runtime
fences. It never selects or calls an inference provider.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

RUNTIME_CONTRACT = "raph-obus-game-runtime-v1"
SKEW_SECONDS = 60
NONCE_TTL_SECONDS = 120
_MIN_LEASE_SECONDS = 5
_MAX_LEASE_SECONDS = 600
_UUID4_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")


class RuntimeDenied(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Produce the exact UTF-8 body representation covered by host HMAC."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _uuid4(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _UUID4_RE.fullmatch(value):
        raise RuntimeDenied(400, code)
    return value


def _string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 100:
        raise RuntimeDenied(400, code)
    return value


@dataclass(frozen=True)
class RuntimeSnapshot:
    boot_epoch: str
    generation: str | None
    policy_revision: int
    lease_expires_at_ms: int | None
    enabled: bool
    mode: str = "local"
    codex: bool = False
    exportable: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "contract": RUNTIME_CONTRACT,
            "bootEpoch": self.boot_epoch,
            "generation": self.generation,
            "sessionPolicyRevision": self.policy_revision,
            "leaseExpiresAtMs": self.lease_expires_at_ms,
            "policy": {
                "enabled": self.enabled,
                "mode": self.mode,
                "codex": self.codex,
                "exportable": self.exportable,
            },
        }


class GameRuntimeAuthority:
    """Local, durable capability authority for one game-agent process lifetime."""

    def __init__(self, root: Path, *, clock: Callable[[], int] = _now_ms) -> None:
        self.root = root
        self._clock = clock
        self.boot_epoch = str(uuid.uuid4())
        self._initialize()

    @property
    def _db_path(self) -> Path:
        return self.root / "runtime.sqlite"

    @property
    def _token_path(self) -> Path:
        return self.root / "host-control-token"

    def host_key(self) -> bytes:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            with self._token_path.open("x", encoding="ascii") as handle:
                handle.write(secrets.token_hex(32))
            try:
                self._token_path.chmod(0o600)
            except OSError:
                pass
        except FileExistsError:
            pass
        raw = self._token_path.read_text(encoding="ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", raw):
            raise RuntimeError("host-control-token must contain exactly 64 lowercase hexadecimal characters")
        return bytes.fromhex(raw)

    def _connect(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._transaction() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions(
                  campaign TEXT NOT NULL,
                  session TEXT NOT NULL,
                  boot_epoch TEXT NOT NULL,
                  generation TEXT,
                  policy_revision INTEGER NOT NULL,
                  lease_expires_at_ms INTEGER,
                  enabled INTEGER NOT NULL,
                  mode TEXT NOT NULL,
                  codex INTEGER NOT NULL,
                  exportable INTEGER NOT NULL,
                  PRIMARY KEY(campaign, session)
                );
                CREATE TABLE IF NOT EXISTS nonces(
                  nonce TEXT PRIMARY KEY,
                  seen_at_ms INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations(
                  op_id TEXT PRIMARY KEY,
                  action TEXT NOT NULL,
                  fingerprint TEXT NOT NULL,
                  response TEXT NOT NULL,
                  created_at_ms INTEGER NOT NULL
                );
                """
            )

    def _signed_bytes(self, method: str, path: str, timestamp: str, nonce: str, body: Mapping[str, Any]) -> bytes:
        digest = hashlib.sha256(canonical_json(body)).hexdigest()
        return f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{digest}".encode("utf-8")

    def verify_host(self, method: str, path: str, body: Mapping[str, Any], headers: Mapping[str, str]) -> None:
        normalized = {str(key).lower(): str(value) for key, value in headers.items()}
        timestamp = normalized.get("x-obus-game-timestamp", "")
        nonce = normalized.get("x-obus-game-nonce", "")
        signature = normalized.get("x-obus-game-signature", "")
        if not re.fullmatch(r"[0-9]{10,}", timestamp):
            raise RuntimeDenied(401, "host_timestamp_invalid")
        if abs((self._clock() // 1000) - int(timestamp)) > SKEW_SECONDS:
            raise RuntimeDenied(401, "host_timestamp_stale")
        if not re.fullmatch(r"[0-9a-f]{64}", nonce):
            raise RuntimeDenied(401, "host_nonce_invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", signature):
            raise RuntimeDenied(401, "host_signature_invalid")
        expected = hmac.new(self.host_key(), self._signed_bytes(method, path, timestamp, nonce, body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise RuntimeDenied(401, "host_signature_invalid")
        now = self._clock()
        with self._transaction() as db:
            db.execute("DELETE FROM nonces WHERE seen_at_ms < ?", (now - NONCE_TTL_SECONDS * 1000,))
            try:
                db.execute("INSERT INTO nonces(nonce, seen_at_ms) VALUES(?, ?)", (nonce, now))
            except sqlite3.IntegrityError as exc:
                raise RuntimeDenied(409, "host_nonce_replayed") from exc

    def _snapshot_from(self, row: sqlite3.Row | None) -> RuntimeSnapshot:
        if row is None or row["boot_epoch"] != self.boot_epoch or not row["generation"]:
            return RuntimeSnapshot(self.boot_epoch, None, row["policy_revision"] if row else 0, None, False)
        expires = int(row["lease_expires_at_ms"] or 0)
        if expires <= self._clock():
            return RuntimeSnapshot(self.boot_epoch, None, int(row["policy_revision"]), None, False)
        return RuntimeSnapshot(
            self.boot_epoch,
            str(row["generation"]),
            int(row["policy_revision"]),
            expires,
            bool(row["enabled"]),
            str(row["mode"]),
            bool(row["codex"]),
            bool(row["exportable"]),
        )

    def snapshot(self, campaign: str, session: str) -> RuntimeSnapshot:
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM sessions WHERE campaign=? AND session=?", (campaign, session)).fetchone()
        finally:
            connection.close()
        return self._snapshot_from(row)

    def _validate_common(self, body: Mapping[str, Any], fields: set[str]) -> None:
        if set(body) != fields or body.get("contract") != RUNTIME_CONTRACT:
            raise RuntimeDenied(400, "runtime_body_invalid")
        _string(body.get("campaign"), "runtime_campaign_invalid")
        _string(body.get("session"), "runtime_session_invalid")
        _uuid4(body.get("expectedBootEpoch"), "runtime_boot_epoch_invalid")
        _uuid4(body.get("opId"), "runtime_operation_id_invalid")

    def _lease_seconds(self, body: Mapping[str, Any]) -> int:
        lease = body.get("leaseSeconds")
        if isinstance(lease, bool) or not isinstance(lease, int) or not _MIN_LEASE_SECONDS <= lease <= _MAX_LEASE_SECONDS:
            raise RuntimeDenied(400, "runtime_lease_invalid")
        return lease

    def _operation(self, db: sqlite3.Connection, action: str, body: Mapping[str, Any]) -> dict[str, Any] | None:
        fingerprint = hashlib.sha256(canonical_json(body)).hexdigest()
        prior = db.execute("SELECT action, fingerprint, response FROM operations WHERE op_id=?", (body["opId"],)).fetchone()
        if prior is None:
            return None
        if prior["action"] != action or prior["fingerprint"] != fingerprint:
            raise RuntimeDenied(409, "runtime_operation_conflict")
        return json.loads(prior["response"])

    def _record_operation(self, db: sqlite3.Connection, action: str, body: Mapping[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        db.execute(
            "INSERT INTO operations(op_id, action, fingerprint, response, created_at_ms) VALUES(?,?,?,?,?)",
            (body["opId"], action, hashlib.sha256(canonical_json(body)).hexdigest(), json.dumps(response, separators=(",", ":")), self._clock()),
        )
        return response

    def _current_row(self, db: sqlite3.Connection, campaign: str, session: str) -> sqlite3.Row | None:
        return db.execute("SELECT * FROM sessions WHERE campaign=? AND session=?", (campaign, session)).fetchone()

    def _require_current(self, row: sqlite3.Row | None, body: Mapping[str, Any]) -> None:
        if body["expectedBootEpoch"] != self.boot_epoch:
            raise RuntimeDenied(409, "runtime_boot_epoch_stale")
        if row is None or row["boot_epoch"] != self.boot_epoch or not row["generation"]:
            raise RuntimeDenied(409, "runtime_host_generation_required")
        if int(row["lease_expires_at_ms"] or 0) <= self._clock():
            raise RuntimeDenied(409, "runtime_generation_expired")
        if row["generation"] != body["generation"]:
            raise RuntimeDenied(409, "runtime_generation_stale")

    def register(self, body: Mapping[str, Any]) -> dict[str, Any]:
        fields = {"contract", "campaign", "session", "generation", "expectedBootEpoch", "expectedGeneration", "opId", "leaseSeconds"}
        self._validate_common(body, fields)
        generation = _uuid4(body.get("generation"), "runtime_generation_invalid")
        expected = body.get("expectedGeneration")
        if expected is not None:
            _uuid4(expected, "runtime_expected_generation_invalid")
        lease = self._lease_seconds(body)
        if body["expectedBootEpoch"] != self.boot_epoch:
            raise RuntimeDenied(409, "runtime_boot_epoch_stale")
        with self._transaction() as db:
            replay = self._operation(db, "register", body)
            if replay is not None:
                return replay
            row = self._current_row(db, body["campaign"], body["session"])
            current = self._snapshot_from(row).generation
            if current is None:
                if expected is not None:
                    raise RuntimeDenied(409, "runtime_generation_cas_failed")
            elif expected != current:
                raise RuntimeDenied(409, "runtime_generation_cas_failed")
            if generation == current:
                raise RuntimeDenied(409, "runtime_generation_reused")
            expires = self._clock() + lease * 1000
            db.execute(
                """INSERT INTO sessions(campaign,session,boot_epoch,generation,policy_revision,lease_expires_at_ms,enabled,mode,codex,exportable)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(campaign,session) DO UPDATE SET boot_epoch=excluded.boot_epoch,generation=excluded.generation,
                   policy_revision=excluded.policy_revision,lease_expires_at_ms=excluded.lease_expires_at_ms,enabled=excluded.enabled,
                   mode=excluded.mode,codex=excluded.codex,exportable=excluded.exportable""",
                (body["campaign"], body["session"], self.boot_epoch, generation, 0, expires, 1, "local", 0, 0),
            )
            response = {"status": "registered", "runtime": RuntimeSnapshot(self.boot_epoch, generation, 0, expires, True).public()}
            return self._record_operation(db, "register", body, response)

    def renew(self, body: Mapping[str, Any]) -> dict[str, Any]:
        fields = {"contract", "campaign", "session", "generation", "expectedBootEpoch", "expectedSessionPolicyRevision", "opId", "leaseSeconds"}
        self._validate_common(body, fields)
        _uuid4(body.get("generation"), "runtime_generation_invalid")
        revision = body.get("expectedSessionPolicyRevision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise RuntimeDenied(400, "runtime_policy_revision_invalid")
        lease = self._lease_seconds(body)
        with self._transaction() as db:
            replay = self._operation(db, "renew", body)
            if replay is not None:
                return replay
            row = self._current_row(db, body["campaign"], body["session"])
            self._require_current(row, body)
            if row["policy_revision"] != revision:
                raise RuntimeDenied(409, "runtime_policy_revision_stale")
            expires = self._clock() + lease * 1000
            db.execute("UPDATE sessions SET lease_expires_at_ms=? WHERE campaign=? AND session=?", (expires, body["campaign"], body["session"]))
            response = {"status": "renewed", "runtime": RuntimeSnapshot(self.boot_epoch, body["generation"], revision, expires, bool(row["enabled"]), str(row["mode"]), bool(row["codex"]), bool(row["exportable"])).public()}
            return self._record_operation(db, "renew", body, response)

    def patch_policy(self, body: Mapping[str, Any]) -> dict[str, Any]:
        fields = {"contract", "campaign", "session", "generation", "expectedBootEpoch", "expectedSessionPolicyRevision", "opId", "policy"}
        self._validate_common(body, fields)
        _uuid4(body.get("generation"), "runtime_generation_invalid")
        revision = body.get("expectedSessionPolicyRevision")
        policy = body.get("policy")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise RuntimeDenied(400, "runtime_policy_revision_invalid")
        if not isinstance(policy, Mapping) or set(policy) != {"enabled", "mode", "codex", "exportable"}:
            raise RuntimeDenied(400, "runtime_policy_invalid")
        if not isinstance(policy["enabled"], bool) or policy["mode"] != "local" or policy["codex"] is not False or policy["exportable"] is not False:
            raise RuntimeDenied(409, "runtime_policy_not_local_only")
        with self._transaction() as db:
            replay = self._operation(db, "patch_policy", body)
            if replay is not None:
                return replay
            row = self._current_row(db, body["campaign"], body["session"])
            self._require_current(row, body)
            if row["policy_revision"] != revision:
                raise RuntimeDenied(409, "runtime_policy_revision_stale")
            next_revision = revision + 1
            db.execute(
                "UPDATE sessions SET policy_revision=?, enabled=?, mode='local', codex=0, exportable=0 WHERE campaign=? AND session=?",
                (next_revision, int(policy["enabled"]), body["campaign"], body["session"]),
            )
            response = {"status": "policy_updated", "runtime": RuntimeSnapshot(self.boot_epoch, body["generation"], next_revision, int(row["lease_expires_at_ms"]), policy["enabled"]).public()}
            return self._record_operation(db, "patch_policy", body, response)
