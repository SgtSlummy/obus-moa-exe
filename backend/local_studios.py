"""Loopback-only status and launch helpers for OBus visual integrations."""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from backend.process_utils import silent_process_kwargs


DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"
DEFAULT_UNDERSTAND_ANYTHING_URL = "http://127.0.0.1:5173"
MAX_GRAPH_BYTES = 5 * 1024 * 1024


def _loopback_url(value: str, fallback: str) -> str:
    """Return a normalized local HTTP URL, never an arbitrary network target."""
    candidate = str(value or fallback).strip().rstrip("/")
    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return fallback
    return candidate


def _json_probe(url: str, path: str, timeout: float = 1.5) -> tuple[bool, dict[str, Any] | None]:
    try:
        with urllib.request.urlopen(f"{url}{path}", timeout=timeout) as response:
            if response.status != 200:
                return False, None
            value = json.loads(response.read().decode("utf-8"))
            return True, value if isinstance(value, dict) else None
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        return False, None


def comfyui_configuration() -> dict[str, Any]:
    home = Path(os.environ.get("COMFYUI_HOME", Path.home() / "Documents" / "comfy" / "ComfyUI")).expanduser()
    python = Path(os.environ.get("COMFYUI_PYTHON", home / ".venv" / "Scripts" / "python.exe")).expanduser()
    return {
        "url": _loopback_url(os.environ.get("COMFYUI_URL", DEFAULT_COMFYUI_URL), DEFAULT_COMFYUI_URL),
        "home": home,
        "python": python,
    }


def comfyui_status() -> dict[str, Any]:
    config = comfyui_configuration()
    reachable, stats = _json_probe(config["url"], "/system_stats")
    system = (stats or {}).get("system") or {}
    launch_ready = (config["home"] / "main.py").is_file() and config["python"].is_file()
    reason = "ready" if reachable else "service_not_running" if launch_ready else "source_not_found"
    next_step = "none" if reachable else "start_local_service" if launch_ready else "configure_source_root"
    return {
        "url": config["url"],
        "reachable": reachable,
        "status": "ready" if reachable else "offline",
        "version": system.get("comfyui_version"),
        "device": system.get("device"),
        "launch_ready": launch_ready,
        "launch_mode": "local-source",
        "reason": reason,
        "next_step": next_step,
    }


def launch_comfyui() -> dict[str, Any]:
    """Start only the configured current-user local ComfyUI source install."""
    status = comfyui_status()
    if status["reachable"]:
        return {**status, "started": False, "message": "ComfyUI is already running."}

    config = comfyui_configuration()
    main = config["home"] / "main.py"
    python = config["python"]
    if not main.is_file() or not python.is_file():
        return {
            **status,
            "started": False,
            "message": "ComfyUI source or its configured virtual-environment Python was not found.",
        }

    subprocess.Popen(
        [str(python), "main.py", "--listen", "127.0.0.1", "--port", str(urllib.parse.urlsplit(config["url"]).port or 8188)],
        cwd=str(config["home"]),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **silent_process_kwargs(),
    )
    return {**status, "started": True, "message": "ComfyUI launch requested; refresh its status in a moment."}


def _graph_path(workspace_root: str | None) -> Path | None:
    if not workspace_root:
        return None
    root = Path(workspace_root).expanduser()
    if not root.is_dir():
        return None
    for name in (".ua", ".understand-anything"):
        candidate = root / name / "knowledge-graph.json"
        if candidate.is_file() and candidate.stat().st_size <= MAX_GRAPH_BYTES:
            return candidate
    return None


def understand_anything_status(workspace_root: str | None) -> dict[str, Any]:
    url = _loopback_url(os.environ.get("UNDERSTAND_ANYTHING_URL", DEFAULT_UNDERSTAND_ANYTHING_URL), DEFAULT_UNDERSTAND_ANYTHING_URL)
    graph_path = _graph_path(workspace_root)
    graph: dict[str, Any] = {}
    if graph_path:
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            graph_path = None
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    edges = graph.get("edges") if isinstance(graph, dict) else []
    reachable, _ = _json_probe(url, "/")
    reason = "ready" if graph_path else "workspace_not_configured" if not workspace_root else "graph_not_found"
    next_step = "none" if graph_path else "configure_workspace_root" if not workspace_root else "run_understand_analysis"
    return {
        "url": url,
        "reachable": reachable,
        "status": "ready" if graph_path else "needs-analysis",
        "graph_available": bool(graph_path),
        "nodes": len(nodes) if isinstance(nodes, list) else 0,
        "edges": len(edges) if isinstance(edges, list) else 0,
        "graph_path": str(graph_path.relative_to(Path(workspace_root))) if graph_path and workspace_root else None,
        "workspace_configured": bool(workspace_root),
        "reason": reason,
        "next_step": next_step,
    }


def understand_anything_context(workspace_root: str | None) -> dict[str, Any]:
    status = understand_anything_status(workspace_root)
    if not status["graph_available"]:
        raise ValueError("No Understand Anything graph is available in the configured workspace.")
    context = (
        "[Understand Anything graph summary]\n"
        f"Graph: {status['graph_path']}\n"
        f"Structural nodes: {status['nodes']}\n"
        f"Relationships: {status['edges']}\n"
        "Use this as structural orientation only; inspect bounded workspace files before making implementation claims.\n"
        "[/Understand Anything graph summary]"
    )
    return {"context": context, "nodes": status["nodes"], "edges": status["edges"]}
