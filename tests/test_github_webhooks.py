from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import backend.github_webhook_api as webhook_api
from backend.github_webhooks import GitHubWebhookStore, repair_request, verify_github_signature
from backend.main import app


def signed_headers(secret: str, body: bytes, delivery: str = "delivery-1", event: str = "push") -> dict[str, str]:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {
        "X-Hub-Signature-256": f"sha256={digest}",
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": event,
        "Content-Type": "application/json",
    }


def test_signature_verification_is_constant_contract():
    body = b'{"ok":true}'
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()

    assert verify_github_signature("secret", body, signature) is True
    assert verify_github_signature("wrong", body, signature) is False
    assert verify_github_signature("secret", body, None) is False


def test_store_rejects_replayed_delivery_without_storing_payload(tmp_path):
    store = GitHubWebhookStore(tmp_path / "webhooks.sqlite3")
    payload = {"action": "completed", "repository": {"full_name": "owner/repo"}, "secret": "discard-me"}

    assert store.record("same-id", "workflow_run", payload) is True
    assert store.record("same-id", "workflow_run", payload) is False
    assert store.status()["deliveries"] == 1
    assert b"discard-me" not in (tmp_path / "webhooks.sqlite3").read_bytes()


def test_repair_request_only_accepts_completed_failures():
    failed = {
        "action": "completed",
        "repository": {"full_name": "owner/repo"},
        "workflow_run": {"conclusion": "failure", "name": "CI", "html_url": "https://example.invalid/run"},
    }
    successful = {**failed, "workflow_run": {**failed["workflow_run"], "conclusion": "success"}}

    assert "safely repair" in repair_request("workflow_run", failed)
    assert repair_request("workflow_run", successful) is None
    assert repair_request("push", failed) is None


def test_webhook_accepts_signed_delivery_and_rejects_replay(monkeypatch, tmp_path):
    secret = "webhook-test-secret"
    monkeypatch.setenv("OBUS_GITHUB_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("OBUS_GITHUB_AUTO_REPAIR", "false")
    monkeypatch.setattr(webhook_api, "_store", GitHubWebhookStore(tmp_path / "api.sqlite3"))
    body = json.dumps({"repository": {"full_name": "owner/repo"}, "sender": {"login": "octocat"}}).encode()
    client = TestClient(app)

    first = client.post("/api/integrations/github-app/webhook", content=body, headers=signed_headers(secret, body))
    replay = client.post("/api/integrations/github-app/webhook", content=body, headers=signed_headers(secret, body))

    assert first.status_code == 202
    assert first.json()["duplicate"] is False
    assert replay.status_code == 202
    assert replay.json()["duplicate"] is True


def test_webhook_rejects_invalid_signature(monkeypatch, tmp_path):
    monkeypatch.setenv("OBUS_GITHUB_WEBHOOK_SECRET", "correct")
    monkeypatch.setattr(webhook_api, "_store", GitHubWebhookStore(tmp_path / "api.sqlite3"))
    body = b"{}"

    response = TestClient(app).post(
        "/api/integrations/github-app/webhook", content=body, headers=signed_headers("wrong", body)
    )

    assert response.status_code == 401
