from unittest.mock import patch

import backend.main as backend


def test_auto_deliberation_enabled(client):
    enabled = client.put("/api/settings/auto-deliberation", json={"enabled": True})
    assert enabled.status_code == 200
    assert enabled.json() == {"enabled": True}
    assert client.get("/api/settings/auto-deliberation").json() == {"enabled": True}

    with patch.object(backend, "ROOM_COMPLETE", backend.offline_room_complete), \
         patch.object(backend, "room_provider_ready", return_value=True):
        resp = client.post("/api/deliberate", json={"prompt": "Design a secure multi-agent workflow"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["room_ids"]) == 2
    assert len(data["card_sets"]) == 2
    assert all(data["card_sets"])
    assert len(data["round_results"]) == 2
    assert all(item["plan"]["card_ids"] for item in data["round_results"])
    assert all(item["assignments"] for item in data["round_results"])
    assert data["thread"]["status"] == "complete"
    assert any(message["kind"] == "prompt" for message in data["thread"]["messages"])

    assert client.get(f"/api/rooms/{data['room_ids'][0]}").status_code == 200
    persisted = client.get("/api/forum/threads").json()
    assert any(thread["id"] == data["thread_id"] for thread in persisted)


def test_auto_deliberation_disabled(client):
    disabled = client.put("/api/settings/auto-deliberation", json={"enabled": False})
    assert disabled.status_code == 200
    resp = client.post("/api/deliberate", json={"prompt": "Test"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Auto deliberation is disabled"
