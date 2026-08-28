import json

from backend import main


def test_warmup_preloads_without_empty_generation_prompt(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, traceback):
            return False

    def open_request(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(main, "get_ollama_status", lambda: {"connected": True, "models": ["gpt-oss:20b"]})
    monkeypatch.setattr(main, "open_loopback_request", open_request)
    monkeypatch.setattr(main, "read_loopback_warmup_response", lambda response: {"load_duration": 123})

    result = main.warm_ollama_model("gpt-oss:20b", keep_alive=-1)

    assert result["status"] == "warm"
    assert result["accepted"] is True
    assert captured["timeout"] == 300
    assert captured["payload"] == {"model": "gpt-oss:20b", "keep_alive": -1}


def test_warmup_marks_an_already_loaded_model_ready_without_request(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_ollama_status",
        lambda: {"connected": True, "models": ["gpt-oss:20b"], "running_models": ["gpt-oss:20b"]},
    )
    monkeypatch.setattr(main, "open_loopback_request", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("preload request")))

    result = main.warm_ollama_model("gpt-oss:20b", keep_alive=-1)

    assert result["status"] == "warm"
    assert result["accepted"] is True
    assert result["model"] == "gpt-oss:20b"
