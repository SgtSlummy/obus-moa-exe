import io
import threading

import pytest

from backend.autonomy import ProviderRegistry


class _CompletedProcess:
    def __init__(self):
        self.stdout = io.StringIO("plan complete")
        self.returncode = 0

    def poll(self):
        return 0


def test_autoagent_runtime_executes_a_validated_upstream_plan(monkeypatch, tmp_path):
    captured = {}
    events = []

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _CompletedProcess()

    monkeypatch.setattr("backend.autonomy.subprocess.Popen", fake_popen)
    output = ProviderRegistry._run_autoagent(
        None,
        {
            "objective": "fallback objective",
            "workspace": str(tmp_path),
            "upstream_plan": {
                "title": "Investigate",
                "steps": [
                    {"objective": "collect facts", "agent": "researcher"},
                    {"objective": "summarize", "agent": "writer"},
                ],
            },
        },
        threading.Event(),
        lambda event, payload: events.append((event, payload)),
    )

    assert output == "plan complete"
    assert captured["args"][-1] == "researcher: collect facts\n\nwriter: summarize"
    assert events[0][0] == "provider.plan"
    assert events[0][1]["plan"]["framework"] == "autoagent"


def test_autoagent_runtime_refuses_unapproved_upstream_plan(tmp_path):
    with pytest.raises(PermissionError, match="requires OBus approval"):
        ProviderRegistry._run_autoagent(
            None,
            {
                "objective": "fallback objective",
                "workspace": str(tmp_path),
                "upstream_plan": {
                    "steps": [{"objective": "deploy", "requires_approval": True}],
                },
            },
            threading.Event(),
            lambda _event, _payload: None,
        )
