from __future__ import annotations

import hashlib
import hmac

import pytest

from backend.game_runtime import GameRuntimeAuthority, RuntimeDenied


def body(authority, generation, expected=None, op="33333333-3333-4333-8333-333333333333"):
    return {"contract":"raph-obus-game-runtime-v1","campaign":"campaign-1","session":"session-1","generation":generation,"expectedBootEpoch":authority.boot_epoch,"expectedGeneration":expected,"opId":op,"leaseSeconds":30}


def headers(authority, payload, nonce="00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"):
    timestamp = str(authority.clock() // 1000)
    message = authority._signed_bytes("PUT", "/api/game/runtime/host-generation", timestamp, nonce, payload)
    return {"X-Obus-Game-Host-Timestamp":timestamp,"X-Obus-Game-Host-Nonce":nonce,"X-Obus-Game-Host-Signature":hmac.new(authority.host_key(), message, hashlib.sha256).hexdigest()}


def test_register_is_durable_idempotent_and_fences_stale_generation(tmp_path):
    authority = GameRuntimeAuthority(tmp_path, clock=lambda: 1_735_689_600_000)
    first = body(authority, "22222222-2222-4222-8222-222222222222")
    authority.verify_host("PUT", "/api/game/runtime/host-generation", first, headers(authority, first))
    result = authority.register(first)
    assert result["generation"] == first["generation"]
    with pytest.raises(RuntimeDenied) as replay:
        authority.verify_host("PUT", "/api/game/runtime/host-generation", first, headers(authority, first))
    assert replay.value.code == "host_signature_replayed"
    replacement = body(authority, "44444444-4444-4444-8444-444444444444", first["generation"], "55555555-5555-4555-8555-555555555555")
    authority.verify_host("PUT", "/api/game/runtime/host-generation", replacement, headers(authority, replacement, "111122223333444455556666777788889999aaaabbbbccccddddeeeeffff0000"))
    authority.register(replacement)
    stale = body(authority, "66666666-6666-4666-8666-666666666666", first["generation"], "77777777-7777-4777-8777-777777777777")
    authority.verify_host("PUT", "/api/game/runtime/host-generation", stale, headers(authority, stale, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
    with pytest.raises(RuntimeDenied) as denied:
        authority.register(stale)
    assert denied.value.code == "runtime_generation_conflict"
