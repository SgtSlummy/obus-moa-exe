import hashlib
import hmac
import tempfile
import threading
import uuid
from pathlib import Path

import pytest

from backend.game_runtime import GameRuntimeAuthority, RuntimeDenied, canonical_json


class Clock:
    def __init__(self, now=1_700_000_000_000):
        self.now = now

    def __call__(self):
        return self.now


def register_body(authority, *, session="session-1", generation=None, expected=None, op_id=None, lease=30):
    return {
        "contract": "raph-obus-game-runtime-v1",
        "campaign": "camp-1",
        "session": session,
        "generation": generation or str(uuid.uuid4()),
        "expectedBootEpoch": authority.boot_epoch,
        "expectedGeneration": expected,
        "opId": op_id or str(uuid.uuid4()),
        "leaseSeconds": lease,
    }


def renewal_body(authority, runtime, *, session="session-1", lease=30):
    return {
        "contract": "raph-obus-game-runtime-v1",
        "campaign": "camp-1",
        "session": session,
        "generation": runtime["generation"],
        "expectedBootEpoch": runtime["bootEpoch"],
        "expectedSessionPolicyRevision": runtime["sessionPolicyRevision"],
        "opId": str(uuid.uuid4()),
        "leaseSeconds": lease,
    }


def signed(authority, method, path, body, nonce):
    timestamp = str(authority._clock() // 1000)
    signature = hmac.new(authority.host_key(), authority._signed_bytes(method, path, timestamp, nonce, body), hashlib.sha256).hexdigest()
    return {"X-Obus-Game-Host-Timestamp": timestamp, "X-Obus-Game-Host-Nonce": nonce, "X-Obus-Game-Host-Signature": signature}


def test_hmac_reference_vector_and_nonce_replay():
    clock = Clock()
    with tempfile.TemporaryDirectory() as directory:
        authority = GameRuntimeAuthority(Path(directory), clock=clock)
        authority._token_path.write_text("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f", encoding="ascii")
        body = {
            "campaign": "camp-1",
            "contract": "raph-obus-game-runtime-v1",
            "expectedBootEpoch": "11111111-1111-4111-8111-111111111111",
            "expectedGeneration": None,
            "generation": "22222222-2222-4222-8222-222222222222",
            "leaseSeconds": 30,
            "opId": "33333333-3333-4333-8333-333333333333",
            "session": "session-1",
        }
        nonce = "a" * 64
        headers = signed(authority, "PUT", "/api/game/runtime/host-generation", body, nonce)
        assert hashlib.sha256(canonical_json(body)).hexdigest() == "76c174f7ce7accce9028c8d1ae1c47df9cf44450387200908fbba61410e54c64"
        assert headers["X-Obus-Game-Host-Signature"] == "62460488d134d384526d339e3670801c5e480fed7ed6c45dc6f32bfe0d0c9598"
        authority.verify_host("PUT", "/api/game/runtime/host-generation", body, headers)
        with pytest.raises(RuntimeDenied, match="host_nonce_replayed"):
            authority.verify_host("PUT", "/api/game/runtime/host-generation", body, headers)


def test_campaign_master_policy_fences_all_existing_and_future_sessions():
    clock = Clock()
    with tempfile.TemporaryDirectory() as directory:
        authority = GameRuntimeAuthority(Path(directory), clock=clock)
        master = authority.register(register_body(authority, session="campaign"))["runtime"]
        child = authority.register(register_body(authority, session="session-2", generation=master["generation"], expected=None))["runtime"]
        assert child["generation"] == master["generation"]
        policy = {
            "contract": "raph-obus-game-runtime-v1",
            "campaign": "camp-1",
            "session": "campaign",
            "expectedGeneration": master["generation"],
            "expectedBootEpoch": master["bootEpoch"],
            "expectedSessionPolicyRevision": master["sessionPolicyRevision"],
            "opId": str(uuid.uuid4()),
            "policy": {"enabled": False, "mode": "local", "codex": False, "exportable": False},
        }
        changed = authority.patch_policy(policy)["runtime"]
        child_after = authority.snapshot("camp-1", "session-2").public()
        assert changed["sessionPolicyRevision"] == master["sessionPolicyRevision"] + 1
        assert child_after["sessionPolicyRevision"] == child["sessionPolicyRevision"] + 1
        assert child_after["policy"]["enabled"] is False
        # A child may join or renew under a disabled master, but it cannot change
        # that policy and remains unable to dispatch.
        future = authority.register(register_body(authority, session="session-3", generation=master["generation"], expected=None))["runtime"]
        assert future["policy"]["enabled"] is False
        assert future["policy"]["codex"] is False


def test_master_replacement_invalidates_other_sessions_and_resets_safe_defaults():
    clock = Clock()
    with tempfile.TemporaryDirectory() as directory:
        authority = GameRuntimeAuthority(Path(directory), clock=clock)
        first = authority.register(register_body(authority, session="campaign"))["runtime"]
        authority.register(register_body(authority, session="session-2", generation=first["generation"], expected=None))
        authority.patch_policy({
            "contract": "raph-obus-game-runtime-v1", "campaign": "camp-1", "session": "campaign",
            "expectedGeneration": first["generation"], "expectedBootEpoch": first["bootEpoch"],
            "expectedSessionPolicyRevision": first["sessionPolicyRevision"], "opId": str(uuid.uuid4()),
            "policy": {"enabled": False, "mode": "local", "codex": False, "exportable": False},
        })
        replacement = authority.register(register_body(authority, session="campaign", generation=str(uuid.uuid4()), expected=first["generation"]))["runtime"]
        assert replacement["generation"] != first["generation"]
        assert replacement["policy"] == {"enabled": True, "mode": "local", "codex": False, "exportable": False}
        assert authority.snapshot("camp-1", "session-2").generation is None
        with pytest.raises(RuntimeDenied, match="runtime_generation_stale"):
            authority.register(register_body(authority, session="session-2", generation=first["generation"], expected=None))


def test_master_expiry_denies_child_renewal_until_fresh_master_registration():
    clock = Clock()
    with tempfile.TemporaryDirectory() as directory:
        authority = GameRuntimeAuthority(Path(directory), clock=clock)
        master = authority.register(register_body(authority, session="campaign", lease=5))["runtime"]
        child = authority.register(register_body(authority, session="session-2", generation=master["generation"], expected=None, lease=30))["runtime"]
        clock.now += 5_001
        assert authority.snapshot("camp-1", "campaign").generation is None
        assert authority.snapshot("camp-1", "session-2").generation is None
        with pytest.raises(RuntimeDenied, match="runtime_generation_expired"):
            authority.renew(renewal_body(authority, child, session="session-2"))
        fresh = authority.register(register_body(authority, session="campaign", generation=str(uuid.uuid4()), expected=None))["runtime"]
        assert fresh["generation"] is not None
        assert authority.snapshot("camp-1", "session-2").generation is None


def test_session_revoke_immediately_invalidates_only_that_child_fence():
    clock = Clock()
    with tempfile.TemporaryDirectory() as directory:
        authority = GameRuntimeAuthority(Path(directory), clock=clock)
        master = authority.register(register_body(authority, session="campaign"))["runtime"]
        child = authority.register(register_body(authority, session="session-2", generation=master["generation"], expected=None))["runtime"]
        revoke = {
            "contract": "raph-obus-game-runtime-v1", "campaign": "camp-1", "session": "session-2",
            "generation": child["generation"], "expectedBootEpoch": child["bootEpoch"],
            "expectedSessionPolicyRevision": child["sessionPolicyRevision"], "opId": str(uuid.uuid4()),
        }
        receipt = authority.revoke_session(revoke)
        assert receipt["status"] == "session_revoked"
        assert authority.snapshot("camp-1", "session-2").generation is None
        assert authority.snapshot("camp-1", "campaign").generation == master["generation"]
        assert authority.revoke_session(revoke) == receipt


def test_concurrent_master_compare_and_swap_has_one_winner():
    clock = Clock()
    with tempfile.TemporaryDirectory() as directory:
        authority = GameRuntimeAuthority(Path(directory), clock=clock)
        initial = authority.register(register_body(authority, session="campaign"))["runtime"]
        barrier = threading.Barrier(3)
        outcomes = []

        def replace():
            body = register_body(authority, session="campaign", generation=str(uuid.uuid4()), expected=initial["generation"])
            barrier.wait()
            try:
                outcomes.append(("ok", authority.register(body)["runtime"]["generation"]))
            except RuntimeDenied as error:
                outcomes.append(("denied", error.code))

        workers = [threading.Thread(target=replace) for _ in range(2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join()
        assert [kind for kind, _ in outcomes].count("ok") == 1
        assert [kind for kind, _ in outcomes].count("denied") == 1


def test_master_release_permits_immediate_restart_and_stale_close_cannot_revoke_it(tmp_path):
    authority = GameRuntimeAuthority(tmp_path, clock=Clock())
    first = authority.register(register_body(authority, session="campaign"))["runtime"]
    authority.register(register_body(authority, session="child", generation=first["generation"]))
    release = renewal_body(authority, first, session="campaign")
    del release["leaseSeconds"]
    for field, bad in [("expectedBootEpoch", str(uuid.uuid4())), ("generation", str(uuid.uuid4())), ("expectedSessionPolicyRevision", first["sessionPolicyRevision"] + 1)]:
        with pytest.raises(RuntimeDenied):
            authority.release_host({**release, field: bad, "opId": str(uuid.uuid4())})
        assert authority.snapshot("camp-1", "campaign").generation == first["generation"]
    receipt = authority.release_host(release)
    assert receipt["status"] == "host_released"
    assert receipt["runtime"]["generation"] is None
    assert receipt["runtime"]["leaseExpiresAtMs"] is None
    assert receipt["runtime"]["sessionPolicyRevision"] == first["sessionPolicyRevision"] + 1
    assert authority.snapshot("camp-1", "child").generation is None
    second = authority.register(register_body(authority, session="campaign"))["runtime"]
    assert second["generation"] != first["generation"]
    assert authority.release_host(release) == receipt  # exact retry has no new mutation
    with pytest.raises(RuntimeDenied, match="runtime_generation_stale"):
        authority.release_host({**release, "opId": str(uuid.uuid4())})
    assert authority.snapshot("camp-1", "campaign").generation == second["generation"]


def test_child_cannot_release_master(tmp_path):
    authority = GameRuntimeAuthority(tmp_path, clock=Clock())
    first = authority.register(register_body(authority, session="campaign"))["runtime"]
    body = renewal_body(authority, first, session="child")
    del body["leaseSeconds"]
    with pytest.raises(RuntimeDenied, match="runtime_master_session_required"):
        authority.release_host(body)
    assert authority.snapshot("camp-1", "campaign").generation == first["generation"]
