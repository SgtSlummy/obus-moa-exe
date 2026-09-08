"""Durable, private campaign-runtime authority for the game agent.

A campaign owns one host generation, lease, and local-only policy.  A session
holds only a lease under that generation and an effective policy revision.  The
module never selects or calls an inference provider.
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
            "requiredForRoute": True,
            "effectivePolicy": {
                "enabled": self.enabled,
                "mode": self.mode,
                "codex": self.codex,
                "exportable": self.exportable,
                "tools": False,
                "personalMemory": False,
                "autoMemory": False,
            },
            "policy": {
                "enabled": self.enabled,
                "mode": self.mode,
                "codex": self.codex,
                "exportable": self.exportable,
            },
        }


class GameRuntimeAuthority:
    """Local campaign master authority for a single game-agent process boot."""

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
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    @contextmanager
    def receipt_transaction(
        self,
        campaign: str,
        session: str,
        *,
        boot_epoch: str,
        generation: str,
        policy_revision: int,
    ) -> Iterator[sqlite3.Connection]:
        """Commit a game receipt under the same SQLite lock used by runtime writers.

        Initialize game.sqlite's schema before entering, and do not enter while
        holding another game write transaction. Perform inference before this
        short section; its body may only read/write receipts using the yielded
        connection, without committing, rolling back or running executescript.

        Two connections give explicit commit order without relying on ATTACH or
        changing journal modes: runtime BEGIN IMMEDIATE excludes policy writers
        in every authority/process until the game transaction commits or rolls
        back. This guard never writes runtime rows. It is not a two-database
        crash transaction; game.sqlite alone owns receipt atomicity. A crash
        before its commit rolls back the receipt, while a committed receipt was
        validated before any subsequent policy writer could acquire the lock.
        """
        _string(campaign, "runtime_campaign_invalid")
        _string(session, "runtime_session_invalid")
        if (not isinstance(boot_epoch, str) or not isinstance(generation, str)
                or isinstance(policy_revision, bool) or not isinstance(policy_revision, int)
                or policy_revision < 0):
            raise RuntimeDenied(400, "runtime_fence_invalid")
        expected = (boot_epoch, generation, policy_revision)
        # Existing-file mode prevents missing initialization from silently
        # creating a second or empty authoritative game database.
        game_uri = (self.root / "game.sqlite").resolve().as_uri() + "?mode=rw"
        game = sqlite3.connect(game_uri, uri=True, timeout=10, isolation_level=None)
        game.row_factory = sqlite3.Row
        try:
            with self._transaction() as runtime:
                def validate() -> None:
                    snapshot = self._snapshot_from(
                        self._campaign_row(runtime, campaign), self._session_row(runtime, campaign, session)
                    )
                    if not snapshot.generation:
                        raise RuntimeDenied(409, "runtime_host_generation_required")
                    if (snapshot.boot_epoch, snapshot.generation, snapshot.policy_revision) != expected:
                        raise RuntimeDenied(409, "runtime_fence_stale")
                    if not snapshot.enabled:
                        raise RuntimeDenied(409, "game_ai_disabled")
                    if snapshot.mode != "local" or snapshot.codex or snapshot.exportable:
                        raise RuntimeDenied(409, "runtime_policy_not_local_only")

                def receipt_statements_only(action: int, _arg1, _arg2, _database, _trigger) -> int:
                    if action in {sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT,
                                  sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA}:
                        return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK

                try:
                    game.execute("BEGIN IMMEDIATE")
                    validate()
                    # Guard ownership also prevents accidental `with game:` or
                    # executescript calls from committing before final validation.
                    game.set_authorizer(receipt_statements_only)
                    try:
                        yield game
                    finally:
                        game.set_authorizer(None)
                    # Recheck leases after the body, immediately before commit.
                    # Policy/generation/revocation writers still cannot proceed.
                    validate()
                    game.execute("COMMIT")
                except BaseException:
                    if game.in_transaction:
                        game.execute("ROLLBACK")
                    raise
        finally:
            game.close()

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaign_runtime(
                  campaign TEXT PRIMARY KEY,
                  boot_epoch TEXT NOT NULL,
                  generation TEXT,
                  policy_revision INTEGER NOT NULL,
                  lease_expires_at_ms INTEGER,
                  enabled INTEGER NOT NULL,
                  mode TEXT NOT NULL,
                  codex INTEGER NOT NULL,
                  exportable INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS session_runtime(
                  campaign TEXT NOT NULL,
                  session TEXT NOT NULL,
                  generation TEXT,
                  policy_revision INTEGER NOT NULL,
                  lease_expires_at_ms INTEGER,
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
        finally:
            connection.close()

    def _signed_bytes(self, method: str, path: str, timestamp: str, nonce: str, body: Mapping[str, Any]) -> bytes:
        digest = hashlib.sha256(canonical_json(body)).hexdigest()
        return f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{digest}".encode("utf-8")

    def verify_host(self, method: str, path: str, body: Mapping[str, Any], headers: Mapping[str, str]) -> None:
        normalized = {str(key).lower(): str(value) for key, value in headers.items()}
        timestamp = normalized.get("x-obus-game-host-timestamp", "")
        nonce = normalized.get("x-obus-game-host-nonce", "")
        signature = normalized.get("x-obus-game-host-signature", "")
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

    def _campaign_row(self, db: sqlite3.Connection, campaign: str) -> sqlite3.Row | None:
        return db.execute("SELECT * FROM campaign_runtime WHERE campaign=?", (campaign,)).fetchone()

    def _session_row(self, db: sqlite3.Connection, campaign: str, session: str) -> sqlite3.Row | None:
        return db.execute("SELECT * FROM session_runtime WHERE campaign=? AND session=?", (campaign, session)).fetchone()

    def _campaign_active(self, master: sqlite3.Row | None) -> bool:
        return bool(
            master
            and master["boot_epoch"] == self.boot_epoch
            and master["generation"]
            and int(master["lease_expires_at_ms"] or 0) > self._clock()
        )

    def _snapshot_from(self, master: sqlite3.Row | None, child: sqlite3.Row | None) -> RuntimeSnapshot:
        revision = int(child["policy_revision"]) if child else int(master["policy_revision"]) if master else 0
        if not self._campaign_active(master):
            return RuntimeSnapshot(self.boot_epoch, None, revision, None, False)
        if child is None or child["generation"] != master["generation"] or int(child["lease_expires_at_ms"] or 0) <= self._clock():
            return RuntimeSnapshot(self.boot_epoch, None, revision, None, False)
        return RuntimeSnapshot(
            self.boot_epoch,
            str(master["generation"]),
            revision,
            min(int(master["lease_expires_at_ms"]), int(child["lease_expires_at_ms"])),
            bool(master["enabled"]),
            str(master["mode"]),
            bool(master["codex"]),
            bool(master["exportable"]),
        )

    def snapshot(self, campaign: str, session: str) -> RuntimeSnapshot:
        connection = self._connect()
        try:
            master = self._campaign_row(connection, campaign)
            child = self._session_row(connection, campaign, session)
        finally:
            connection.close()
        return self._snapshot_from(master, child)

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

    def _require_current(self, master: sqlite3.Row | None, child: sqlite3.Row | None, body: Mapping[str, Any]) -> None:
        if body["expectedBootEpoch"] != self.boot_epoch:
            raise RuntimeDenied(409, "runtime_boot_epoch_stale")
        if master is None or master["boot_epoch"] != self.boot_epoch or not master["generation"]:
            raise RuntimeDenied(409, "runtime_host_generation_required")
        if int(master["lease_expires_at_ms"] or 0) <= self._clock():
            raise RuntimeDenied(409, "runtime_generation_expired")
        if master["generation"] != body["generation"]:
            raise RuntimeDenied(409, "runtime_generation_stale")
        if child is None or child["generation"] != master["generation"]:
            raise RuntimeDenied(409, "runtime_session_generation_required")
        if int(child["lease_expires_at_ms"] or 0) <= self._clock():
            raise RuntimeDenied(409, "runtime_session_lease_expired")

    def _save_session(self, db: sqlite3.Connection, campaign: str, session: str, generation: str, revision: int, expires: int) -> None:
        db.execute(
            """INSERT INTO session_runtime(campaign,session,generation,policy_revision,lease_expires_at_ms)
               VALUES(?,?,?,?,?)
               ON CONFLICT(campaign,session) DO UPDATE SET generation=excluded.generation,
               policy_revision=excluded.policy_revision,lease_expires_at_ms=excluded.lease_expires_at_ms""",
            (campaign, session, generation, revision, expires),
        )

    def _reset_campaign(self, db: sqlite3.Connection, body: Mapping[str, Any], generation: str, lease: int, master: sqlite3.Row | None) -> RuntimeSnapshot:
        next_master_revision = (int(master["policy_revision"]) + 1) if master else 0
        previous_child = self._session_row(db, body["campaign"], body["session"])
        session_revision = (int(previous_child["policy_revision"]) + 1) if previous_child else next_master_revision
        expires = self._clock() + lease * 1000
        db.execute(
            """INSERT INTO campaign_runtime(campaign,boot_epoch,generation,policy_revision,lease_expires_at_ms,enabled,mode,codex,exportable)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(campaign) DO UPDATE SET boot_epoch=excluded.boot_epoch,generation=excluded.generation,
               policy_revision=excluded.policy_revision,lease_expires_at_ms=excluded.lease_expires_at_ms,enabled=excluded.enabled,
               mode=excluded.mode,codex=excluded.codex,exportable=excluded.exportable""",
            (body["campaign"], self.boot_epoch, generation, next_master_revision, expires, 1, "local", 0, 0),
        )
        # A new master generation invalidates every old child fence.  The caller's
        # session is then registered under the new generation in the same write.
        db.execute(
            "UPDATE session_runtime SET generation=NULL, lease_expires_at_ms=NULL, policy_revision=policy_revision+1 WHERE campaign=?",
            (body["campaign"],),
        )
        self._save_session(db, body["campaign"], body["session"], generation, session_revision, expires)
        return RuntimeSnapshot(self.boot_epoch, generation, session_revision, expires, True)

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
            master = self._campaign_row(db, body["campaign"])
            active = self._campaign_active(master)
            current = str(master["generation"]) if active else None
            if body["session"] != "campaign":
                # A child can only join the live campaign generation. Its CAS
                # compares the child snapshot, never the parent's generation.
                if current is None:
                    raise RuntimeDenied(409, "runtime_host_generation_required")
                if generation != current:
                    raise RuntimeDenied(409, "runtime_generation_stale")
                child = self._session_row(db, body["campaign"], body["session"])
                observed = self._snapshot_from(master, child)
                if expected != observed.generation:
                    raise RuntimeDenied(409, "runtime_generation_cas_failed")
                revision = max(int(master["policy_revision"]), int(child["policy_revision"]) if child else 0)
                if child is not None and observed.generation is None:
                    # Rejoining must not revive an expired or revoked fence.
                    revision += 1
                expires = self._clock() + lease * 1000
                self._save_session(db, body["campaign"], body["session"], current, revision, expires)
                refreshed_child = self._session_row(db, body["campaign"], body["session"])
                response = {"status": "registered", "runtime": self._snapshot_from(master, refreshed_child).public()}
                return self._record_operation(db, "register", body, response)
            if current is None:
                if expected is not None:
                    raise RuntimeDenied(409, "runtime_generation_cas_failed")
                snapshot = self._reset_campaign(db, body, generation, lease, master)
                response = {"status": "registered", "runtime": snapshot.public()}
                return self._record_operation(db, "register", body, response)
            if expected != current:
                raise RuntimeDenied(409, "runtime_generation_cas_failed")
            if generation != current:
                snapshot = self._reset_campaign(db, body, generation, lease, master)
                response = {"status": "registered", "runtime": snapshot.public()}
                return self._record_operation(db, "register", body, response)
            child = self._session_row(db, body["campaign"], body["session"])
            revision = int(child["policy_revision"]) if child and child["generation"] == current else int(master["policy_revision"])
            expires = self._clock() + lease * 1000
            self._save_session(db, body["campaign"], body["session"], current, revision, expires)
            db.execute("UPDATE campaign_runtime SET lease_expires_at_ms=? WHERE campaign=?", (expires, body["campaign"]))
            refreshed_master = self._campaign_row(db, body["campaign"])
            refreshed_child = self._session_row(db, body["campaign"], body["session"])
            response = {"status": "registered", "runtime": self._snapshot_from(refreshed_master, refreshed_child).public()}
            return self._record_operation(db, "register", body, response)

    def renew(self, body: Mapping[str, Any]) -> dict[str, Any]:
        fields = {"contract", "campaign", "session", "generation", "expectedBootEpoch", "expectedSessionPolicyRevision", "opId", "leaseSeconds"}
        self._validate_common(body, fields)
        _uuid4(body.get("generation"), "runtime_generation_invalid")
        revision = body.get("expectedSessionPolicyRevision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise RuntimeDenied(400, "runtime_policy_revision_invalid")
        lease = self._lease_seconds(body)
        if body["expectedBootEpoch"] != self.boot_epoch:
            raise RuntimeDenied(409, "runtime_boot_epoch_stale")
        with self._transaction() as db:
            replay = self._operation(db, "renew", body)
            if replay is not None:
                return replay
            master = self._campaign_row(db, body["campaign"])
            child = self._session_row(db, body["campaign"], body["session"])
            self._require_current(master, child, body)
            if child["policy_revision"] != revision:
                raise RuntimeDenied(409, "runtime_policy_revision_stale")
            expires = self._clock() + lease * 1000
            db.execute("UPDATE session_runtime SET lease_expires_at_ms=? WHERE campaign=? AND session=?", (expires, body["campaign"], body["session"]))
            if body["session"] == "campaign":
                db.execute("UPDATE campaign_runtime SET lease_expires_at_ms=? WHERE campaign=?", (expires, body["campaign"]))
            refreshed_master = self._campaign_row(db, body["campaign"])
            refreshed_child = self._session_row(db, body["campaign"], body["session"])
            response = {"status": "renewed", "runtime": self._snapshot_from(refreshed_master, refreshed_child).public()}
            return self._record_operation(db, "renew", body, response)

    def patch_policy(self, body: Mapping[str, Any]) -> dict[str, Any]:
        fields = {"contract", "campaign", "session", "expectedGeneration", "expectedBootEpoch", "expectedSessionPolicyRevision", "opId", "policy"}
        self._validate_common(body, fields)
        if body["session"] != "campaign":
            raise RuntimeDenied(403, "runtime_master_policy_required")
        _uuid4(body.get("expectedGeneration"), "runtime_generation_invalid")
        revision = body.get("expectedSessionPolicyRevision")
        policy = body.get("policy")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise RuntimeDenied(400, "runtime_policy_revision_invalid")
        if not isinstance(policy, Mapping) or set(policy) != {"enabled", "mode", "codex", "exportable"}:
            raise RuntimeDenied(400, "runtime_policy_invalid")
        if not isinstance(policy["enabled"], bool) or policy["mode"] != "local" or policy["codex"] is not False or policy["exportable"] is not False:
            raise RuntimeDenied(409, "runtime_policy_not_local_only")
        if body["expectedBootEpoch"] != self.boot_epoch:
            raise RuntimeDenied(409, "runtime_boot_epoch_stale")
        with self._transaction() as db:
            replay = self._operation(db, "patch_policy", body)
            if replay is not None:
                return replay
            master = self._campaign_row(db, body["campaign"])
            child = self._session_row(db, body["campaign"], body["session"])
            self._require_current(master, child, {**body, "generation": body["expectedGeneration"]})
            if child["policy_revision"] != revision:
                raise RuntimeDenied(409, "runtime_policy_revision_stale")
            db.execute(
                "UPDATE campaign_runtime SET policy_revision=policy_revision+1, enabled=?, mode='local', codex=0, exportable=0 WHERE campaign=?",
                (int(policy["enabled"]), body["campaign"]),
            )
            # Every current session gets a new effective revision in one transaction,
            # so queued or late work holding any old four-field fence fails closed.
            db.execute("UPDATE session_runtime SET policy_revision=policy_revision+1 WHERE campaign=?", (body["campaign"],))
            refreshed_master = self._campaign_row(db, body["campaign"])
            refreshed_child = self._session_row(db, body["campaign"], body["session"])
            response = {"status": "policy_updated", "runtime": self._snapshot_from(refreshed_master, refreshed_child).public()}
            return self._record_operation(db, "patch_policy", body, response)

    def revoke_session(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """Immediately invalidate one child fence without altering campaign policy."""
        fields = {"contract", "campaign", "session", "generation", "expectedBootEpoch", "expectedSessionPolicyRevision", "opId"}
        self._validate_common(body, fields)
        if body["session"] == "campaign":
            raise RuntimeDenied(403, "runtime_child_session_required")
        _uuid4(body.get("generation"), "runtime_generation_invalid")
        revision = body.get("expectedSessionPolicyRevision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise RuntimeDenied(400, "runtime_policy_revision_invalid")
        if body["expectedBootEpoch"] != self.boot_epoch:
            raise RuntimeDenied(409, "runtime_boot_epoch_stale")
        with self._transaction() as db:
            replay = self._operation(db, "revoke_session", body)
            if replay is not None:
                return replay
            master = self._campaign_row(db, body["campaign"])
            child = self._session_row(db, body["campaign"], body["session"])
            if master is None or master["boot_epoch"] != self.boot_epoch or not master["generation"]:
                raise RuntimeDenied(409, "runtime_host_generation_required")
            if int(master["lease_expires_at_ms"] or 0) <= self._clock():
                raise RuntimeDenied(409, "runtime_generation_expired")
            if master["generation"] != body["generation"]:
                raise RuntimeDenied(409, "runtime_generation_stale")
            if child is None or child["generation"] != master["generation"]:
                raise RuntimeDenied(409, "runtime_session_generation_required")
            if child["policy_revision"] != revision:
                raise RuntimeDenied(409, "runtime_policy_revision_stale")
            db.execute(
                "UPDATE session_runtime SET generation=NULL, lease_expires_at_ms=NULL, policy_revision=policy_revision+1 WHERE campaign=? AND session=?",
                (body["campaign"], body["session"]),
            )
            revoked = self._session_row(db, body["campaign"], body["session"])
            response = {"status": "session_revoked", "runtime": self._snapshot_from(master, revoked).public()}
            return self._record_operation(db, "revoke_session", body, response)
