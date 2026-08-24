from unittest.mock import patch

import backend.warp_preprocessing as preprocessing


def test_small_inputs_use_cpu_without_warp():
    with patch.object(preprocessing.nvidia_warp_runtime, "preprocess") as warp_preprocess:
        result = preprocessing.preprocess([1.0, 2.0, 3.0], requested_device="cuda:0", min_batch_size=4)

    warp_preprocess.assert_not_called()
    assert result["backend"] == "cpu"
    assert result["selected_device"] == "cpu"
    assert result["fallback_reason"] == "batch_below_gpu_threshold"
    assert result["checksum"] == 6.0


def test_large_inputs_use_warp_runtime():
    expected = {
        "backend": "nvidia-warp",
        "selected_device": "cuda:0",
        "fallback": False,
        "fallback_reason": None,
        "items": 4,
        "checksum": 10.0,
        "ok": True,
    }
    with patch.object(preprocessing.nvidia_warp_runtime, "preprocess", return_value=expected) as warp_preprocess:
        result = preprocessing.preprocess([1.0, 2.0, 3.0, 4.0], requested_device="cuda:0", min_batch_size=4)

    warp_preprocess.assert_called_once()
    assert result == expected
