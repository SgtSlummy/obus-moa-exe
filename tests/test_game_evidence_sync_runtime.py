"""Evidence synchronization survives AI-off without granting inference permission."""
from contextlib import closing
from dataclasses import replace
import sqlite3
from types import SimpleNamespace
import uuid

import pytest

from backend.game_evidence import EvidenceDenied, EvidenceSnapshot, initialize_schema, resolve_evidence, save_snapshot
from backend.game_runtime import GameRuntimeAuthority, RuntimeDenied


class Clock:
    def __init__(self):
        self.now = 1_700_000_000_000

    def __call__(self):
        return self.now


def register(authority, session="campaign", generation=None):
    return authority.register({"contract": "raph-obus-game-runtime-v1", "campaign": "camp-1", "session": session,
        "generation": generation or str(uuid.uuid4()), "expectedBootEpoch": authority.boot_epoch,
        "expectedGeneration": None, "opId": str(uuid.uuid4()), "leaseSeconds": 30})["runtime"]


def policy_body(state, enabled):
    return {"contract": "raph-obus-game-runtime-v1", "campaign": "camp-1", "session": "campaign",
        "expectedGeneration": state.child["generation"], "expectedBootEpoch": state.child["bootEpoch"],
        "expectedSessionPolicyRevision": state.child["sessionPolicyRevision"], "opId": str(uuid.uuid4()),
        "policy": {"enabled": enabled, "mode": "local", "codex": False, "exportable": False}}


def change_policy(state, enabled):
    result = state.authority.patch_policy(policy_body(state, enabled))["runtime"]
    state.child["sessionPolicyRevision"] = result["sessionPolicyRevision"]
    return result


def guarded(state, kind="evidence", **updates):
    expected = {"boot_epoch": state.child["bootEpoch"], "generation": state.child["generation"],
                "policy_revision": state.child["sessionPolicyRevision"], **updates}
    return getattr(state.authority, f"{kind}_transaction")("camp-1", "session-1", **expected)


def updates(root):
    with closing(sqlite3.connect(root / "game.sqlite")) as db:
        return db.execute("SELECT id,body FROM evidence_updates ORDER BY id").fetchall()


def runtime_dump(root):
    with closing(sqlite3.connect(root / "runtime.sqlite")) as db:
        return tuple(db.iterdump())


@pytest.fixture
def state(tmp_path):
    clock = Clock()
    authority = GameRuntimeAuthority(tmp_path, clock=clock)
    master = register(authority)
    child = register(authority, "session-1", master["generation"])
    with closing(sqlite3.connect(tmp_path / "game.sqlite")) as db, db:
        db.execute("CREATE TABLE evidence_updates(id TEXT PRIMARY KEY,body TEXT NOT NULL)")
        initialize_schema(db)
    return SimpleNamespace(root=tmp_path, clock=clock, authority=authority, child=child)


def evidence(state, revision=1, external=True):
    return EvidenceSnapshot.model_validate({
        "contract": "raph-obus-game-evidence-v1", "campaign": "camp-1", "session": "session-1", "revision": revision,
        "runtime": {"contract": "raph-obus-game-runtime-v1", "bootEpoch": state.child["bootEpoch"],
                    "generation": state.child["generation"], "sessionPolicyRevision": state.child["sessionPolicyRevision"]},
        "participants": [{"user": "player-1", "capture": True, "external": external, "captureEpoch": 0, "externalEpoch": 0 if external else 1}],
        "sources": [{"ref": "entry-1", "revision": 1, "audience": "party", "owner": "", "text": "Fixture recording.",
                     "provenance": "chronicle:entry-1", "deleted": False, "derivesFrom": [],
                     "contributors": [{"user": "player-1", "captureEpoch": 0, "externalEpoch": 0, "exportableAtCapture": True}]}],
    })


def test_consent_withdrawal_syncs_while_ai_off_but_inference_receipt_is_denied(state):
    with guarded(state) as db:
        save_snapshot(db, evidence(state))
    change_policy(state, False)
    before = runtime_dump(state.root)
    with guarded(state) as db:
        assert save_snapshot(db, evidence(state, revision=2, external=False))["status"] == "saved"
    assert runtime_dump(state.root) == before, "evidence guard must never write runtime rows"
    with guarded(state) as db:
        with pytest.raises(EvidenceDenied, match="evidence_external_consent_required"):
            resolve_evidence(db, "camp-1", "session-1", "player-1", "player", 2, [{"ref": "entry-1", "revision": 1}], external=True)
        assert resolve_evidence(db, "camp-1", "session-1", "player-1", "player", 2, [{"ref": "entry-1", "revision": 1}])["sources"]
    with pytest.raises(RuntimeDenied, match="game_ai_disabled"):
        with guarded(state, "receipt"):
            pytest.fail("sync permission must not grant inference receipt permission")
    assert updates(state.root) == []


@pytest.mark.parametrize("kind", ["evidence", "receipt"])
def test_both_guards_keep_game_only_commit_semantics(state, kind):
    before = runtime_dump(state.root)
    with guarded(state, kind) as db:
        db.execute("INSERT INTO evidence_updates VALUES ('new','accepted')")
        assert updates(state.root) == []
    assert updates(state.root) == [("new", "accepted")]
    assert runtime_dump(state.root) == before


