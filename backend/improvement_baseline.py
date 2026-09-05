"""Reproducible, synthetic cross-model baseline for measured Obus improvements.

The suite is deliberately public and deterministic.  It is development evidence only:
results never qualify, promote, or otherwise mutate the Autonomous AGI claim.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import time
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "improvement-baseline-manifest.json"
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OMNIROUTE_CHAT_URL = "http://127.0.0.1:20128/v1/chat/completions"
BASELINE_RECEIPT_DIR_ENV = "OBUS_BASELINE_RECEIPT_DIR"
_ALLOWED_ADAPTERS = frozenset({"ollama_chat", "omniroute_chat"})
_ALLOWED_SCORERS = frozenset({"exact", "json_equal"})

Generator = Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]

_LATEST_REPORT: dict[str, Any] | None = None
_LATEST_LOCK = RLock()


class BaselineEvaluationError(ValueError):
    """Raised when the frozen baseline contract or a caller request is invalid."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def document_digest(value: Any) -> str:
    """Return a stable SHA-256 digest for JSON-compatible evidence."""

    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def receipt_directory() -> Path:
    """Return the bounded local directory for persistent synthetic receipts."""

    configured = os.environ.get(BASELINE_RECEIPT_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Obus" / "receipts" / "improvement-baseline"
    return Path.home() / ".local" / "share" / "obus" / "receipts" / "improvement-baseline"


def _validated_report(value: Any) -> dict[str, Any]:
    report = dict(_require_mapping(value, "baseline report"))
    declared = _require_text(report.get("report_digest"), "report.report_digest")
    payload = deepcopy(report)
    payload.pop("report_digest", None)
    if document_digest(payload) != declared:
        raise BaselineEvaluationError("baseline report digest does not match its content")
    return report


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _persist_report(report: Mapping[str, Any]) -> dict[str, str]:
    verified = _validated_report(report)
    directory = receipt_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        content = (_canonical_json(verified) + "\n").encode("utf-8")
        artifact = directory / f"{verified['report_digest']}.json"
        if artifact.exists() and artifact.read_bytes() != content:
            raise BaselineEvaluationError("content-addressed receipt collision")
        if not artifact.exists():
            _atomic_write(artifact, content)
        latest = directory / "latest.json"
        _atomic_write(latest, content)
        latest_valid = directory / "latest-valid.json"
        comparison = _require_mapping(verified.get("comparison"), "report comparison")
        if comparison.get("measurement_valid") is True:
            _atomic_write(latest_valid, content)
    except OSError as exc:
        raise BaselineEvaluationError("baseline receipt could not be persisted") from exc
    return {
        "directory": str(directory),
        "artifact": str(artifact),
        "latest": str(latest),
        "latest_valid": str(latest_valid),
    }


def _load_persisted_report() -> dict[str, Any] | None:
    latest = receipt_directory() / "latest.json"
    if not latest.exists():
        return None
    try:
        value = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineEvaluationError("persisted baseline receipt is unreadable") from exc
    return _validated_report(value)


def _load_latest_valid_report() -> dict[str, Any] | None:
    latest_valid = receipt_directory() / "latest-valid.json"
    if not latest_valid.exists():
        return None
    try:
        value = json.loads(latest_valid.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineEvaluationError("latest valid baseline receipt is unreadable") from exc
    report = _validated_report(value)
    comparison = _require_mapping(report.get("comparison"), "report comparison")
    if comparison.get("measurement_valid") is not True:
        raise BaselineEvaluationError("latest valid baseline receipt is not measurement-valid")
    return report


def harness_digest() -> str:
    """Identify the exact scorer/runner implementation used by a receipt."""

    return sha256(Path(__file__).read_bytes()).hexdigest()


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BaselineEvaluationError(f"{label} must be an object")
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BaselineEvaluationError(f"{label} must be a non-empty string")
    return value


def _require_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BaselineEvaluationError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise BaselineEvaluationError(f"{label} must be between {minimum} and {maximum}")
    return value


def _validate_protocol(protocol: Mapping[str, Any]) -> None:
    default_repeats = _require_int(
        protocol.get("default_repeats"), "protocol.default_repeats", 1, 3
    )
    max_repeats = _require_int(
        protocol.get("max_repeats"), "protocol.max_repeats", 1, 3
    )
    if default_repeats > max_repeats:
        raise BaselineEvaluationError("default_repeats cannot exceed max_repeats")
    _require_int(protocol.get("seed"), "protocol.seed", 0, 2_147_483_647)
    _require_int(
        protocol.get("max_output_tokens"), "protocol.max_output_tokens", 1, 128
    )
    _require_int(protocol.get("timeout_seconds"), "protocol.timeout_seconds", 1, 180)
    if protocol.get("temperature") != 0:
        raise BaselineEvaluationError("protocol.temperature must be zero")
    _require_text(protocol.get("system_prompt"), "protocol.system_prompt")
    required = protocol.get("required_arm_ids")
    if not isinstance(required, list) or len(required) < 2:
        raise BaselineEvaluationError("protocol.required_arm_ids must name at least two arms")


def _validate_arms(manifest: Mapping[str, Any]) -> None:
    arms = manifest.get("arms")
    if not isinstance(arms, list) or len(arms) < 2:
        raise BaselineEvaluationError("arms must contain at least two entries")
    ids: set[str] = set()
    for index, raw_arm in enumerate(arms):
        arm = _require_mapping(raw_arm, f"arms[{index}]")
        arm_id = _require_text(arm.get("id"), f"arms[{index}].id")
        if arm_id in ids:
            raise BaselineEvaluationError(f"duplicate arm id: {arm_id}")
        ids.add(arm_id)
        _require_text(arm.get("provider"), f"arms[{index}].provider")
        adapter = _require_text(arm.get("adapter"), f"arms[{index}].adapter")
        if adapter not in _ALLOWED_ADAPTERS:
            raise BaselineEvaluationError(f"unsupported adapter: {adapter}")
        _require_text(arm.get("model"), f"arms[{index}].model")
    required = set(manifest["protocol"]["required_arm_ids"])
    if not required.issubset(ids):
        raise BaselineEvaluationError("every required arm id must exist")


def _validate_probes(manifest: Mapping[str, Any]) -> None:
    probes = manifest.get("probes")
    if not isinstance(probes, list) or len(probes) < 4:
        raise BaselineEvaluationError("probes must contain at least four entries")
    ids: set[str] = set()
    for index, raw_probe in enumerate(probes):
        probe = _require_mapping(raw_probe, f"probes[{index}]")
        probe_id = _require_text(probe.get("id"), f"probes[{index}].id")
        if probe_id in ids:
            raise BaselineEvaluationError(f"duplicate probe id: {probe_id}")
        ids.add(probe_id)
        _require_text(probe.get("category"), f"probes[{index}].category")
        _require_text(probe.get("prompt"), f"probes[{index}].prompt")
        scorer = _require_mapping(probe.get("scorer"), f"probes[{index}].scorer")
        scorer_type = _require_text(scorer.get("type"), "scorer.type")
        if scorer_type not in _ALLOWED_SCORERS:
            raise BaselineEvaluationError(f"unsupported scorer: {scorer_type}")
        if "expected" not in scorer:
            raise BaselineEvaluationError(f"probe {probe_id} has no expected value")
        if scorer_type == "exact" and not isinstance(scorer["expected"], str):
            raise BaselineEvaluationError(f"probe {probe_id} exact expected must be text")
        if scorer_type == "json_equal" and not isinstance(
            scorer["expected"], (Mapping, list)
        ):
            raise BaselineEvaluationError(
                f"probe {probe_id} json_equal expected must be JSON object or array"
            )


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Fail closed when the suite would not produce comparable receipts."""

    if manifest.get("schema_version") != 1:
        raise BaselineEvaluationError("unsupported manifest schema_version")
    suite = _require_mapping(manifest.get("suite"), "suite")
    for key in ("id", "version", "title", "purpose", "visibility", "evidence_class"):
        _require_text(suite.get(key), f"suite.{key}")
    if suite.get("evidence_class") != "descriptive_non_agi":
        raise BaselineEvaluationError("suite.evidence_class must remain descriptive_non_agi")
    protocol = _require_mapping(manifest.get("protocol"), "protocol")
    _validate_protocol(protocol)
    _validate_arms(manifest)
    _validate_probes(manifest)
    limitations = manifest.get("limitations")
    if not isinstance(limitations, list) or not all(
        isinstance(item, str) and item.strip() for item in limitations
    ):
        raise BaselineEvaluationError("limitations must be a non-empty text list")


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the frozen synthetic suite."""

    source = path or MANIFEST_PATH
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineEvaluationError("baseline manifest is unavailable") from exc
    manifest = dict(_require_mapping(value, "manifest"))
    validate_manifest(manifest)
    return manifest


def _strip_code_fence(value: str) -> str:
    text = value.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines:
        lines.pop(0)
    if lines and lines[-1].strip() == "```":
        lines.pop()
    return "\n".join(lines).strip()


def score_output(output: str, scorer: Mapping[str, Any]) -> dict[str, Any]:
    """Score one response without a model judge or subjective rubric."""

    observed = _strip_code_fence(output)
    scorer_type = scorer["type"]
    if scorer_type == "exact":
        expected = str(scorer["expected"]).strip()
        if not scorer.get("case_sensitive", True):
            passed = observed.casefold() == expected.casefold()
        else:
            passed = observed == expected
        return {"score": 1.0 if passed else 0.0, "passed": passed, "reason": "exact"}
    if scorer_type == "json_equal":
        try:
            parsed = json.loads(observed)
        except json.JSONDecodeError:
            return {"score": 0.0, "passed": False, "reason": "invalid_json"}
        passed = parsed == scorer["expected"]
        return {
            "score": 1.0 if passed else 0.0,
            "passed": passed,
            "reason": "json_equal",
        }
    raise BaselineEvaluationError(f"unsupported scorer: {scorer_type}")


def _post_json(url: str, payload: Mapping[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        data=_canonical_json(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        raise BaselineEvaluationError(f"adapter returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise BaselineEvaluationError("adapter is unavailable") from exc
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BaselineEvaluationError("adapter returned invalid JSON") from exc
    return dict(_require_mapping(value, "adapter response"))


def _ollama_generate(
    prompt: str, arm: Mapping[str, Any], protocol: Mapping[str, Any]
) -> Mapping[str, Any]:
    from backend.epistemic_policy import guard_epistemic_request

    guard_decision = guard_epistemic_request(prompt)
    if guard_decision.blocked and guard_decision.response:
        return {
            "text": guard_decision.response,
            "returned_model": str(arm["model"]),
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    payload = {
        "model": arm["model"],
        "messages": [
            {"role": "system", "content": str(protocol["system_prompt"])},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "keep_alive": -1,
        "options": {
            "temperature": protocol["temperature"],
            "seed": protocol["seed"],
            "num_predict": protocol["max_output_tokens"],
            "num_ctx": 8192,
        },
    }
    response = _post_json(OLLAMA_CHAT_URL, payload, protocol["timeout_seconds"])
    message = _require_mapping(response.get("message"), "Ollama message")
    text = message.get("content")
    if not isinstance(text, str):
        raise BaselineEvaluationError("Ollama response has no text content")
    return {
        "text": text,
        "returned_model": str(response.get("model") or arm["model"]),
        "finish_reason": "stop" if response.get("done") else "incomplete",
        "usage": {
            "prompt_tokens": response.get("prompt_eval_count"),
            "completion_tokens": response.get("eval_count"),
        },
    }


def _omniroute_generate(
    prompt: str, arm: Mapping[str, Any], protocol: Mapping[str, Any]
) -> Mapping[str, Any]:
    payload = {
        "model": arm["model"],
        "messages": [
            {"role": "system", "content": protocol["system_prompt"]},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "temperature": protocol["temperature"],
        "seed": protocol["seed"],
        "max_tokens": protocol["max_output_tokens"],
    }
    response = _post_json(OMNIROUTE_CHAT_URL, payload, protocol["timeout_seconds"])
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise BaselineEvaluationError("OmniRoute response has no choices")
    choice = _require_mapping(choices[0], "OmniRoute choice")
    message = _require_mapping(choice.get("message"), "OmniRoute message")
    text = message.get("content")
    if not isinstance(text, str):
        raise BaselineEvaluationError("OmniRoute response has no text content")
    usage = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    return {
        "text": text,
        "returned_model": str(response.get("model") or arm["model"]),
        "finish_reason": str(choice.get("finish_reason") or "unknown"),
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    }


def _adapter_for(arm: Mapping[str, Any]) -> Generator:
    adapter = arm["adapter"]
    if adapter == "ollama_chat":
        return _ollama_generate
    if adapter == "omniroute_chat":
        return _omniroute_generate
    raise BaselineEvaluationError(f"unsupported adapter: {adapter}")


def _clean_usage(value: Any) -> dict[str, int | None]:
    if not isinstance(value, Mapping):
        return {}
    cleaned: dict[str, int | None] = {}
    for key, raw in value.items():
        if raw is None:
            cleaned[str(key)] = None
        elif isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            cleaned[str(key)] = raw
    return cleaned


def _run_probe(
    probe: Mapping[str, Any],
    repeat: int,
    arm: Mapping[str, Any],
    protocol: Mapping[str, Any],
    generator: Generator,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = generator(str(probe["prompt"]), arm, protocol)
        text = response.get("text")
        if not isinstance(text, str):
            raise BaselineEvaluationError("generator returned no text")
        scored = score_output(text, _require_mapping(probe["scorer"], "scorer"))
        return {
            "probe_id": probe["id"],
            "category": probe["category"],
            "repeat": repeat,
            "status": "completed",
            "score": scored["score"],
            "passed": scored["passed"],
            "score_reason": scored["reason"],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "output_digest": sha256(text.encode("utf-8")).hexdigest(),
            "observed_output": _strip_code_fence(text)[:512],
            "returned_model": str(response.get("returned_model") or arm["model"]),
            "finish_reason": str(response.get("finish_reason") or "unknown"),
            "usage": _clean_usage(response.get("usage")),
            "error": None,
        }
    except (BaselineEvaluationError, ValueError, TypeError) as exc:
        return {
            "probe_id": probe["id"],
            "category": probe["category"],
            "repeat": repeat,
            "status": "error",
            "score": 0.0,
            "passed": False,
            "score_reason": "adapter_error",
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "output_digest": None,
            "observed_output": "",
            "returned_model": None,
            "finish_reason": None,
            "usage": {},
            "error": str(exc),
        }


def _category_scores(samples: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for sample in samples:
        grouped.setdefault(str(sample["category"]), []).append(float(sample["score"]))
    return {
        category: round(statistics.fmean(scores) * 100, 2)
        for category, scores in sorted(grouped.items())
    }


def _repeat_scores(samples: Sequence[Mapping[str, Any]], repeats: int) -> list[float]:
    values: list[float] = []
    for repeat in range(1, repeats + 1):
        scores = [float(item["score"]) for item in samples if item["repeat"] == repeat]
        values.append(round(statistics.fmean(scores) * 100, 2) if scores else 0.0)
    return values


def _arm_summary(samples: Sequence[Mapping[str, Any]], repeats: int) -> dict[str, Any]:
    scores = [float(sample["score"]) for sample in samples]
    repeat_scores = _repeat_scores(samples, repeats)
    returned_models = sorted(
        {str(sample["returned_model"]) for sample in samples if sample["returned_model"]}
    )
    error_count = sum(1 for sample in samples if sample["status"] != "completed")
    return {
        "status": "completed" if error_count == 0 else "incomplete",
        "score_percent": round(statistics.fmean(scores) * 100, 2) if scores else 0.0,
        "passed_samples": sum(1 for sample in samples if sample["passed"]),
        "sample_count": len(samples),
        "error_count": error_count,
        "category_scores": _category_scores(samples),
        "repeat_scores": repeat_scores,
        "repeat_stddev": round(statistics.pstdev(repeat_scores), 4)
        if len(repeat_scores) > 1
        else 0.0,
        "returned_models": returned_models,
        "identity_stable": len(returned_models) == 1 and error_count == 0,
        "latency_ms_total": sum(int(sample["latency_ms"]) for sample in samples),
    }


def run_arm(
    manifest: Mapping[str, Any],
    arm: Mapping[str, Any],
    repeats: int,
    generator: Generator | None = None,
) -> dict[str, Any]:
    """Run one frozen arm and return its content-addressed receipt."""

    protocol = _require_mapping(manifest["protocol"], "protocol")
    selected_generator = generator or _adapter_for(arm)
    started_at = datetime.now(UTC).isoformat()
    samples = [
        _run_probe(probe, repeat, arm, protocol, selected_generator)
        for repeat in range(1, repeats + 1)
        for probe in manifest["probes"]
    ]
    summary = _arm_summary(samples, repeats)
    policy_binding = None
    if arm["adapter"] == "ollama_chat":
        from backend.epistemic_policy import epistemic_policy_status_payload

        policy_status = epistemic_policy_status_payload()
        policy_binding = {
            key: policy_status.get(key)
            for key in ("policy_id", "version", "status", "enabled", "directive_sha256")
        }
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "suite_id": manifest["suite"]["id"],
        "suite_version": manifest["suite"]["version"],
        "manifest_digest": document_digest(manifest),
        "harness_digest": harness_digest(),
        "arm": {
            "id": arm["id"],
            "provider": arm["provider"],
            "adapter": arm["adapter"],
            "requested_model": arm["model"],
        },
        "protocol": {
            "repeats": repeats,
            "temperature": protocol["temperature"],
            "seed": protocol["seed"],
            "max_output_tokens": protocol["max_output_tokens"],
            "tool_access": False,
            "workspace_data_sent": False,
        },
        "epistemic_policy": policy_binding,
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "samples": samples,
        "evidence_class": "descriptive_non_agi",
        "can_promote_autonomous_agi": False,
    }
    receipt["receipt_digest"] = document_digest(receipt)
    return receipt


def _next_gap(arms: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Select only a practically meaningful measured external lead.

    A positive score delta alone can be ordinary measurement noise.  The
    comparison is still recorded for diagnosis, but it must clear one whole
    percentage point before it is eligible to seed a bounded improvement task.
    Promotion remains outside this selection path and requires human approval.
    """
    practical_margin = 1.0
    local = arms[0]["summary"]["category_scores"]
    external = arms[1]["summary"]["category_scores"]
    categories = sorted(set(local) | set(external))
    gaps = [
        {
            "category": category,
            "local_score": float(local.get(category, 0.0)),
            "external_score": float(external.get(category, 0.0)),
            "external_minus_local": round(
                float(external.get(category, 0.0)) - float(local.get(category, 0.0)), 2
            ),
        }
        for category in categories
    ]
    positive = sorted(gaps, key=lambda item: item["external_minus_local"], reverse=True)
    if positive and positive[0]["external_minus_local"] >= practical_margin:
        return {
            **positive[0],
            "selection_status": "measured_external_lead",
            "task_selection_permitted": True,
            "practical_margin": practical_margin,
        }
    if positive and positive[0]["external_minus_local"] > 0:
        return {
            **positive[0],
            "selection_status": "measured_external_lead_below_practical_margin",
            "task_selection_permitted": False,
            "practical_margin": practical_margin,
        }
    return {
        "category": "no_measured_local_deficit",
        "local_score": float(arms[0]["summary"]["score_percent"]),
        "external_score": float(arms[1]["summary"]["score_percent"]),
        "external_minus_local": round(
            float(arms[1]["summary"]["score_percent"])
            - float(arms[0]["summary"]["score_percent"]),
            2,
        ),
        "selection_status": "no_measured_local_deficit",
        "task_selection_permitted": False,
        "practical_margin": practical_margin,
    }


def _comparison_summary(
    manifest: Mapping[str, Any], arms: Sequence[Mapping[str, Any]], repeats: int
) -> dict[str, Any]:
    local_score = float(arms[0]["summary"]["score_percent"])
    external_score = float(arms[1]["summary"]["score_percent"])
    complete = all(arm["summary"]["status"] == "completed" for arm in arms)
    stable = all(arm["summary"]["identity_stable"] for arm in arms)
    blockers = [
        "public_development_suite",
        "not_independent_replication",
        "external_snapshot_not_immutable",
    ]
    if str(arms[1]["arm"]["requested_model"]).startswith("auto/"):
        blockers.append("external_alias_not_immutable")
    if repeats < 2:
        blockers.append("single_run_no_variance_evidence")
    if not complete:
        blockers.append("incomplete_samples")
    if not stable:
        blockers.append("model_identity_not_stable")
    if math.isclose(local_score, external_score):
        leader = "tie"
    else:
        leader = arms[0]["arm"]["id"] if local_score > external_score else arms[1]["arm"]["id"]
    next_gap = _next_gap(arms)
    task_selection_permitted = bool(next_gap["task_selection_permitted"])
    planning_eligible = (
        complete
        and stable
        and repeats >= 2
        and "external_alias_not_immutable" not in blockers
        and task_selection_permitted
    )
    learning_objective = {
        "schema_version": "evidence-qualified-development-objective-v1",
        "status": (
            "eligible_for_operator_planning"
            if planning_eligible
            else (
                "ineligible_no_measured_local_deficit"
                if not task_selection_permitted
                else "ineligible_insufficient_verified_evidence"
            )
        ),
        "category": next_gap["category"],
        "kind": (
            "close_external_lead"
            if task_selection_permitted
            else "no_measured_local_deficit"
        ),
        "direction": "improve_local_score" if task_selection_permitted else "none",
        "local_score": next_gap["local_score"],
        "external_score": next_gap["external_score"],
        "external_minus_local": next_gap["external_minus_local"],
        "evidence_source": "repeated_cross_model_development_baseline",
        "operator_action": (
            f"Review the verified {next_gap['category']} gap before selecting an explicit development task."
            if planning_eligible
            else (
                "No learning task is selected: this comparison shows no category where external outperforms local."
                if not task_selection_permitted
                else "Do not select a learning task from this comparison; obtain stable repeated evidence first."
            )
        ),
        "task_selection_permitted": task_selection_permitted,
        "automatic_execution_authorized": False,
        "promotion_authorized": False,
        "autonomous_agi_evidence": False,
    }
    return {
        "status": "descriptive_only" if complete else "incomplete",
        "measurement_valid": complete,
        "leader": leader,
        "local_score_percent": local_score,
        "external_score_percent": external_score,
        "local_minus_external_points": round(local_score - external_score, 2),
        "next_improvement_gap": next_gap,
        "learning_objective": learning_objective,
        "comparability_blockers": blockers,
        "autonomous_agi_evidence": False,
        "promotion_authorized": False,
    }


def _select_arms(manifest: Mapping[str, Any], arm_ids: Sequence[str] | None) -> list[dict[str, Any]]:
    required = list(manifest["protocol"]["required_arm_ids"])
    selected_ids = list(arm_ids) if arm_ids is not None else required
    if selected_ids != required:
        raise BaselineEvaluationError(
            "this comparison must use the frozen required arms in their declared order"
        )
    arm_by_id = {arm["id"]: arm for arm in manifest["arms"]}
    return [dict(arm_by_id[arm_id]) for arm_id in selected_ids]


def run_comparison(
    *,
    repeats: int | None = None,
    arm_ids: Sequence[str] | None = None,
    generator: Generator | None = None,
) -> dict[str, Any]:
    """Run the complete frozen comparison without task tools or private context."""

    manifest = load_manifest()
    protocol = manifest["protocol"]
    selected_repeats = protocol["default_repeats"] if repeats is None else repeats
    selected_repeats = _require_int(
        selected_repeats, "repeats", 1, int(protocol["max_repeats"])
    )
    selected_arms = _select_arms(manifest, arm_ids)
    receipts = [
        run_arm(manifest, arm, selected_repeats, generator=generator)
        for arm in selected_arms
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "suite": deepcopy(manifest["suite"]),
        "manifest_digest": document_digest(manifest),
        "harness_digest": harness_digest(),
        "repeats": selected_repeats,
        "arms": receipts,
        "comparison": _comparison_summary(manifest, receipts, selected_repeats),
        "limitations": list(manifest["limitations"]),
        "research_basis": deepcopy(manifest.get("research_basis", [])),
        "target_claim_relationship": {
            "target": "Autonomous AGI",
            "can_qualify_claim": False,
            "can_promote_claim": False,
            "reason": "A public synthetic development baseline is not sealed capability evidence.",
        },
    }
    report["report_digest"] = document_digest(report)
    return report


def _restore_configured_local_runtime() -> dict[str, Any]:
    """Recover the configured primary after a descriptive local-model probe."""

    try:
        # Delay the import to avoid coupling the evidence module to application startup.
        from backend.main import _configured_local_model, warm_ollama_model

        model = _configured_local_model()
        warmup = warm_ollama_model(model)
    except Exception:
        return {
            "status": "recovery_unavailable",
            "non_evidence": True,
            "reason": "configured_local_warmup_unavailable",
        }

    observed_context = warmup.get("observed_context_tokens") or warmup.get("context_tokens")
    verified = warmup.get("status") == "warm" and warmup.get("accepted") is True
    return {
        "status": "restored" if verified else "recovery_unverified",
        "model": model,
        "observed_context_tokens": observed_context,
        "non_evidence": True,
    }


def run_and_record_comparison(*, repeats: int | None = None) -> dict[str, Any]:
    """Run, persist, then restore the configured primary local runtime."""

    report: dict[str, Any] | None = None
    try:
        report = run_comparison(repeats=repeats)
        with _LATEST_LOCK:
            global _LATEST_REPORT
            _persist_report(report)
            _LATEST_REPORT = deepcopy(report)
        return report
    finally:
        recovery = _restore_configured_local_runtime()
        if report is not None:
            # Operational recovery is intentionally excluded from the evidence digest.
            report["runtime_recovery"] = recovery


def baseline_status() -> dict[str, Any]:
    """Return the current valid baseline and latest attempt without running models."""

    manifest = load_manifest()
    manifest_id = document_digest(manifest)
    harness_id = harness_digest()
    directory = receipt_directory()
    with _LATEST_LOCK:
        global _LATEST_REPORT
        latest = deepcopy(_LATEST_REPORT)
        if latest is None:
            latest = _load_persisted_report()
            if latest is not None:
                _LATEST_REPORT = deepcopy(latest)
    latest_valid = _load_latest_valid_report()

    latest_matches_current = bool(
        latest
        and latest.get("manifest_digest") == manifest_id
        and latest.get("harness_digest") == harness_id
    )
    latest_measurement_valid = bool(
        latest_matches_current
        and isinstance(latest.get("comparison"), Mapping)
        and latest["comparison"].get("measurement_valid") is True
    )
    valid_matches_current = bool(
        latest_valid
        and latest_valid.get("manifest_digest") == manifest_id
        and latest_valid.get("harness_digest") == harness_id
    )
    current = latest if latest_measurement_valid else (
        latest_valid if valid_matches_current else None
    )
    current_source = (
        "latest" if latest_measurement_valid else (
            "latest-valid" if valid_matches_current else None
        )
    )
    latest_attempt = latest if latest_matches_current else None
    latest_attempt_status = (
        str(latest_attempt["comparison"].get("status"))
        if latest_attempt and isinstance(latest_attempt.get("comparison"), Mapping)
        else None
    )
    incomplete_report_digest = (
        latest_attempt.get("report_digest")
        if latest_attempt and not latest_measurement_valid
        else None
    )
    return {
        "schema_version": 1,
        "status": "measured" if current else ("stale" if latest else "not_run"),
        "suite": deepcopy(manifest["suite"]),
        "manifest_digest": manifest_id,
        "harness_digest": harness_id,
        "default_repeats": manifest["protocol"]["default_repeats"],
        "max_repeats": manifest["protocol"]["max_repeats"],
        "arm_ids": list(manifest["protocol"]["required_arm_ids"]),
        "probe_count": len(manifest["probes"]),
        "limitations": list(manifest["limitations"]),
        "latest_report": current,
        "latest_report_source": current_source,
        "latest_attempt": latest_attempt,
        "latest_attempt_status": latest_attempt_status,
        "incomplete_report_digest": incomplete_report_digest,
        "stale_report_digest": latest.get("report_digest") if latest and not latest_matches_current else None,
        "receipt_storage": {
            "directory": str(directory),
            "latest": str(directory / "latest.json"),
            "latest_valid": str(directory / "latest-valid.json"),
            "persistent": (directory / "latest.json").exists(),
            "valid_persistent": (directory / "latest-valid.json").exists(),
        },
        "can_promote_autonomous_agi": False,
    }
