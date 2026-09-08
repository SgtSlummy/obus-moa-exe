"""Receipt commits are fenced across connections/processes, without locking inference."""
from __future__ import annotations

import json
import multiprocessing
import sqlite3
import uuid
from contextlib import closing, contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.game_runtime import GameRuntimeAuthority, RuntimeDenied


class Clock:
    def __init__(self, now=1_700_000_000_000):
        self.now = now

    def __call__(self):
        return self.now


def registration(authority, *, session="campaign", generation=None, expected=None, lease=30):
    return {
        "contract": "raph-obus-game-runtime-v1",
        "campaign": "camp-1",
        "session": session,
        "generation": generation or str(uuid.uuid4()),
        "expectedBootEpoch": authority.boot_epoch,
        "expectedGeneration": expected,
        "opId": str(uuid.uuid4()),
        "leaseSeconds": lease,
    }


def disable_body(master):
    return {
        "contract": "raph-obus-game-runtime-v1",
        "campaign": "camp-1",
        "session": "campaign",
        "expectedGeneration": master["generation"],
        "expectedBootEpoch": master["bootEpoch"],
        "expectedSessionPolicyRevision": master["sessionPolicyRevision"],
        "opId": str(uuid.uuid4()),
        "policy": {"enabled": False, "mode": "local", "codex": False, "exportable": False},
    }


def fence(runtime):
    return {
        "boot_epoch": runtime["bootEpoch"],
        "generation": runtime["generation"],
        "policy_revision": runtime["sessionPolicyRevision"],
    }


def peer_authority(root, clock, boot_epoch):
    # A separate worker using the authenticated host epoch, not a host restart.
    peer = GameRuntimeAuthority(root, clock=clock)
    peer.boot_epoch = boot_epoch

    def connect_without_waiting():
        db = sqlite3.connect(root / "runtime.sqlite", timeout=0, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    peer._connect = connect_without_waiting
    return peer


def receipt_rows(root):
    with closing(sqlite3.connect(root / "game.sqlite")) as db, db:
        return db.execute("SELECT id, body FROM receipts ORDER BY id").fetchall()


@pytest.fixture
def runtime(tmp_path):
    clock = Clock()
    authority = GameRuntimeAuthority(tmp_path, clock=clock)
    master = authority.register(registration(authority))["runtime"]
    child = authority.register(registration(authority, session="session-1", generation=master["generation"]))["runtime"]
    with closing(sqlite3.connect(tmp_path / "game.sqlite")) as db, db:
        db.execute("CREATE TABLE receipts(id TEXT PRIMARY KEY, body TEXT NOT NULL)")
    return SimpleNamespace(root=tmp_path, clock=clock, authority=authority, master=master, child=child)


def guard(runtime, **overrides):
    expected = {**fence(runtime.child), **overrides}
    return runtime.authority.receipt_transaction("camp-1", "session-1", **expected)


def test_committed_policy_change_prevents_receipt(runtime):
    peer = peer_authority(runtime.root, runtime.clock, runtime.authority.boot_epoch)
    changed = peer.patch_policy(disable_body(runtime.master))["runtime"]
    with pytest.raises(RuntimeDenied) as denied:
        with guard(runtime):
            pytest.fail("a stale fence must never reach the receipt body")
    assert denied.value.status == 409
    assert denied.value.code == "runtime_fence_stale"
    with pytest.raises(RuntimeDenied) as disabled:
        with guard(runtime, policy_revision=changed["sessionPolicyRevision"]):
            pytest.fail("a matching disabled policy must never reach the receipt body")
    assert disabled.value.code == "game_ai_disabled"
    assert receipt_rows(runtime.root) == []


def policy_writer(root, boot_epoch, now, body, pipe):
    """Real separate-process contention, with no timing-only completion assertion."""
    try:
        root = Path(root)
        peer = peer_authority(root, Clock(now), boot_epoch)
        pipe.send(("ready",))
        while pipe.recv() == "write":
            try:
                peer.patch_policy(body)
                pipe.send(("committed", receipt_rows(root)))
            except sqlite3.OperationalError as exc:
                pipe.send(("locked" if "locked" in str(exc).lower() else "error", str(exc)))
    except BaseException as exc:
        pipe.send(("error", repr(exc)))
    finally:
        pipe.close()


def receive(pipe):
    assert pipe.poll(15), "owned fixture worker did not reach its controlled barrier"
    result = pipe.recv()
    assert result[0] != "error", result
    return result


@pytest.mark.parametrize("runtime_journal,game_journal", [("delete", "delete"), ("delete", "wal"), ("wal", "delete"), ("wal", "wal")])
def test_policy_writer_cannot_cross_validation_and_durable_commit(runtime, runtime_journal, game_journal):
    for name, mode in (("runtime.sqlite", runtime_journal), ("game.sqlite", game_journal)):
        with closing(sqlite3.connect(runtime.root / name)) as db, db:
            assert db.execute(f"PRAGMA journal_mode={mode}").fetchone()[0] == mode
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=policy_writer, args=(str(runtime.root), runtime.authority.boot_epoch,
                               runtime.clock.now, disable_body(runtime.master), child))
    process.start()
    child.close()
    try:
        assert receive(parent) == ("ready",)
        with guard(runtime) as db:
            # Entry has validated the fence. The other process actually attempts
            # a policy write at both barriers and SQLite rejects it as locked.
            parent.send("write")
            assert receive(parent)[0] == "locked"
            db.execute("INSERT INTO receipts VALUES (?, ?)", ("new", "accepted"))
            assert receipt_rows(runtime.root) == []
            parent.send("write")
            assert receive(parent)[0] == "locked"
        parent.send("write")
        assert receive(parent) == ("committed", [("new", "accepted")])
    finally:
        if process.is_alive():
            parent.send("stop")
        process.join(15)
        if process.is_alive():
            process.terminate()  # Only this test's owned fixture worker.
            process.join(5)
        parent.close()
    assert process.exitcode == 0


