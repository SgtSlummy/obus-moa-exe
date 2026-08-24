import pytest
from fastapi.testclient import TestClient
from backend.main import app, save_state

@pytest.fixture
def client():
    # Reset state before each test
    save_state({})
    return TestClient(app)

def test_auto_deliberation_enabled(client):
    client.put("/api/settings/auto-deliberation", json={"enabled": True})
    resp = client.post("/api/deliberate", json={"prompt": "Test prompt"})
    assert resp.status_code == 200
    data = resp.json()
    assert "room_id" in data and "thread_id" in data
    r = client.get(f"/api/rooms/{data['room_id']}")
    assert r.status_code == 200

def test_auto_deliberation_disabled(client):
    client.put("/api/settings/auto-deliberation", json={"enabled": False})
    resp = client.post("/api/deliberate", json={"prompt": "Test"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Auto deliberation is disabled"
