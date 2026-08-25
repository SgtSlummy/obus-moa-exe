from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

MAX_WEBHOOK_BYTES = 1_048_576


def verify_github_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature[7:], expected)


def default_webhook_database() -> Path:
    configured = os.getenv("OBUS_GITHUB_WEBHOOK_DB")
    if configured:
        return Path(configured).expanduser()
    root = os.getenv("LOCALAPPDATA") or os.getenv("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".obus"
    return base / "OBus" / "github-webhooks.sqlite3"


class GitHubWebhookStore:
    def __init__(self, database: Path | str | None = None):
        self.database = Path(database) if database is not None else default_webhook_database()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS github_webhook_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    event TEXT NOT NULL,
                    action TEXT,
                    repository TEXT,
                    sender TEXT,
                    received_at REAL NOT NULL,
                    repair_objective_id TEXT
                )
                """
            )

    def record(self, delivery_id: str, event: str, payload: dict[str, Any]) -> bool:
        repository = payload.get("repository") or {}
        sender = payload.get("sender") or {}
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO github_webhook_deliveries
                    (delivery_id, event, action, repository, sender, received_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        delivery_id,
                        event,
                        str(payload.get("action") or "")[:100],
                        str(repository.get("full_name") or "")[:200],
                        str(sender.get("login") or "")[:100],
                        time.time(),
                    ),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def attach_objective(self, delivery_id: str, objective_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE github_webhook_deliveries SET repair_objective_id = ? WHERE delivery_id = ?",
                (objective_id, delivery_id),
            )

    def status(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count, MAX(received_at) AS latest FROM github_webhook_deliveries"
            ).fetchone()
        return {
            "configured": bool(os.getenv("OBUS_GITHUB_WEBHOOK_SECRET")),
            "auto_repair": os.getenv("OBUS_GITHUB_AUTO_REPAIR", "").lower() in {"1", "true", "yes"},
            "deliveries": int(row["count"]),
            "last_delivery_at": row["latest"],
        }


def repair_request(event: str, payload: dict[str, Any]) -> str | None:
    if event == "workflow_run":
        run = payload.get("workflow_run") or {}
        if payload.get("action") == "completed" and run.get("conclusion") in {"failure", "timed_out"}:
            repository = (payload.get("repository") or {}).get("full_name", "unknown repository")
            return f"Diagnose and safely repair failed GitHub workflow {run.get('name', 'workflow')} in {repository}. Run URL: {run.get('html_url', 'unavailable')}"
    if event == "check_suite":
        suite = payload.get("check_suite") or {}
        if payload.get("action") == "completed" and suite.get("conclusion") in {"failure", "timed_out"}:
            repository = (payload.get("repository") or {}).get("full_name", "unknown repository")
            return f"Diagnose and safely repair failed GitHub check suite in {repository}."
    return None


def decode_payload(body: bytes) -> dict[str, Any]:
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("GitHub webhook payload must be an object")
    return value