@pytest.mark.parametrize("operation", ["insert", "normalize"])
def test_body_failure_rolls_back_receipt_and_releases_writer(runtime, operation):
    if operation == "normalize":
        with closing(sqlite3.connect(runtime.root / "game.sqlite")) as db, db:
            db.execute("INSERT INTO receipts VALUES ('legacy', 'old transcript')")
    peer = peer_authority(runtime.root, runtime.clock, runtime.authority.boot_epoch)
    with pytest.raises(ValueError, match="fixture body failure"):
        with guard(runtime) as db:
            if operation == "insert":
                db.execute("INSERT INTO receipts VALUES ('new', 'accepted')")
            else:
                db.execute("UPDATE receipts SET body='receipt only' WHERE id='legacy'")
            raise ValueError("fixture body failure")
    assert receipt_rows(runtime.root) == ([] if operation == "insert" else [("legacy", "old transcript")])
    assert peer.patch_policy(disable_body(runtime.master))["runtime"]["policy"]["enabled"] is False


@pytest.mark.parametrize("early_commit", ["commit", "with_connection", "executescript", "pragma", "savepoint", "attach"])
def test_body_cannot_commit_early_or_change_transaction_settings(runtime, early_commit):
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with guard(runtime) as db:
            db.execute("INSERT INTO receipts VALUES ('new', 'accepted')")
            if early_commit == "commit":
                db.commit()
            elif early_commit == "with_connection":
                with db:
                    pass
            elif early_commit == "executescript":
                db.executescript("SELECT 1;")
            elif early_commit == "pragma":
                db.execute("PRAGMA journal_mode")
            elif early_commit == "savepoint":
                db.execute("SAVEPOINT early")
            else:
                db.execute("ATTACH DATABASE ':memory:' AS other")
    assert receipt_rows(runtime.root) == []
    peer = peer_authority(runtime.root, runtime.clock, runtime.authority.boot_epoch)
    peer.patch_policy(disable_body(runtime.master))


def test_lease_expiring_in_receipt_body_rolls_back(runtime):
    with pytest.raises(RuntimeDenied) as denied:
        with guard(runtime) as db:
            db.execute("INSERT INTO receipts VALUES ('new', 'accepted')")
            runtime.clock.now += 30_000
    assert denied.value.code == "runtime_host_generation_required"
    assert receipt_rows(runtime.root) == []


