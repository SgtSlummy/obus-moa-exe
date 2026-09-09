"""Temp SQLite fixtures; no providers, live files, credentials or services."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from types import SimpleNamespace
import uuid

import pytest

from backend import game_dispatch as ledger
from backend.game_runtime import GameRuntimeAuthority, RuntimeDenied, RUNTIME_CONTRACT


@contextmanager
def transaction(path):
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def register(authority, session="campaign", generation=None, expected=None):
    return authority.register({"contract": RUNTIME_CONTRACT, "campaign": "camp", "session": session,
        "generation": generation or str(uuid.uuid4()), "expectedBootEpoch": authority.boot_epoch,
        "expectedGeneration": expected, "opId": str(uuid.uuid4()), "leaseSeconds": 30})["runtime"]


def policy(state, *, enabled=True, mode="local-free", exportable=True, codex=False):
    current = state.authority.snapshot("camp", "campaign")
    return state.authority.patch_policy({"contract": RUNTIME_CONTRACT, "campaign": "camp", "session": "campaign",
        "expectedGeneration": current.generation, "expectedBootEpoch": current.boot_epoch,
        "expectedSessionPolicyRevision": current.policy_revision, "opId": str(uuid.uuid4()),
        "policy": {"enabled": enabled, "mode": mode, "codex": codex, "exportable": exportable}})["runtime"]


def fence(snapshot):
    return {"boot_epoch": snapshot.boot_epoch, "generation": snapshot.generation,
            "policy_revision": snapshot.policy_revision}


@pytest.fixture
def state(tmp_path):
    clock = SimpleNamespace(now=1_800_000_000_000)
    authority = GameRuntimeAuthority(tmp_path, clock=lambda: clock.now)
    master = register(authority)
    register(authority, "session", master["generation"])
    path = tmp_path / "game.sqlite"
    ledger.prepare_dispatch_store(path)
    with transaction(path) as db:
        db.execute("CREATE TABLE receipts(id TEXT PRIMARY KEY,body TEXT NOT NULL)")
    result = SimpleNamespace(root=tmp_path, path=path, authority=authority, clock=clock)
    policy(result)
    result.snapshot = authority.snapshot("camp", "session")
    return result


def metadata(state, **overrides):
    value = {"campaign": "camp", "session": "session", "owner": "host", "request_id": "request",
        "fingerprint": "a" * 64, "task": "summary", **fence(state.snapshot),
        "evidence_revision": 3, "evidence_digest": "b" * 64, "route_id": "approved-free",
        "route_digest": "c" * 64, "provider": "verified-provider", "model": "free-model",
        "now_ms": state.clock.now}
    value.update(overrides)
    return value


def queue(state, **overrides):
    with state.authority.dispatch_transaction("camp", "session", **fence(state.snapshot)) as (db, snapshot):
        assert snapshot.mode == "local-free"
        return ledger.enqueue(db, **metadata(state, **overrides))


def claim(state, attempt):
    with state.authority.dispatch_transaction("camp", "session", **fence(state.snapshot)) as (db, _):
        return ledger.mark_dispatched(db, attempt["attemptId"], fingerprint="a" * 64, now_ms=state.clock.now)


def provenance(**overrides):
    value = {"provider": "verified-provider", "model": "free-model", "route_id": "approved-free",
             "gateway": "openrouter", "destination": "external", "cost": "zero"}
    value.update(overrides)
    return value


def recent(state, **kwargs):
    db = sqlite3.connect(state.path)
    try:
        return ledger.recent(db, campaign="camp", **kwargs)
    finally:
        db.close()


def test_host_free_policy_propagates_to_child_and_only_external_guard_requires_export(state):
    snapshot = state.authority.require_dispatch("camp", "session", **fence(state.snapshot), external=True)
    assert snapshot.mode == "local-free" and snapshot.exportable and not snapshot.codex
    with pytest.raises(FrozenInstanceError):
        snapshot.mode = "local"
    policy(state, exportable=False)
    snapshot = state.authority.snapshot("camp", "session")
    assert state.authority.require_dispatch("camp", "session", **fence(snapshot)) == snapshot
    with pytest.raises(RuntimeDenied, match="runtime_external_disabled"):
        state.authority.require_dispatch("camp", "session", **fence(snapshot), external=True)
    # Local STT/receipt and consent synchronization remain valid under this mode.
    with state.authority.receipt_transaction("camp", "session", **fence(snapshot)) as db:
        db.execute("INSERT INTO receipts VALUES('local','ok')")
    with state.authority.evidence_transaction("camp", "session", **fence(snapshot)) as db:
        assert db.execute("SELECT body FROM receipts").fetchone()[0] == "ok"


@pytest.mark.parametrize("mode,exportable,codex", [("local", True, False), ("paid", True, False), ("local-free", True, True)])
def test_host_cannot_enable_paid_codex_or_contradict_local(state, mode, exportable, codex):
    with pytest.raises(RuntimeDenied, match="runtime_policy_not_local_only"):
        policy(state, mode=mode, exportable=exportable, codex=codex)


def test_snapshot_cannot_mix_master_policy_with_new_child_revision(state, monkeypatch):
    # WAL lets the controlled writer commit between the two reads. The reader's
    # explicit transaction must still observe one immutable database snapshot.
    db = sqlite3.connect(state.root / "runtime.sqlite")
    db.execute("PRAGMA journal_mode=WAL")
    db.close()
    peer = GameRuntimeAuthority(state.root, clock=lambda: state.clock.now)
    peer.boot_epoch = state.authority.boot_epoch
    original = state.authority._campaign_row
    changed = False
    def master_then_change(connection, campaign):
        nonlocal changed
        row = original(connection, campaign)
        if not changed:
            changed = True
            policy(SimpleNamespace(authority=peer), enabled=False)
        return row
    monkeypatch.setattr(state.authority, "_campaign_row", master_then_change)
    snapshot = state.authority.snapshot("camp", "session")
    assert snapshot == state.snapshot
    fresh = state.authority.snapshot("camp", "session")
    assert fresh.enabled is False and fresh.policy_revision == snapshot.policy_revision + 1


def test_disable_keeps_evidence_sync_but_denies_dispatch_and_receipts(state):
    policy(state, enabled=False)
    snapshot = state.authority.snapshot("camp", "session")
    with state.authority.evidence_transaction("camp", "session", **fence(snapshot)) as db:
        db.execute("INSERT INTO receipts VALUES('consent','withdrawn')")
    for guard in (state.authority.dispatch_transaction, state.authority.receipt_transaction):
        with pytest.raises(RuntimeDenied, match="game_ai_disabled"):
            with guard("camp", "session", **fence(snapshot)):
                pytest.fail("disabled AI must not dispatch or save a result")


def test_enqueue_is_idempotent_per_route_and_fingerprint_global(state):
    first = queue(state)
    assert queue(state) == first
    with pytest.raises(ledger.DispatchDenied, match="dispatch_request_conflict"):
        queue(state, fingerprint="d" * 64, route_digest="e" * 64)
    with pytest.raises(ledger.DispatchDenied, match="dispatch_attempt_conflict"):
        queue(state, evidence_revision=4)
    assert recent(state)["counts"]["queued"] == 1


def test_only_one_concurrent_claim_can_commit(state):
    attempt = queue(state)
    barrier = threading.Barrier(2)
    def worker():
        barrier.wait(timeout=3)
        try:
            return claim(state, attempt)["status"]
        except ledger.DispatchDenied as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert sorted(results) == ["dispatch_attempt_not_queued", "dispatched"]
    assert recent(state)["counts"]["dispatched"] == 1


def test_prequeued_different_routes_cannot_both_dispatch(state):
    first = queue(state)
    second = queue(state, route_digest="d" * 64, route_id="another-free")
    barrier = threading.Barrier(2)
    def worker(attempt):
        barrier.wait(timeout=3)
        try:
            return claim(state, attempt)["status"]
        except ledger.DispatchDenied as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, (first, second)))
    assert sorted(results) == ["dispatch_request_already_sent", "dispatched"]
    assert recent(state)["counts"]["dispatched"] == 1


def test_failed_route_can_advance_but_uncertain_route_cannot(state):
    first = queue(state)
    claim(state, first)
    with transaction(state.path) as db:
        ledger.finish(db, first["attemptId"], fingerprint="a" * 64, outcome="failed", now_ms=state.clock.now)
    second = queue(state, route_digest="d" * 64, route_id="another-free")
    assert second["attemptId"] != first["attemptId"]
    claim(state, second)
    with transaction(state.path) as db:
        ledger.finish(db, second["attemptId"], fingerprint="a" * 64, outcome="uncertain", now_ms=state.clock.now)
    assert queue(state, route_digest="d" * 64, route_id="another-free")["status"] == "uncertain"
    with pytest.raises(ledger.DispatchDenied, match="dispatch_request_already_sent"):
        queue(state, route_digest="e" * 64)


def test_disable_before_claim_cancels_durably_without_send(state):
    attempt = queue(state)
    policy(state, enabled=False)
    with pytest.raises(RuntimeDenied, match="runtime_fence_stale"):
        claim(state, attempt)
    row = recent(state)["jobs"][0]
    assert row["status"] == "cancelled" and row["dispatchedAtMs"] is None
    assert row["cancelReason"] == "policy_changed"


def test_policy_writer_cannot_slip_between_claim_validation_and_commit(state):
    attempt = queue(state)
    # A second authority instance shares only durable files and the process boot
    # identifier. No Python object lock can serialize this writer with the guard.
    peer = GameRuntimeAuthority(state.root, clock=lambda: state.clock.now)
    peer.boot_epoch = state.authority.boot_epoch
    entered = threading.Event()
    finished = threading.Event()
    def disable():
        entered.set()
        policy(SimpleNamespace(authority=peer), enabled=False)
        finished.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with state.authority.dispatch_transaction("camp", "session", **fence(state.snapshot)) as (db, _):
            ledger.mark_dispatched(db, attempt["attemptId"], fingerprint="a" * 64, now_ms=state.clock.now)
            future = pool.submit(disable)
            assert entered.wait(2)
            assert not finished.wait(0.1)
        future.result(timeout=5)
    row = recent(state)["jobs"][0]
    assert row["status"] == "dispatched" and row["cancelRequested"] is True
    assert row["dispatchedAtMs"] is not None
    with transaction(state.path) as db:
        with pytest.raises(ledger.DispatchDenied, match="dispatch_result_not_authorized"):
            ledger.finish(db, attempt["attemptId"], fingerprint="a" * 64, outcome="completed", now_ms=state.clock.now, provenance=provenance())
        ledger.finish(db, attempt["attemptId"], fingerprint="a" * 64, outcome="discarded", now_ms=state.clock.now)


def test_provider_runs_outside_guard_and_can_disable_during_work(state):
    attempt = queue(state)
    claim(state, attempt)
    def fake_provider():
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(lambda: policy(state, enabled=False)).result(timeout=5)
        return "discard this late result"
    assert fake_provider()
    with pytest.raises(RuntimeDenied):
        with state.authority.receipt_transaction("camp", "session", **fence(state.snapshot)) as db:
            db.execute("INSERT INTO receipts VALUES('late','must not persist')")
    assert recent(state)["jobs"][0]["cancelRequested"]


def test_generation_restart_marks_inflight_uncertain_and_cancels_queue(state):
    first = queue(state)
    claim(state, first)
    queue(state, request_id="queued-request")
    restarted = GameRuntimeAuthority(state.root, clock=lambda: state.clock.now)
    fresh = register(restarted)
    assert fresh["policy"] == {"enabled": True, "mode": "local", "codex": False, "exportable": False}
    counts = recent(state)["counts"]
    assert counts["uncertain"] == 1 and counts["cancelled"] == 1
    with pytest.raises(RuntimeDenied):
        claim(state, first)


def test_child_revoke_cancels_only_target_session(state):
    queue(state)
    register(state.authority, "other", state.snapshot.generation)
    other = state.authority.snapshot("camp", "other")
    with state.authority.dispatch_transaction("camp", "other", **fence(other)) as (db, _):
        ledger.enqueue(db, **metadata(state, session="other", policy_revision=other.policy_revision))
    state.authority.revoke_session({"contract": RUNTIME_CONTRACT, "campaign": "camp", "session": "session",
        "generation": state.snapshot.generation, "expectedBootEpoch": state.snapshot.boot_epoch,
        "expectedSessionPolicyRevision": state.snapshot.policy_revision, "opId": str(uuid.uuid4())})
    assert recent(state, session="session")["counts"]["cancelled"] == 1
    assert recent(state, session="other")["counts"]["queued"] == 1


@pytest.mark.parametrize("when", ["before", "after"])
def test_expired_lease_never_commits_claim(state, when):
    attempt = queue(state)
    if when == "before":
        state.clock.now += 30_001
    with pytest.raises(RuntimeDenied, match="runtime_host_generation_required"):
        with state.authority.dispatch_transaction("camp", "session", **fence(state.snapshot)) as (db, _):
            ledger.mark_dispatched(db, attempt["attemptId"], fingerprint="a" * 64, now_ms=state.clock.now)
            if when == "after":
                state.clock.now += 30_001
    assert recent(state)["counts"]["queued"] == 1


@pytest.mark.parametrize("action", ["raise", "commit", "context", "executescript"])
def test_failed_guard_rolls_back_and_releases_writer_lock(state, action):
    attempt = queue(state)
    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        with state.authority.dispatch_transaction("camp", "session", **fence(state.snapshot)) as (db, _):
            ledger.mark_dispatched(db, attempt["attemptId"], fingerprint="a" * 64, now_ms=state.clock.now)
            if action == "raise":
                raise RuntimeError("controlled failure")
            if action == "commit":
                db.commit()
            elif action == "context":
                with db:
                    pass
            elif action == "executescript":
                db.executescript("SELECT 1;")
    assert recent(state)["counts"]["queued"] == 1
    assert claim(state, attempt)["status"] == "dispatched"


def test_result_and_ledger_completion_roll_back_together(state):
    attempt = queue(state)
    claim(state, attempt)
    with pytest.raises(RuntimeError):
        with state.authority.receipt_transaction("camp", "session", **fence(state.snapshot)) as db:
            ledger.finish(db, attempt["attemptId"], fingerprint="a" * 64, outcome="completed", now_ms=state.clock.now, provenance=provenance())
            db.execute("INSERT INTO receipts VALUES('result','authorized output')")
            raise RuntimeError("before durable receipt")
    assert recent(state)["counts"]["dispatched"] == 1
    with state.authority.receipt_transaction("camp", "session", **fence(state.snapshot)) as db:
        assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0
        ledger.finish(db, attempt["attemptId"], fingerprint="a" * 64, outcome="completed", now_ms=state.clock.now, provenance=provenance())
        db.execute("INSERT INTO receipts VALUES('result','authorized output')")
    assert recent(state)["counts"]["completed"] == 1


@pytest.mark.parametrize("bad", [{"prompt": "secret"}, {"provider": "different"}, {"cost": "paid"}, {"destination": "local"}])
def test_provenance_rejects_unexpected_text_or_destination(state, bad):
    attempt = queue(state)
    claim(state, attempt)
    with transaction(state.path) as db:
        with pytest.raises(ledger.DispatchDenied):
            ledger.finish(db, attempt["attemptId"], fingerprint="a" * 64, outcome="completed", now_ms=state.clock.now, provenance=provenance(**bad))
    assert recent(state)["counts"]["dispatched"] == 1


def test_public_recent_is_bounded_and_excludes_private_metadata(state):
    for index in range(3):
        queue(state, request_id=f"private-request-{index}", owner="secret-owner")
    result = recent(state, limit=2)
    assert len(result["jobs"]) == 2 and result["counts"]["queued"] == 3
    encoded = json.dumps(result)
    for private in ("secret-owner", "private-request", "boot_epoch", "generation", "evidence_digest", "evidence_revision", "fingerprint", "approved-free"):
        assert private not in encoded
    with pytest.raises(ledger.DispatchDenied):
        recent(state, limit=51)


def test_ledger_requires_owned_transaction(state):
    db = sqlite3.connect(state.path, isolation_level=None)
    try:
        with pytest.raises(ledger.DispatchDenied, match="dispatch_transaction_required"):
            ledger.enqueue(db, **metadata(state))
    finally:
        db.close()


@pytest.mark.parametrize("journal", ["delete", "wal"])
def test_preflight_backs_up_existing_database_before_migration(tmp_path, journal):
    path = tmp_path / "game.sqlite"
    db = sqlite3.connect(path)
    db.execute(f"PRAGMA journal_mode={journal}")
    db.execute("CREATE TABLE legacy(id INTEGER PRIMARY KEY,text TEXT)")
    db.execute("INSERT INTO legacy VALUES(1,'preserved game state')")
    db.commit()
    db.close()
    result = ledger.prepare_dispatch_store(path)
    assert result["backedUp"] and result["status"] == "prepared"
    backup = Path(result["backupPath"])
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == result["backupSha256"]
    saved = sqlite3.connect(backup)
    current = sqlite3.connect(path)
    try:
        assert saved.execute("SELECT text FROM legacy").fetchone()[0] == "preserved game state"
        assert not ledger.schema_ready(saved)
        assert ledger.schema_ready(current)
        assert current.execute("PRAGMA journal_mode").fetchone()[0] == journal
    finally:
        saved.close()
        current.close()
    assert ledger.prepare_dispatch_store(path) == {"status": "ready", "version": 1}
    assert len(list((tmp_path / "backups").glob("*.sqlite"))) == 1


def test_concurrent_preparers_create_only_one_backup(tmp_path):
    path = tmp_path / "game.sqlite"
    with transaction(path) as db:
        db.execute("CREATE TABLE legacy(value TEXT)")
    barrier = threading.Barrier(2)
    def prepare():
        barrier.wait(timeout=3)
        return ledger.prepare_dispatch_store(path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: prepare(), range(2)))
    assert sorted(result["status"] for result in results) == ["prepared", "ready"]
    assert len(list((tmp_path / "backups").glob("*.sqlite"))) == 1


def test_failed_backup_prevents_schema_mutation(tmp_path, monkeypatch):
    path = tmp_path / "game.sqlite"
    with transaction(path) as db:
        db.execute("CREATE TABLE legacy(value TEXT)")
        db.execute("INSERT INTO legacy VALUES('safe')")
    original = Path.open
    def denied(self, *args, **kwargs):
        if self.name.startswith("game-before-dispatch"):
            raise PermissionError("fixture backup denied")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(PermissionError):
        ledger.prepare_dispatch_store(path)
    with transaction(path) as db:
        assert not ledger.schema_ready(db)
        assert db.execute("SELECT value FROM legacy").fetchone()[0] == "safe"
        with pytest.raises(ledger.DispatchDenied, match="dispatch_backup_required"):
            ledger.initialize_schema(db)


def test_public_status_missing_path_does_not_create_directories_or_database(tmp_path):
    path = tmp_path / "absent" / "game.sqlite"
    result = ledger.public_recent(path, "camp", "session")
    assert result["status"] == "uninitialized" and result["available"] is False
    assert result["jobs"] == [] and not any(result["counts"].values())
    assert not path.parent.exists()


def test_public_status_legacy_store_is_unchanged_and_not_migrated(tmp_path):
    path = tmp_path / "game.sqlite"
    with transaction(path) as db:
        db.execute("CREATE TABLE legacy(value TEXT)")
        db.execute("INSERT INTO legacy VALUES('untouched')")
    before = path.read_bytes()
    assert ledger.public_recent(path, "camp")["status"] == "uninitialized"
    assert path.read_bytes() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["game.sqlite"]


def test_public_status_uses_encoded_readonly_uri_and_filters_scope(state, monkeypatch):
    first = queue(state)
    queue(state, session="session", request_id="another")
    observed = []
    original = ledger.sqlite3.connect
    def connect(database, *args, **kwargs):
        observed.append((database, kwargs))
        return original(database, *args, **kwargs)
    monkeypatch.setattr(ledger.sqlite3, "connect", connect)
    result = ledger.public_recent(state.path, "camp", "session", 1)
    assert result["status"] == "ready" and result["available"] is True
    assert len(result["jobs"]) == 1 and result["counts"]["queued"] == 2
    assert ledger.public_recent(state.path, "other-campaign")["jobs"] == []
    assert ledger.public_recent(state.path, "camp", "other-session")["jobs"] == []
    assert all(value[0] == state.path.resolve().as_uri() + "?mode=ro" for value in observed)
    assert all(value[1]["uri"] is True and value[1]["timeout"] <= 0.25 for value in observed)


def test_public_status_path_with_spaces_and_hash_has_no_uri_ambiguity(tmp_path):
    directory = tmp_path / "game data #1"
    path = directory / "game #1.sqlite"
    ledger.prepare_dispatch_store(path)
    assert ledger.public_recent(path, "camp")["status"] == "ready"
    assert sorted(item.name for item in directory.iterdir()) == ["game #1.sqlite"]


def test_public_status_dormant_wal_is_unavailable_without_new_sidecars(tmp_path):
    path = tmp_path / "game.sqlite"
    ledger.prepare_dispatch_store(path)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.close()
    before = sorted(item.name for item in tmp_path.iterdir())
    assert before == ["game.sqlite"]
    result = ledger.public_recent(path, "camp")
    assert result["status"] == "unavailable" and result["available"] is False
    assert sorted(item.name for item in tmp_path.iterdir()) == before


def test_public_status_active_wal_reads_committed_snapshot(state):
    attempt = queue(state)
    writer = sqlite3.connect(state.path, isolation_level=None)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE dispatch_attempts SET status='cancelled' WHERE attempt_id=?", (attempt["attemptId"],))
        old = ledger.public_recent(state.path, "camp", "session")
        assert old["status"] == "ready" and old["counts"]["queued"] == 1
        assert old["jobs"][0]["status"] == "queued"
        writer.execute("COMMIT")
        new = ledger.public_recent(state.path, "camp", "session")
        assert new["status"] == "ready" and new["counts"]["cancelled"] == 1
        assert new["jobs"][0]["status"] == "cancelled"
    finally:
        writer.close()


def test_public_status_nested_write_attempt_is_denied(state, monkeypatch):
    def accidental_write(db, **kwargs):
        db.execute("CREATE TABLE forbidden(value TEXT)")
        pytest.fail("read-only URI must prevent writes")
    monkeypatch.setattr(ledger, "recent", accidental_write)
    result = ledger.public_recent(state.path, "camp", "session")
    assert result["status"] == "unavailable" and result["available"] is False
    with transaction(state.path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='forbidden'").fetchone()


@pytest.mark.parametrize("kind", ["corrupt", "incomplete", "unsupported", "busy"])
def test_public_status_never_claims_health_on_storage_errors(tmp_path, kind):
    path = tmp_path / "game.sqlite"
    held = None
    if kind == "corrupt":
        path.write_bytes(b"not a SQLite database")
    else:
        ledger.prepare_dispatch_store(path)
        if kind == "incomplete":
            with transaction(path) as db:
                db.execute("DROP TABLE dispatch_schema")
        elif kind == "unsupported":
            with transaction(path) as db:
                db.execute("UPDATE dispatch_schema SET version=999")
        else:
            held = sqlite3.connect(path, isolation_level=None)
            held.execute("BEGIN EXCLUSIVE")
    try:
        result = ledger.public_recent(path, "camp")
        assert result["status"] == "unavailable" and result["available"] is False
        assert result["jobs"] == [] and not any(result["counts"].values())
        assert str(path) not in json.dumps(result)
    finally:
        if held is not None:
            held.close()


@pytest.mark.parametrize("limit", [0, 51, True, "1"])
def test_public_status_invalid_limit_does_not_touch_path(tmp_path, limit):
    path = tmp_path / "absent" / "game.sqlite"
    with pytest.raises(ledger.DispatchDenied, match="dispatch_limit_invalid"):
        ledger.public_recent(path, "camp", limit=limit)
    assert not path.parent.exists()


def test_policy_writes_do_not_migrate_existing_store(tmp_path):
    authority = GameRuntimeAuthority(tmp_path)
    register(authority)
    path = tmp_path / "game.sqlite"
    with transaction(path) as db:
        db.execute("CREATE TABLE legacy(value TEXT)")
    policy(SimpleNamespace(authority=authority), enabled=False)
    with transaction(path) as db:
        assert not ledger.schema_ready(db)
    assert not (tmp_path / "backups").exists()
