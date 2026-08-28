from backend.main import select_task_performance_profile


def test_simple_one_shot_balanced_request_uses_fast_profile():
    assert select_task_performance_profile("Reply with exactly: ready", "balanced") == "fast"


def test_complex_balanced_request_keeps_parallel_profile():
    assert select_task_performance_profile("Investigate the architecture and build a test plan", "balanced") == "balanced"


def test_explicit_non_default_profiles_are_preserved():
    assert select_task_performance_profile("Reply with exactly: ready", "deep") == "deep"
    assert select_task_performance_profile("Reply with exactly: ready", "throughput") == "throughput"
    assert select_task_performance_profile("Reply with exactly: ready", "fast") == "fast"
