import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "obus_benchmark_plan.py"
SPEC = importlib.util.spec_from_file_location("obus_benchmark_plan", SCRIPT)
benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(benchmark)


def test_startup_receipt_prefers_newest_valid_loopback_port(tmp_path):
    receipts = tmp_path / "OBus" / "logs" / "startup"
    receipts.mkdir(parents=True)
    (receipts / "obus-startup-old.json").write_text(json.dumps({"app_port": 38173}), encoding="utf-8")
    newest = receipts / "obus-startup-new.json"
    newest.write_text(json.dumps({"app_port": 52276}), encoding="utf-8")
    assert benchmark.startup_receipt_obus_url(str(tmp_path)) == "http://127.0.0.1:52276"


def test_startup_receipt_skips_invalid_port_and_explicit_url_wins(tmp_path):
    receipts = tmp_path / "OBus" / "logs" / "startup"
    receipts.mkdir(parents=True)
    (receipts / "obus-startup-invalid.json").write_text(json.dumps({"app_port": 70000}), encoding="utf-8")
    assert benchmark.startup_receipt_obus_url(str(tmp_path)) is None
    assert benchmark.resolve_obus_url("http://127.0.0.1:49999") == "http://127.0.0.1:49999"


def test_probe_summary_excludes_full_dashboard_and_keeps_readiness():
    summary = benchmark.summarize_probe_body(
        "/api/dashboard",
        {
            "cards": [{"name": "one", "secret": "not retained"}],
            "settings": {"selected_model": "gpt-oss:20b", "autonomy_level": "high"},
            "voice": {"ready": True, "model_path": "not retained"},
            "warm_runtime": {"status": "warm", "secret": "not retained"},
        },
    )
    assert summary == {
        "card_count": 1,
        "selected_model": "gpt-oss:20b",
        "autonomy_level": "high",
        "voice_ready": True,
        "warm_status": "warm",
    }


def test_probe_summary_keeps_only_operational_ollama_model_fields():
    summary = benchmark.summarize_probe_body(
        "/api/ps",
        {"models": [{"name": "gpt-oss:20b", "context_length": 117964, "size_vram": 13, "secret": "not retained"}]},
    )
    assert summary == {"model_count": 1, "models": [{"name": "gpt-oss:20b", "context_length": 117964, "size_vram": 13}]}
