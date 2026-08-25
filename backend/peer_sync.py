"""Signed Thor peer enrollment and replay-protected learning synchronization."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def encode_key(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def decode_key(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def is_tailscale_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%")[0])
    except ValueError:
        return False
    if ip.is_loopback:
        return True
    return ip in ipaddress.ip_network("100.64.0.0/10") or ip in ipaddress.ip_network("fd7a:115c:a1e0::/48")


def protect_private_key(value: bytes) -> str:
    """Protect identity material with Windows DPAPI; portable encoding supports non-Windows CI."""
    if os.name != "nt":
        return f"portable:{encode_key(value)}"
    import ctypes
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    buffer = ctypes.create_string_buffer(value)
    input_blob = DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    output_blob = DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob), "Obus peer identity", None, None, None, 0x1, ctypes.byref(output_blob)
    ):
        raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
    try:
        protected = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)
    return f"dpapi:{encode_key(protected)}"


def unprotect_private_key(value: str) -> bytes:
    if value.startswith("portable:"):
        return decode_key(value.removeprefix("portable:"))
    if not value.startswith("dpapi:"):
        return decode_key(value)
    if os.name != "nt":
        raise OSError("DPAPI identity can only be opened by its Windows account")
    import ctypes
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    protected = decode_key(value.removeprefix("dpapi:"))
    buffer = ctypes.create_string_buffer(protected)
    input_blob = DataBlob(len(protected), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    output_blob = DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 0x1, ctypes.byref(output_blob)
    ):
        raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


class PeerSyncStore:
    def __init__(self, database: Path):
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS harness_identity (
                    id INTEGER PRIMARY KEY CHECK(id=1), device_id TEXT NOT NULL,
                    private_key TEXT NOT NULL, public_key TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS harness_peers (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, public_key TEXT NOT NULL UNIQUE,
                    authority TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                    paired_at REAL NOT NULL, last_seen_at REAL
                );
                CREATE TABLE IF NOT EXISTS harness_peer_nonces (
                    peer_id TEXT NOT NULL, nonce TEXT NOT NULL, seen_at REAL NOT NULL,
                    PRIMARY KEY(peer_id, nonce)
                );
                CREATE TABLE IF NOT EXISTS harness_synced_lessons (
                    id TEXT PRIMARY KEY, objective TEXT NOT NULL, content TEXT NOT NULL,
                    hlc_physical INTEGER NOT NULL, hlc_logical INTEGER NOT NULL,
                    device_id TEXT NOT NULL, signature TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                    received_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_synced_lesson_objective
                    ON harness_synced_lessons(objective, active, hlc_physical, hlc_logical);
            """)
        self._identity()

    def _identity(self) -> dict[str, str]:
        with self._connection() as connection:
            row = connection.execute("SELECT device_id,private_key,public_key FROM harness_identity WHERE id=1").fetchone()
            if row:
                identity = dict(row)
                if not identity["private_key"].startswith(("dpapi:", "portable:")):
                    identity["private_key"] = protect_private_key(decode_key(identity["private_key"]))
                    connection.execute("UPDATE harness_identity SET private_key=? WHERE id=1",
                                       (identity["private_key"],))
                return identity
            private = Ed25519PrivateKey.generate()
            private_raw = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                                serialization.NoEncryption())
            public_raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            identity = {"device_id": uuid.uuid4().hex, "private_key": protect_private_key(private_raw),
                        "public_key": encode_key(public_raw)}
            connection.execute("INSERT INTO harness_identity(id,device_id,private_key,public_key) VALUES(1,?,?,?)",
                               (identity["device_id"], identity["private_key"], identity["public_key"]))
            return identity

    def identity_public(self) -> dict[str, str]:
        identity = self._identity()
        return {"device_id": identity["device_id"], "public_key": identity["public_key"]}

    def sign(self, payload: Any) -> str:
        private = Ed25519PrivateKey.from_private_bytes(unprotect_private_key(self._identity()["private_key"]))
        return encode_key(private.sign(canonical_json(payload)))

    def pair(self, name: str, public_key: str, supplied_key: str) -> dict[str, Any]:
        expected = os.environ.get("OBUS_PAIRING_KEY", "")
        if not expected:
            raise PermissionError("pairing is disabled until OBUS_PAIRING_KEY is configured")
        if not hmac.compare_digest(supplied_key.encode(), expected.encode()):
            raise PermissionError("invalid pairing key")
        Ed25519PublicKey.from_public_bytes(decode_key(public_key))
        peer_id = uuid.uuid4().hex
        with self._connection() as connection:
            existing = connection.execute("SELECT id FROM harness_peers WHERE public_key=?", (public_key,)).fetchone()
            if existing:
                raise ValueError("public key is already paired")
            connection.execute(
                "INSERT INTO harness_peers(id,name,public_key,authority,paired_at) VALUES(?,?,?,?,?)",
                (peer_id, name, public_key, "full", time.time()),
            )
        return self.get_peer(peer_id)

    def get_peer(self, peer_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM harness_peers WHERE id=?", (peer_id,)).fetchone()
        if row is None:
            raise KeyError(peer_id)
        return dict(row) | {"revoked": bool(row["revoked"])}

    def peers(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM harness_peers ORDER BY paired_at DESC").fetchall()
        return [dict(row) | {"revoked": bool(row["revoked"])} for row in rows]

    def revoke(self, peer_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute("UPDATE harness_peers SET revoked=1 WHERE id=?", (peer_id,))
            if cursor.rowcount == 0:
                raise KeyError(peer_id)
        return self.get_peer(peer_id)

    def verify(self, peer_id: str, timestamp: int, nonce: str, payload: Any, signature: str,
               max_age_seconds: int = 300) -> dict[str, Any]:
        peer = self.get_peer(peer_id)
        if peer["revoked"]:
            raise PermissionError("peer is revoked")
        now = int(time.time())
        if abs(now - timestamp) > max_age_seconds:
            raise PermissionError("signed request expired")
        message = {"peer_id": peer_id, "timestamp": timestamp, "nonce": nonce, "payload": payload}
        public = Ed25519PublicKey.from_public_bytes(decode_key(peer["public_key"]))
        try:
            public.verify(decode_key(signature), canonical_json(message))
        except Exception as exc:
            raise PermissionError("invalid peer signature") from exc
        with self._connection() as connection:
            connection.execute("DELETE FROM harness_peer_nonces WHERE seen_at<?", (time.time() - max_age_seconds,))
            try:
                connection.execute("INSERT INTO harness_peer_nonces(peer_id,nonce,seen_at) VALUES(?,?,?)",
                                   (peer_id, nonce, time.time()))
            except sqlite3.IntegrityError as exc:
                raise PermissionError("replayed signed request") from exc
            connection.execute("UPDATE harness_peers SET last_seen_at=? WHERE id=?", (time.time(), peer_id))
        return peer

    def signed_envelope(self, payload: Any) -> dict[str, Any]:
        identity = self._identity()
        envelope = {"peer_id": identity["device_id"], "timestamp": int(time.time()),
                    "nonce": uuid.uuid4().hex, "payload": payload}
        envelope["signature"] = self.sign(envelope)
        return envelope

    def ingest_lesson(self, lesson: dict[str, Any], signature: str) -> dict[str, Any]:
        required = {"id", "objective", "content", "hlc_physical", "hlc_logical", "device_id"}
        if not required.issubset(lesson):
            raise ValueError("lesson payload is incomplete")
        objective = str(lesson["objective"])
        ordering = (int(lesson["hlc_physical"]), int(lesson["hlc_logical"]), str(lesson["device_id"]))
        with self._connection() as connection:
            current = connection.execute(
                "SELECT hlc_physical,hlc_logical,device_id FROM harness_synced_lessons "
                "WHERE objective=? AND active=1 ORDER BY hlc_physical DESC,hlc_logical DESC,device_id DESC LIMIT 1",
                (objective,),
            ).fetchone()
            if current and ordering <= (current["hlc_physical"], current["hlc_logical"], current["device_id"]):
                return {"accepted": False, "reason": "superseded"}
            connection.execute("UPDATE harness_synced_lessons SET active=0 WHERE objective=?", (objective,))
            connection.execute(
                "INSERT OR REPLACE INTO harness_synced_lessons(id,objective,content,hlc_physical,hlc_logical,"
                "device_id,signature,active,received_at) VALUES(?,?,?,?,?,?,?,1,?)",
                (lesson["id"], objective, lesson["content"], ordering[0], ordering[1], ordering[2],
                 signature, time.time()),
            )
        return {"accepted": True, "lesson_id": lesson["id"]}

    def synced_lessons(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM harness_synced_lessons WHERE active=1 ORDER BY received_at DESC"
            ).fetchall()
        return [dict(row) | {"active": bool(row["active"])} for row in rows]
