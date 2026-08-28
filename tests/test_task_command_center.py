from pathlib import Path


SOURCE = Path(__file__).parents[1] / "backend" / "static" / "aui" / "task-command-center.js"


def test_task_command_center_has_safe_resume_and_approval_surfaces():
    source = SOURCE.read_text(encoding="utf-8")

    assert "Task command center" in source
    assert "/api/harness/tasks?limit=12" in source
    assert "/api/harness/approvals?limit=12" in source
    assert "Opening a task never replays it" in source
    assert "sessionStorage.setItem('obus-last-autonomous-task'" in source
    assert "Open agent jobs" in source
    assert "controlDrawer.open = false" in source
    assert "Selected task" in source
    assert "/api/harness/tasks/${encodeURIComponent(id)}" in source
    assert "/resume`, {method:'POST'}" in source
    assert "Re-inspecting the workspace before resume" in source


def test_task_command_center_collapses_for_small_windows():
    source = SOURCE.read_text(encoding="utf-8")

    assert "@media(max-width:720px){.task-command-grid{grid-template-columns:1fr}" in source
