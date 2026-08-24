from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.nvidia_warp_runtime as runtime
import backend.main as backend


def fake_warp(*, cuda_available=True, devices=("cpu", "cuda:0")):
    return SimpleNamespace(
        config=SimpleNamespace(version="test-warp"),
        is_cuda_available=lambda: cuda_available,
        get_devices=lambda: [SimpleNamespace(alias=device) for device in devices],
    )


def test_status_is_honest_when_warp_is_unavailable(monkeypatch):
    monkeypatch.setattr(runtime, "_load_warp", lambda: None)

    result = runtime.status("cuda:0")

    assert result["available"] is False
    assert result["backend"] == "nvidia-warp"
    assert result["requested_device"] == "cuda:0"
    assert result["selected_device"] == "cpu"
    assert result["fallback"] is True
    assert result["llm_inference_acceleration"] is False


def test_select_device_falls_back_to_cpu_when_cuda_is_unavailable(monkeypatch):
    monkeypatch.setattr(runtime, "_load_warp", lambda: fake_warp(cuda_available=False, devices=("cpu",)))

    result = runtime.select_device("cuda:0")

    assert result == {
        "requested_device": "cuda:0",
        "selected_device": "cpu",
        "fallback": True,
        "fallback_reason": "CUDA device unavailable",
    }


def test_select_device_uses_cuda_when_requested_and_available(monkeypatch):
    monkeypatch.setattr(runtime, "_load_warp", lambda: fake_warp())

    result = runtime.select_device("cuda:0")

    assert result == {
        "requested_device": "cuda:0",
        "selected_device": "cuda:0",
        "fallback": False,
        "fallback_reason": None,
    }


def test_status_reports_warp_device_inventory(monkeypatch):
    monkeypatch.setattr(runtime, "_load_warp", lambda: fake_warp())

    result = runtime.status("cuda:0")

    assert result["available"] is True
    assert result["version"] == "test-warp"
    assert result["devices"] == ["cpu", "cuda:0"]
    assert result["selected_device"] == "cuda:0"


def test_warmup_returns_unavailable_without_warp(monkeypatch):
    monkeypatch.setattr(runtime, "_load_warp", lambda: None)

    result = runtime.warmup("cuda:0")

    assert result["ok"] is False
    assert result["available"] is False
    assert result["selected_device"] == "cpu"


def test_nvidia_warp_status_endpoint_is_secret_free():
    client = TestClient(backend.app)
    with patch.object(backend.nvidia_warp_runtime, "status", return_value={"available": True, "backend": "nvidia-warp", "selected_device": "cuda:0"}):
        response = client.get("/api/integrations/nvidia-warp")

    assert response.status_code == 200
    assert response.json()["backend"] == "nvidia-warp"
    assert "api_key" not in response.text.lower()


def test_nvidia_warp_warmup_endpoint_returns_runtime_result():
    client = TestClient(backend.app)
    expected = {"ok": True, "backend": "nvidia-warp", "selected_device": "cuda:0", "value": 42}
    with patch.object(backend.nvidia_warp_runtime, "warmup", return_value=expected):
        response = client.post("/api/integrations/nvidia-warp/warmup", json={"device": "cuda:0"})

    assert response.status_code == 200
    assert response.json() == expected


def test_dashboard_exposes_nvidia_warp_status():
    client = TestClient(backend.app)
    with patch.object(backend.nvidia_warp_runtime, "status", return_value={"available": False, "backend": "nvidia-warp"}):
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json()["nvidia_warp"]["backend"] == "nvidia-warp"