@pytest.mark.parametrize("invalid", ["lease", "boot", "generation", "revision", "restart", "revoked"])
def test_stale_evidence_fence_fails_before_body(state, invalid):
    expected = {}
    if invalid == "lease":
        state.clock.now += 30_000
    elif invalid == "boot":
        expected["boot_epoch"] = str(uuid.uuid4())
    elif invalid == "generation":
        expected["generation"] = str(uuid.uuid4())
    elif invalid == "revision":
        expected["policy_revision"] = 1
    elif invalid == "restart":
        state.authority = GameRuntimeAuthority(state.root, clock=state.clock)
    else:
        state.authority.revoke_session({"contract": "raph-obus-game-runtime-v1", "campaign": "camp-1", "session": "session-1",
            "generation": state.child["generation"], "expectedBootEpoch": state.child["bootEpoch"],
            "expectedSessionPolicyRevision": state.child["sessionPolicyRevision"], "opId": str(uuid.uuid4())})
    with pytest.raises(RuntimeDenied) as denied:
        with guarded(state, **expected):
            pytest.fail("stale authority must not reach synchronization")
    assert denied.value.status == 409
    assert denied.value.code in {"runtime_host_generation_required", "runtime_fence_stale"}
    assert updates(state.root) == []


@pytest.mark.parametrize("invalid", ["lease", "boot", "generation", "revision"])
def test_final_fence_validation_rolls_back_evidence(state, monkeypatch, invalid):
    original = state.authority._snapshot_from
    calls = []

    def observed_snapshot(*args):
        current = original(*args)
        calls.append(current)
        # Database writers cannot make these changes while the lock is held;
        # fault injection independently proves final fence validation is active.
        if len(calls) > 1 and invalid != "lease":
            if invalid == "boot":
                return replace(current, boot_epoch=str(uuid.uuid4()))
            if invalid == "generation":
                return replace(current, generation=str(uuid.uuid4()))
            return replace(current, policy_revision=current.policy_revision + 1)
        return current

    monkeypatch.setattr(state.authority, "_snapshot_from", observed_snapshot)
    with pytest.raises(RuntimeDenied) as denied:
        with guarded(state) as db:
            db.execute("INSERT INTO evidence_updates VALUES ('new','accepted')")
            if invalid == "lease":
                state.clock.now += 30_000
    assert len(calls) == 2
    assert denied.value.code in {"runtime_host_generation_required", "runtime_fence_stale"}
    assert updates(state.root) == []


def test_body_failure_rolls_back_and_releases_runtime_writer(state):
    before = runtime_dump(state.root)
    with pytest.raises(ValueError, match="fixture failure"):
        with guarded(state) as db:
            db.execute("INSERT INTO evidence_updates VALUES ('new','accepted')")
            raise ValueError("fixture failure")
    assert updates(state.root) == []
    assert runtime_dump(state.root) == before
    assert change_policy(state, False)["policy"]["enabled"] is False
    with guarded(state) as db:
        db.execute("INSERT INTO evidence_updates VALUES ('recovery','accepted')")
    assert updates(state.root) == [("recovery", "accepted")]


@pytest.mark.parametrize("early", ["commit", "with_db", "executescript", "rollback", "savepoint", "pragma"])
def test_evidence_body_cannot_take_transaction_ownership(state, early):
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with guarded(state) as db:
            db.execute("INSERT INTO evidence_updates VALUES ('new','accepted')")
            if early == "commit":
                db.commit()
            elif early == "with_db":
                with db:
                    pass
            elif early == "executescript":
                db.executescript("SELECT 1;")
            elif early == "rollback":
                db.rollback()
            elif early == "savepoint":
                db.execute("SAVEPOINT bypass")
            else:
                db.execute("PRAGMA journal_mode")
    assert updates(state.root) == []
    change_policy(state, False)


@pytest.mark.parametrize("mode", ["delete", "wal"])
def test_policy_flip_and_game_writer_are_ordered_after_evidence_commit(state, mode):
    for name in ("game.sqlite", "runtime.sqlite"):
        with closing(sqlite3.connect(state.root / name)) as db:
            assert db.execute(f"PRAGMA journal_mode={mode}").fetchone()[0] == mode
    peer = GameRuntimeAuthority(state.root, clock=state.clock)
    peer.boot_epoch = state.authority.boot_epoch

    def no_wait_connection():
        connection = sqlite3.connect(state.root / "runtime.sqlite", timeout=0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    peer._connect = no_wait_connection
    with guarded(state) as db:
        db.execute("INSERT INTO evidence_updates VALUES ('new','accepted')")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            peer.patch_policy(policy_body(state, False))
        with closing(sqlite3.connect(state.root / "game.sqlite", timeout=0, isolation_level=None)) as game_peer:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                game_peer.execute("INSERT INTO evidence_updates VALUES ('other','too early')")
        assert updates(state.root) == []
    assert updates(state.root) == [("new", "accepted")]
    changed = peer.patch_policy(policy_body(state, False))["runtime"]
    assert changed["policy"]["enabled"] is False
    assert updates(state.root) == [("new", "accepted")]


@pytest.mark.parametrize("mode,codex,exportable", [("paid", 0, 0), ("local", 1, 0), ("local", 0, 1)])
def test_evidence_guard_does_not_expand_provider_policy(state, mode, codex, exportable):
    with closing(sqlite3.connect(state.root / "runtime.sqlite")) as db, db:
        db.execute("UPDATE campaign_runtime SET mode=?,codex=?,exportable=?", (mode, codex, exportable))
    for kind in ("evidence", "receipt"):
        with pytest.raises(RuntimeDenied, match="runtime_policy_not_local_only"):
            with guarded(state, kind):
                pytest.fail("neither guard permits nonlocal policy")
    assert updates(state.root) == []
