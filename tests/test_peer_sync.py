from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.peer_sync import PeerSyncStore, canonical_json, encode_key, is_tailscale_address


def peer_identity() -> tuple[Ed25519PrivateKey, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return private, encode_key(public)


def signed(private: Ed25519PrivateKey, peer_id: str, payload: dict, timestamp: int | None = None,
           nonce: str | None = None) -> dict:
    envelope = {"peer_id": peer_id, "timestamp": timestamp or int(time.time()),
                "nonce": nonce or uuid.uuid4().hex, "payload": payload}
    envelope["signature"] = encode_key(private.sign(canonical_json(envelope)))
    return envelope


def test_pair_verify_replay_and_revoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OBUS_PAIRING_KEY", "special-pairing-key")
    store = PeerSyncStore(tmp_path / "peers.sqlite3")
    private, public = peer_identity()
    peer = store.pair("Thor", public, "special-pairing-key")
    envelope = signed(private, peer["id"], {"objective": "repair"})
    verified = store.verify(envelope["peer_id"], envelope["timestamp"], envelope["nonce"],
                            envelope["payload"], envelope["signature"])
    assert verified["authority"] == "full"
    with pytest.raises(PermissionError, match="replayed"):
        store.verify(envelope["peer_id"], envelope["timestamp"], envelope["nonce"],
                     envelope["payload"], envelope["signature"])
    store.revoke(peer["id"])
    another = signed(private, peer["id"], {"objective": "again"})
    with pytest.raises(PermissionError, match="revoked"):
        store.verify(another["peer_id"], another["timestamp"], another["nonce"],
                     another["payload"], another["signature"])


def test_pairing_requires_configured_matching_key(tmp_path: Path, monkeypatch) -> None:
    store = PeerSyncStore(tmp_path / "peers.sqlite3")
    _, public = peer_identity()
    monkeypatch.delenv("OBUS_PAIRING_KEY", raising=False)
    with pytest.raises(PermissionError, match="disabled"):
        store.pair("Thor", public, "anything")
    monkeypatch.setenv("OBUS_PAIRING_KEY", "correct-special-key")
    with pytest.raises(PermissionError, match="invalid"):
        store.pair("Thor", public, "wrong-special-key")


def test_expired_and_tampered_signatures_are_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OBUS_PAIRING_KEY", "special-pairing-key")
    store = PeerSyncStore(tmp_path / "peers.sqlite3")
    private, public = peer_identity()
    peer = store.pair("Loki", public, "special-pairing-key")
    expired = signed(private, peer["id"], {"value": 1}, timestamp=int(time.time()) - 1000)
    with pytest.raises(PermissionError, match="expired"):
        store.verify(expired["peer_id"], expired["timestamp"], expired["nonce"],
                     expired["payload"], expired["signature"])
    valid = signed(private, peer["id"], {"value": 1})
    with pytest.raises(PermissionError, match="invalid"):
        store.verify(valid["peer_id"], valid["timestamp"], valid["nonce"],
                     {"value": 2}, valid["signature"])


def test_signed_latest_lesson_wins_with_history(tmp_path: Path) -> None:
    store = PeerSyncStore(tmp_path / "peers.sqlite3")
    older = {"id": "old", "objective": "repair", "content": "old", "hlc_physical": 10,
             "hlc_logical": 0, "device_id": "thor"}
    newer = {"id": "new", "objective": "repair", "content": "new", "hlc_physical": 11,
             "hlc_logical": 0, "device_id": "loki"}
    assert store.ingest_lesson(older, "sig-old")["accepted"] is True
    assert store.ingest_lesson(newer, "sig-new")["accepted"] is True
    assert store.ingest_lesson(older | {"id": "late-old"}, "sig-late")["accepted"] is False
    active = store.synced_lessons()
    assert len(active) == 1
    assert active[0]["id"] == "new"


def test_tailscale_address_boundary() -> None:
    assert is_tailscale_address("127.0.0.1")
    assert is_tailscale_address("100.100.10.2")
    assert is_tailscale_address("fd7a:115c:a1e0::1")
    assert not is_tailscale_address("192.168.1.10")
    assert not is_tailscale_address("8.8.8.8")
