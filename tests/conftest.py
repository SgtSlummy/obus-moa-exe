import pytest
from fastapi.testclient import TestClient

import backend.main as backend


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "STATE_FILE", tmp_path / "obus_state.json")
    return TestClient(backend.app)