@pytest.mark.parametrize("change", ["boot", "generation", "revision", "restart", "revoke", "new_generation"])
def test_receipt_rejects_stale_host_and_session_fences(runtime, change):
    overrides = {}
    if change == "boot":
        overrides["boot_epoch"] = str(uuid.uuid4())
    elif change == "generation":
        overrides["generation"] = str(uuid.uuid4())
    elif change == "revision":
        overrides["policy_revision"] = runtime.child["sessionPolicyRevision"] + 1
    elif change == "restart":
        runtime.authority = GameRuntimeAuthority(runtime.root, clock=runtime.clock)
    elif change == "revoke":
        runtime.authority.revoke_session({
            "contract": "raph-obus-game-runtime-v1", "campaign": "camp-1", "session": "session-1",
            "generation": runtime.child["generation"], "expectedBootEpoch": runtime.child["bootEpoch"],
            "expectedSessionPolicyRevision": runtime.child["sessionPolicyRevision"], "opId": str(uuid.uuid4()),
        })
    else:
        runtime.authority.register(registration(runtime.authority, expected=runtime.master["generation"]))
    with pytest.raises(RuntimeDenied) as denied:
        with guard(runtime, **overrides):
            pytest.fail("stale work must never reach the receipt body")
    assert denied.value.status == 409
    assert denied.value.code in {"runtime_host_generation_required", "runtime_fence_stale"}
    assert receipt_rows(runtime.root) == []


def test_missing_game_database_fails_before_runtime_lock(runtime):
    (runtime.root / "game.sqlite").unlink()
    with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
        with guard(runtime):
            pytest.fail("schema initialization is a caller precondition")
    assert not (runtime.root / "game.sqlite").exists()
    peer = peer_authority(runtime.root, runtime.clock, runtime.authority.boot_epoch)
    peer.patch_policy(disable_body(runtime.master))


@pytest.fixture
def game(runtime, monkeypatch):
    from backend import game_agent as agent

    monkeypatch.setattr(agent, "ROOT", runtime.root)
    monkeypatch.setattr(agent, "RUNTIME", runtime.authority)
    with agent.database():
        pass
    calls = []
    transaction = runtime.authority.receipt_transaction

    @contextmanager
    def recorded_transaction(*args, **kwargs):
        calls.append((args, kwargs))
        with transaction(*args, **kwargs) as db:
            yield db

    monkeypatch.setattr(runtime.authority, "receipt_transaction", recorded_transaction)
    runtime.agent = agent
    runtime.guard_calls = calls
    runtime.fence_model = agent.RuntimeFence(
        contract=agent.RUNTIME_CONTRACT,
        bootEpoch=runtime.child["bootEpoch"],
        generation=runtime.child["generation"],
        sessionPolicyRevision=runtime.child["sessionPolicyRevision"],
    )
    runtime.scope = {"campaign": "camp-1", "owner": "host", "role": "host"}
    return runtime


def job_count(game, table):
    assert table in {"game_jobs", "stt_jobs"}
    with game.agent.database() as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def stt_envelope(game, request_id="stt-receipt"):
    return {
        "contract": game.agent.STT_CONTRACT, "scope": game.scope,
        "session": "session-1", "requestId": request_id,
        "runtime": game.fence_model.model_dump(), "mime_type": "audio/wav",
    }


def test_stt_uses_guard_and_commits_receipt_without_transcript(game, monkeypatch):
    monkeypatch.setattr(game.agent, "_transcribe_game_audio", lambda *_args, **_kwargs: ("synthetic speech", "fixture-model"))
    result = game.agent._transcribe_scoped_stt(stt_envelope(game), b"fixture-audio")
    assert result["result"]["text"] == "synthetic speech"
    assert len(game.guard_calls) == 1
    assert job_count(game, "stt_jobs") == 1
    with game.agent.database() as db:
        saved = db.execute("SELECT body FROM stt_jobs").fetchone()[0]
    assert "synthetic speech" not in saved


def test_stt_policy_writer_completes_during_decode_and_stale_receipt_is_rejected(game, monkeypatch):
    from fastapi import HTTPException

    peer = peer_authority(game.root, game.clock, game.authority.boot_epoch)
    decoded = []

    def transcribe(*_args, **_kwargs):
        assert game.guard_calls == [], "decoding must precede the receipt guard"
        peer.patch_policy(disable_body(game.master))
        decoded.append(True)
        return "synthetic speech", "fixture-model"

    monkeypatch.setattr(game.agent, "_transcribe_game_audio", transcribe)
    with pytest.raises(HTTPException) as denied:
        game.agent._transcribe_scoped_stt(stt_envelope(game), b"fixture-audio")
    assert denied.value.status_code == 409
    assert decoded == [True]
    assert job_count(game, "stt_jobs") == 0


