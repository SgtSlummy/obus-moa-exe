from backend import main


def test_live_ollama_vram_overrides_a_stale_warmup_error(monkeypatch):
    monkeypatch.setattr(
        main,
        "GPU_WARM_STATE",
        {
            "status": "error",
            "model": "gpt-oss:20b",
            "keep_alive": -1,
            "started_at": "2026-08-28T00:18:08+00:00",
            "warmed_at": None,
            "load_duration_ns": None,
            "error": "TimeoutError",
        },
    )
    monkeypatch.setattr(
        main,
        "get_ollama_status",
        lambda: {
            "running_models": ["gpt-oss:20b"],
            "vram_bytes": {"gpt-oss:20b": 13_092_750_622},
        },
    )

    status = main.get_gpu_warm_status()

    assert status["status"] == "warm"
    assert status["model"] == "gpt-oss:20b"
    assert status["evidence"] == "ollama_ps_size_vram"
    assert status["error"] == "TimeoutError"


def test_no_live_vram_keeps_the_tracked_warmup_state(monkeypatch):
    monkeypatch.setattr(main, "GPU_WARM_STATE", {"status": "cold", "model": None, "error": None})
    monkeypatch.setattr(main, "get_ollama_status", lambda: {"running_models": ["gpt-oss:20b"], "vram_bytes": {}})

    assert main.get_gpu_warm_status() == {"status": "cold", "model": None, "error": None}
