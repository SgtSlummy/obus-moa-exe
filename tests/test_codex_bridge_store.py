from pathlib import Path

from backend.codex_bridge_store import CodexBridgeThreadStore


def test_store_persists_only_workspace_thread_metadata(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = CodexBridgeThreadStore(tmp_path / "state" / "threads.json")

    store.remember("thr-1", workspace, "gpt-test")
    saved = store.path.read_text(encoding="utf-8")

    assert store.recent(workspace) == [{"thread_id": "thr-1", "workspace": str(workspace.resolve()), "model": "gpt-test", "updated_at": store.recent(workspace)[0]["updated_at"]}]
    assert "prompt" not in saved
    assert "credential" not in saved


def test_store_hides_threads_from_another_workspace(tmp_path: Path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    store = CodexBridgeThreadStore(tmp_path / "threads.json")
    store.remember("thr-one", first)

    assert store.recent(second) == []