def local_job(game, request_id="text-receipt"):
    return game.agent.Job(
        contract=game.agent.CONTRACT,
        scope=game.agent.Scope(**game.scope),
        session="session-1", requestId=request_id, task="narration",
        instructions="Use authorized facts", evidence={"question": "lantern"},
        policy=game.agent.Policy(mode="local", codex=False, exportable=False, namespace="camp-1"),
        runtime=game.fence_model,
    )


def run_local_job(game, local):
    key = {"id": "key-local-ollama", "provider": "ollama", "connected": True,
           "verified": True, "model": "fixture:latest", "base_url": "http://127.0.0.1:11434"}
    return game.agent.run_job(local_job(game), get_keys=lambda: [key], local=local)


def test_text_uses_guard_after_inference_and_commits_once(game):
    generated = []

    def local(_key, _prompt, _maximum):
        assert game.guard_calls == [], "generation must precede the receipt guard"
        generated.append(True)
        return "The lantern glows."

    response = run_local_job(game, local)
    assert "The lantern glows." in json.dumps(response)
    assert generated == [True]
    assert len(game.guard_calls) == 1
    assert job_count(game, "game_jobs") == 1


def test_text_policy_writer_completes_during_inference_and_stale_receipt_is_rejected(game):
    from fastapi import HTTPException

    peer = peer_authority(game.root, game.clock, game.authority.boot_epoch)
    generated = []

    def local(_key, _prompt, _maximum):
        assert game.guard_calls == [], "generation must precede the receipt guard"
        # timeout=0 on the independent connection makes any broad runtime lock
        # fail immediately instead of hiding behind a blocking test timeout.
        peer.patch_policy(disable_body(game.master))
        generated.append(True)
        return "The lantern glows."

    with pytest.raises(HTTPException) as denied:
        run_local_job(game, local)
    assert denied.value.status_code == 409
    assert generated == [True]
    assert job_count(game, "game_jobs") == 0


def seed_legacy_stt(game, monkeypatch):
    monkeypatch.setattr(game.agent, "_transcribe_game_audio", lambda *_args, **_kwargs: ("synthetic speech", "fixture-model"))
    envelope = stt_envelope(game)
    game.agent._transcribe_scoped_stt(envelope, b"fixture-audio")
    legacy = json.dumps({"status": "completed", "result": {"text": "legacy secret"},
                         "receipt": {"engine": "old-engine", "model": "old-model"}})
    with game.agent.database() as db:
        db.execute("UPDATE stt_jobs SET body=?", (legacy,))
    game.guard_calls.clear()

    def never_decode(*_args, **_kwargs):
        pytest.fail("legacy receipt replay must not decode audio again")

    monkeypatch.setattr(game.agent, "_transcribe_game_audio", never_decode)
    return envelope, legacy


def test_legacy_stt_normalization_uses_guard_and_removes_saved_transcript(game, monkeypatch):
    envelope, _legacy = seed_legacy_stt(game, monkeypatch)
    replay = game.agent._transcribe_scoped_stt(envelope, b"fixture-audio")
    assert replay["status"] == "completed_receipt_only"
    assert replay["receipt"]["engine"] == "old-engine"
    assert replay["receipt"]["model"] == "old-model"
    assert "legacy secret" not in json.dumps(replay)
    assert len(game.guard_calls) == 1
    with game.agent.database() as db:
        saved = db.execute("SELECT body FROM stt_jobs").fetchone()[0]
    assert json.loads(saved) == replay
    assert "legacy secret" not in saved


def test_policy_change_before_legacy_normalization_prevents_update(game, monkeypatch):
    from fastapi import HTTPException

    envelope, legacy = seed_legacy_stt(game, monkeypatch)
    peer = peer_authority(game.root, game.clock, game.authority.boot_epoch)
    transaction = game.authority.receipt_transaction

    @contextmanager
    def change_policy_before_guard(*args, **kwargs):
        peer.patch_policy(disable_body(game.master))
        with transaction(*args, **kwargs) as db:
            yield db

    monkeypatch.setattr(game.authority, "receipt_transaction", change_policy_before_guard)
    with pytest.raises(HTTPException) as denied:
        game.agent._transcribe_scoped_stt(envelope, b"fixture-audio")
    assert denied.value.status_code == 409
    assert len(game.guard_calls) == 1
    with game.agent.database() as db:
        assert db.execute("SELECT body FROM stt_jobs").fetchone()[0] == legacy
