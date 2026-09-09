"""Metadata-only external dispatch receipts in the authoritative game database.

Ledger functions own no transaction. Use runtime->game dispatch guards for
claims and successful results; diagnostics may use a game-only transaction but
must never acquire runtime afterwards. A committed dispatched row is the send
linearization point, not proof that a remote service received bytes. Such rows
are never automatically requeued, including after restart.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid
from typing import Any, Mapping

SCHEMA_VERSION = 1
_STATES = ("queued", "dispatched", "completed", "failed", "uncertain", "discarded", "cancelled")
_FINAL = {"completed", "failed", "uncertain", "discarded"}
_REASONS = {"policy_changed", "generation_changed", "session_revoked", "session_rejoined", "evidence_changed", "consent_changed", "host_restart"}
_HEX = re.compile(r"[0-9a-f]{64}")
_SAFE_MAX = 9007199254740991


class DispatchDenied(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status, self.code = status, code


def _text(value: Any, maximum: int = 100) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise DispatchDenied(400, "dispatch_metadata_invalid")
    return value


def _integer(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= _SAFE_MAX:
        raise DispatchDenied(400, "dispatch_metadata_invalid")
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise DispatchDenied(400, "dispatch_digest_invalid")
    return value


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _transaction(db: sqlite3.Connection) -> None:
    if not db.in_transaction:
        raise DispatchDenied(409, "dispatch_transaction_required")


def _exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def schema_ready(db: sqlite3.Connection) -> bool:
    """Never migrate from a policy writer or an inference commit guard."""
    if not _exists(db, "dispatch_schema"):
        if _exists(db, "dispatch_jobs") or _exists(db, "dispatch_attempts"):
            raise DispatchDenied(409, "dispatch_schema_incomplete")
        return False
    row = db.execute("SELECT version FROM dispatch_schema WHERE singleton=1").fetchone()
    if row is None or row[0] != SCHEMA_VERSION or not _exists(db, "dispatch_jobs") or not _exists(db, "dispatch_attempts"):
        raise DispatchDenied(409, "dispatch_schema_unsupported")
    return True


def _create_schema(db: sqlite3.Connection) -> None:
    # Individual statements preserve the caller transaction; never executescript.
    db.execute("CREATE TABLE dispatch_schema(singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)")
    db.execute("""CREATE TABLE dispatch_jobs(
      campaign TEXT NOT NULL, session TEXT NOT NULL, owner TEXT NOT NULL,
      request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
      PRIMARY KEY(campaign,session,owner,request_id))""")
    db.execute("""CREATE TABLE dispatch_attempts(
      attempt_id TEXT PRIMARY KEY, campaign TEXT NOT NULL, session TEXT NOT NULL,
      owner TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
      route_digest TEXT NOT NULL, metadata TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('queued','dispatched','completed','failed','uncertain','discarded','cancelled')),
      created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL,
      dispatched_at_ms INTEGER, finished_at_ms INTEGER,
      cancel_requested INTEGER NOT NULL DEFAULT 0, cancel_reason TEXT,
      provenance TEXT,
      UNIQUE(campaign,session,owner,request_id,route_digest))""")
    db.execute("CREATE INDEX dispatch_recent ON dispatch_attempts(campaign,session,updated_at_ms)")
    db.execute("INSERT INTO dispatch_schema(singleton,version) VALUES(1,?)", (SCHEMA_VERSION,))


def initialize_schema(db: sqlite3.Connection) -> None:
    """Initialize an empty fixture/new database; existing stores need preflight.

    This function owns no transaction. Refuse additive migration of existing
    game data without the consistent backup made by prepare_dispatch_store.
    """
    _transaction(db)
    if schema_ready(db):
        return
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1").fetchone():
        raise DispatchDenied(409, "dispatch_backup_required")
    _create_schema(db)


def prepare_dispatch_store(game_path: Path) -> dict[str, Any]:
    """Back up before additive migration, outside every runtime/game guard.

    A game-only BEGIN IMMEDIATE reserves the writer before a separate read-only
    connection takes an online backup. The reserved connection has not changed
    data, so the backup is consistent in both DELETE and WAL journal modes.
    No runtime lock is acquired. Concurrent preparers serialize, and a failed
    backup prevents schema creation. A crash can leave an extra backup, never a
    migrated database lacking its prior backup. Journal mode is unchanged.
    """
    path = Path(game_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    backup_path: Path | None = None
    try:
        # Keep the multi-query schema probe coherent if another preparer commits
        # its entire migration between individual sqlite_master reads.
        db.execute("BEGIN")
        ready = schema_ready(db)
        db.execute("COMMIT")
        if ready:
            return {"status": "ready", "version": SCHEMA_VERSION}
        db.execute("BEGIN IMMEDIATE")
        if schema_ready(db):
            db.execute("COMMIT")
            return {"status": "ready", "version": SCHEMA_VERSION}
        has_data = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1").fetchone() is not None
        if has_data:
            directory = path.parent / "backups"
            directory.mkdir(parents=True, exist_ok=True)
            backup_path = directory / f"game-before-dispatch-v1-{uuid.uuid4()}.sqlite"
            # Exclusive creation prevents accidental replacement of a backup.
            with backup_path.open("xb"):
                pass
            try:
                source = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)
                destination = sqlite3.connect(backup_path)
                try:
                    source.backup(destination)
                    if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise DispatchDenied(500, "dispatch_backup_invalid")
                finally:
                    destination.close()
                    source.close()
                with backup_path.open("rb") as handle:
                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
            except BaseException:
                # Leave any partial backup for diagnosis, but never migrate.
                raise
        _create_schema(db)
        db.execute("COMMIT")
        result: dict[str, Any] = {"status": "prepared", "version": SCHEMA_VERSION, "backedUp": has_data}
        if backup_path is not None:
            result.update(backupPath=str(backup_path), backupSha256=digest)
        return result
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def _row(db: sqlite3.Connection, attempt_id: str) -> dict[str, Any]:
    cursor = db.execute("SELECT * FROM dispatch_attempts WHERE attempt_id=?", (_text(attempt_id),))
    value = cursor.fetchone()
    if value is None:
        raise DispatchDenied(404, "dispatch_attempt_missing")
    return dict(zip((item[0] for item in cursor.description), value))


def _receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = json.loads(row["metadata"])
    receipt = {
        "attemptId": row["attempt_id"], "status": row["status"],
        "task": metadata["task"], "provider": metadata["provider"], "model": metadata["model"],
        "createdAtMs": row["created_at_ms"], "updatedAtMs": row["updated_at_ms"],
        "dispatchedAtMs": row["dispatched_at_ms"], "finishedAtMs": row["finished_at_ms"],
        "cancelRequested": bool(row["cancel_requested"]), "cancelReason": row["cancel_reason"],
    }
    if row["provenance"] is not None:
        receipt["provenance"] = json.loads(row["provenance"])
    return receipt


def enqueue(db: sqlite3.Connection, *, campaign: str, session: str, owner: str,
            request_id: str, fingerprint: str, task: str, boot_epoch: str,
            generation: str, policy_revision: int, evidence_revision: int,
            evidence_digest: str, route_id: str, route_digest: str, provider: str,
            model: str, now_ms: int) -> dict[str, Any]:
    _transaction(db)
    identity = tuple(_text(value) for value in (campaign, session, owner, request_id))
    fingerprint, route_digest = _digest(fingerprint), _digest(route_digest)
    metadata = {
        "task": _text(task, 32), "boot_epoch": _text(boot_epoch), "generation": _text(generation),
        "policy_revision": _integer(policy_revision), "evidence_revision": _integer(evidence_revision),
        "evidence_digest": _digest(evidence_digest), "route_id": _text(route_id, 160),
        "route_digest": route_digest, "provider": _text(provider, 160), "model": _text(model, 200),
    }
    now_ms = _integer(now_ms)
    prior = db.execute("SELECT fingerprint FROM dispatch_jobs WHERE campaign=? AND session=? AND owner=? AND request_id=?", identity).fetchone()
    if prior and prior[0] != fingerprint:
        raise DispatchDenied(409, "dispatch_request_conflict")
    existing = db.execute("SELECT attempt_id, metadata FROM dispatch_attempts WHERE campaign=? AND session=? AND owner=? AND request_id=? AND route_digest=?", (*identity, route_digest)).fetchone()
    if existing:
        if existing[1] != _json(metadata):
            raise DispatchDenied(409, "dispatch_attempt_conflict")
        return _receipt(_row(db, existing[0]))
    blocked = db.execute("SELECT 1 FROM dispatch_attempts WHERE campaign=? AND session=? AND owner=? AND request_id=? AND status IN ('dispatched','uncertain','completed','discarded') LIMIT 1", identity).fetchone()
    if blocked:
        raise DispatchDenied(409, "dispatch_request_already_sent")
    count = db.execute("SELECT count(*) FROM dispatch_attempts WHERE campaign=? AND session=? AND owner=? AND request_id=?", identity).fetchone()[0]
    if count >= 8:
        raise DispatchDenied(409, "dispatch_attempt_limit")
    if prior is None:
        db.execute("INSERT INTO dispatch_jobs(campaign,session,owner,request_id,fingerprint) VALUES(?,?,?,?,?)", (*identity, fingerprint))
    attempt_id = str(uuid.uuid4())
    db.execute("""INSERT INTO dispatch_attempts(attempt_id,campaign,session,owner,request_id,fingerprint,
               route_digest,metadata,status,created_at_ms,updated_at_ms) VALUES(?,?,?,?,?,?,?,?,'queued',?,?)""",
               (attempt_id, *identity, fingerprint, route_digest, _json(metadata), now_ms, now_ms))
    return _receipt(_row(db, attempt_id))


def mark_dispatched(db: sqlite3.Connection, attempt_id: str, *, fingerprint: str, now_ms: int) -> dict[str, Any]:
    _transaction(db)
    row = _row(db, attempt_id)
    if row["fingerprint"] != _digest(fingerprint):
        raise DispatchDenied(409, "dispatch_request_conflict")
    if row["status"] != "queued" or row["cancel_requested"]:
        raise DispatchDenied(409, "dispatch_attempt_not_queued")
    # Different eligible routes may already be queued by competing workers. A
    # logical job still gets at most one active/uncertain send across all routes.
    blocked = db.execute("""SELECT 1 FROM dispatch_attempts WHERE campaign=? AND session=?
        AND owner=? AND request_id=? AND attempt_id<>?
        AND status IN ('dispatched','uncertain','completed','discarded') LIMIT 1""",
        (row["campaign"], row["session"], row["owner"], row["request_id"], attempt_id)).fetchone()
    if blocked:
        raise DispatchDenied(409, "dispatch_request_already_sent")
    now_ms = _integer(now_ms)
    db.execute("UPDATE dispatch_attempts SET status='dispatched',dispatched_at_ms=?,updated_at_ms=? WHERE attempt_id=?", (now_ms, now_ms, attempt_id))
    return _receipt(_row(db, attempt_id))


def _provenance(value: Mapping[str, Any] | None, metadata: Mapping[str, Any]) -> str | None:
    if value is None:
        return None
    permitted = {"provider", "model", "gateway", "route_id", "destination", "cost", "cost_basis", "completion_tokens", "response_id"}
    if not isinstance(value, Mapping) or set(value) - permitted:
        raise DispatchDenied(400, "dispatch_provenance_invalid")
    normalized = {}
    for key, item in value.items():
        normalized[key] = _integer(item) if key == "completion_tokens" else _text(item, 200)
    if (normalized.get("provider") != metadata["provider"] or normalized.get("model") != metadata["model"]
            or normalized.get("route_id") != metadata["route_id"] or normalized.get("destination") != "external"
            or normalized.get("cost") != "zero"):
        raise DispatchDenied(409, "dispatch_provenance_mismatch")
    return _json(normalized)


def finish(db: sqlite3.Connection, attempt_id: str, *, fingerprint: str, outcome: str,
           now_ms: int, provenance: Mapping[str, Any] | None = None) -> dict[str, Any]:
    _transaction(db)
    row = _row(db, attempt_id)
    if row["fingerprint"] != _digest(fingerprint):
        raise DispatchDenied(409, "dispatch_request_conflict")
    if outcome not in _FINAL:
        raise DispatchDenied(400, "dispatch_outcome_invalid")
    encoded = _provenance(provenance, json.loads(row["metadata"]))
    if row["status"] == outcome and row["provenance"] == encoded:
        return _receipt(row)
    if row["status"] != "dispatched":
        raise DispatchDenied(409, "dispatch_attempt_not_dispatched")
    if outcome == "completed" and (row["cancel_requested"] or encoded is None):
        raise DispatchDenied(409, "dispatch_result_not_authorized")
    now_ms = _integer(now_ms)
    db.execute("UPDATE dispatch_attempts SET status=?,updated_at_ms=?,finished_at_ms=?,provenance=? WHERE attempt_id=?", (outcome, now_ms, now_ms, encoded, attempt_id))
    return _receipt(_row(db, attempt_id))


def cancel_queued(db: sqlite3.Connection, *, campaign: str, session: str | None = None,
                  reason: str, now_ms: int, uncertain_dispatched: bool = False) -> dict[str, int]:
    _transaction(db)
    _text(campaign)
    if session is not None:
        _text(session)
    if reason not in _REASONS or type(uncertain_dispatched) is not bool:
        raise DispatchDenied(400, "dispatch_cancellation_invalid")
    now_ms = _integer(now_ms)
    condition = "campaign=?" + (" AND session=?" if session is not None else "")
    scope = (campaign, session) if session is not None else (campaign,)
    cancelled = db.execute(f"UPDATE dispatch_attempts SET status='cancelled',cancel_requested=1,cancel_reason=?,updated_at_ms=?,finished_at_ms=? WHERE {condition} AND status='queued'", (reason, now_ms, now_ms, *scope)).rowcount
    status = "uncertain" if uncertain_dispatched else "dispatched"
    active = db.execute(f"UPDATE dispatch_attempts SET status=?,cancel_requested=1,cancel_reason=?,updated_at_ms=? WHERE {condition} AND status='dispatched'", (status, reason, now_ms, *scope)).rowcount
    return {"cancelled": cancelled, "inFlight": active}


def recent(db: sqlite3.Connection, *, campaign: str, session: str | None = None, limit: int = 20) -> dict[str, Any]:
    _text(campaign)
    if session is not None:
        _text(session)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise DispatchDenied(400, "dispatch_limit_invalid")
    if not schema_ready(db):
        return {"jobs": [], "counts": {state: 0 for state in _STATES}}
    condition = "campaign=?" + (" AND session=?" if session is not None else "")
    scope = (campaign, session) if session is not None else (campaign,)
    rows = db.execute(f"SELECT attempt_id FROM dispatch_attempts WHERE {condition} ORDER BY updated_at_ms DESC,attempt_id LIMIT ?", (*scope, limit)).fetchall()
    counts = {state: 0 for state in _STATES}
    counts.update(dict(db.execute(f"SELECT status,count(*) FROM dispatch_attempts WHERE {condition} GROUP BY status", scope).fetchall()))
    return {"jobs": [_receipt(_row(db, row[0])) for row in rows], "counts": counts}
