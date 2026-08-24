"""Bounded, optional numeric preprocessing for OBus route manifests."""
from __future__ import annotations

from typing import Any

from backend import nvidia_warp_runtime


def preprocess(values: list[float], requested_device: str | None = None, min_batch_size: int = 256) -> dict[str, Any]:
    """Use CPU for small batches and delegate larger batches to NVIDIA Warp."""
    numbers = [float(value) for value in values]
    if len(numbers) < max(1, int(min_batch_size)) or str(requested_device or "").lower() == "cpu":
        return {
            "backend": "cpu",
            "selected_device": "cpu",
            "fallback": False,
            "fallback_reason": "batch_below_gpu_threshold" if len(numbers) < max(1, int(min_batch_size)) else None,
            "items": len(numbers),
            "checksum": float(sum(numbers)),
            "ok": True,
        }
    return nvidia_warp_runtime.preprocess(numbers, requested_device)
