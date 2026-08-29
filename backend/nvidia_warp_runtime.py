"""Optional NVIDIA Warp runtime boundary for OBus.

This module is intentionally separate from ``backend.warp_companion``, which
launches the unrelated Warp terminal TUI. Warp is used here only for bounded
numeric GPU work; Ollama remains responsible for transformer inference.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any


_BACKEND = "nvidia-warp"
_CPU = "cpu"
_DEFAULT_CUDA = "cuda:0"


def _valid_warp(module: Any) -> bool:
    return all(hasattr(module, name) for name in ("get_devices", "is_cuda_available", "launch", "zeros"))


def _load_warp() -> Any | None:
    """Load the installed Warp package without accepting the local source shadow."""
    try:
        module = importlib.import_module("warp")
    except (ImportError, ModuleNotFoundError):
        module = None
    if module is not None and _valid_warp(module):
        return module

    # The repository contains a source checkout named ``warp``. When OBus is
    # launched from the repository root it can shadow the installed wheel.
    previous = sys.modules.pop("warp", None)
    project_root = Path(__file__).resolve().parents[1]
    original_path = list(sys.path)
    try:
        sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != project_root]
        importlib.invalidate_caches()
        spec = importlib.util.find_spec("warp")
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules["warp"] = module
        spec.loader.exec_module(module)
        return module if _valid_warp(module) else None
    except (ImportError, ModuleNotFoundError, OSError, RuntimeError):
        sys.modules.pop("warp", None)
        if previous is not None:
            sys.modules["warp"] = previous
        return None
    finally:
        sys.path[:] = original_path


def _device_alias(device: Any) -> str:
    return str(getattr(device, "alias", device))


def _devices(module: Any) -> list[str]:
    try:
        return [_device_alias(device) for device in module.get_devices()]
    # Warp initializes its cache lazily in get_devices(). A broken or
    # concurrently-created external cache must not take down the dashboard:
    # GPU acceleration is optional and the CPU fallback remains valid.
    except (AttributeError, OSError, RuntimeError, TypeError):
        return []


def _cuda_available(module: Any) -> bool:
    try:
        return bool(module.is_cuda_available())
    except (AttributeError, OSError, RuntimeError, TypeError):
        return False


def select_device(requested_device: str | None = None) -> dict[str, Any]:
    requested = str(requested_device or "auto").strip().lower()
    module = _load_warp()
    devices = _devices(module) if module is not None else []
    cuda_available = bool(module is not None and _cuda_available(module) and any(device.startswith("cuda:") for device in devices))
    available = set(devices)

    if requested == "auto":
        requested = _DEFAULT_CUDA if cuda_available else _CPU
    if requested == "cuda":
        requested = _DEFAULT_CUDA

    if requested == _CPU and _CPU in available:
        return {"requested_device": requested_device or "auto", "selected_device": _CPU, "fallback": False, "fallback_reason": None}
    if requested in available and requested.startswith("cuda:") and cuda_available:
        return {"requested_device": requested_device or "auto", "selected_device": requested, "fallback": False, "fallback_reason": None}

    reason = "Warp unavailable" if module is None else "CUDA device unavailable" if requested.startswith("cuda") else "Requested device unavailable"
    return {"requested_device": requested_device or "auto", "selected_device": _CPU, "fallback": True, "fallback_reason": reason}


def status(requested_device: str | None = None) -> dict[str, Any]:
    module = _load_warp()
    selection = select_device(requested_device)
    devices = _devices(module) if module is not None else []
    version = str(getattr(getattr(module, "config", None), "version", "unknown")) if module is not None else None
    return {
        "available": module is not None,
        "backend": _BACKEND,
        "version": version,
        "devices": devices,
        "requested_device": selection["requested_device"],
        "selected_device": selection["selected_device"],
        "fallback": selection["fallback"],
        "fallback_reason": selection["fallback_reason"],
        "llm_inference_acceleration": False,
    }


def _run_smoke_kernel(module: Any, device: str) -> int:
    @module.kernel
    def write_value(output: module.array(dtype=module.int32)):
        output[0] = 42

    output = module.zeros(1, dtype=module.int32, device=device)
    module.launch(write_value, dim=1, inputs=[output], device=device)
    module.synchronize_device(device)
    return int(output.numpy()[0])


def warmup(requested_device: str | None = None) -> dict[str, Any]:
    module = _load_warp()
    selection = select_device(requested_device)
    result = {
        **status(requested_device),
        "ok": False,
        "value": None,
    }
    if module is None:
        return result
    try:
        value = _run_smoke_kernel(module, selection["selected_device"])
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        result["error"] = type(exc).__name__
        return result
    result.update({"ok": value == 42, "value": value})
    return result


def preprocess(values: list[float], requested_device: str | None = None) -> dict[str, Any]:
    """Return bounded numeric metadata; this is not model inference."""
    import numpy as np

    selection = select_device(requested_device)
    numbers = [float(value) for value in values]
    module = _load_warp()
    if module is None or selection["selected_device"] == _CPU:
        return {
            "backend": "cpu",
            "selected_device": _CPU,
            "fallback": selection["fallback"],
            "fallback_reason": selection["fallback_reason"],
            "items": len(numbers),
            "checksum": float(sum(numbers)),
            "ok": True,
        }

    @module.kernel
    def copy_values(source: module.array(dtype=module.float32), output: module.array(dtype=module.float32)):
        index = module.tid()
        output[index] = source[index]

    source = module.array(np.asarray(numbers, dtype=np.float32), dtype=module.float32, device=selection["selected_device"])
    output = module.zeros(len(numbers), dtype=module.float32, device=selection["selected_device"])
    module.launch(copy_values, dim=len(numbers), inputs=[source, output], device=selection["selected_device"])
    module.synchronize_device(selection["selected_device"])
    checksum = float(output.numpy().sum())
    return {
        "backend": _BACKEND,
        "selected_device": selection["selected_device"],
        "fallback": selection["fallback"],
        "fallback_reason": selection["fallback_reason"],
        "items": len(numbers),
        "checksum": checksum,
        "ok": True,
    }
