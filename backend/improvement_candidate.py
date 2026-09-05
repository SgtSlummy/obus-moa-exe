"""Trusted, allowlisted evidence runner for the warm-runtime candidate.

Docker supplies a repeatable isolation boundary. The trusted host separately binds
results to concrete source and diff bytes, verifies Ollama, and signs an attestation.
The signature binds recorded evidence; it is not proof that a claim is true.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from .improvement_evaluation import build_improvement_screening_receipt

CANDIDATE_KIND = "ollama-warm-residency-v1"
DOCKER_IMAGE = "obus-dev:latest"
MODEL = "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M"
# This sealed candidate measures the verified RTX 3090 full-GPU Qwen profile.
# Larger advertised contexts spill beyond the intended deterministic local path.
REQUESTED_CONTEXT = 65_536
KEEP_ALIVE = -1
PROBE_RUN_COUNT = 3
PROBE_TEST_PATH = "tests/test_runtime.py"
PROBE_TEST_SELECTORS = (
    "tests/test_runtime.py::RuntimeContractTests::test_warmup_keeps_local_model_resident_without_secrets",
    "tests/test_runtime.py::RuntimeContractTests::test_warmup_rejects_uninstalled_models_before_generation",
    "tests/test_runtime.py::RuntimeContractTests::test_warmup_is_single_flight_and_does_not_corrupt_model_state",
    "tests/test_runtime.py::RuntimeContractTests::test_warmup_recovers_from_non_object_ollama_response",
    "tests/test_runtime.py::RuntimeContractTests::test_startup_warmup_prefers_selected_installed_model",
)
ATTESTATION_KEY_ENV = "OBUS_IMPROVEMENT_ATTESTATION_KEY"

REVIEW_BASELINE_ARTIFACT_DIGEST = "02437041e5b9149076901a3c8e68aa0a426cc5aca16b926b36255814cb2a83f1"
REVIEW_CANDIDATE_ARTIFACT_DIGEST = "9b865e739fc135d3cb901320dec0ef3ffd041976239a7dfe5c0b272953357b20"
REVIEW_BASELINE_RECEIPTS = ("commit-293", "commit-294")
REVIEW_CANDIDATE_RECEIPTS = ("commit-325", "commit-326", "commit-328", "commit-330", "commit-332")

_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_IMMUTABLE_IMAGE = re.compile(r"^sha256:([0-9a-f]{64})$")
_SAFE_EVIDENCE_FIELDS = (
    "invocation_id", "evidence_contract_version", "candidate_kind",
    "objective", "artifact_path",
    "baseline_source_revision", "baseline_artifact_digest", "candidate_digest",
    "source_digest",
    "diff_digest", "diff_bytes", "sandbox_kind", "image_digest",
    "executed_image_ref", "baseline_probe_runs", "baseline_probe_passes",
    "probe_runs", "probe_passes", "model", "requested_context",
    "observed_context", "residency_verified", "test_digest",
    "evaluator_digest", "baseline_command_digest", "command_digest",
    "baseline_output_digest", "output_digest", "harness_manifest_digest",
    "baseline_manifest_digest", "candidate_manifest_digest", "comparison",
    "comparison_digest", "residency_observation_digest",
)


class CandidateRunError(RuntimeError):
    """Trusted candidate infrastructure could not produce evidence."""


class UnsupportedCandidateError(CandidateRunError):
    """The requested candidate is outside the fixed allowlist."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    data = value if isinstance(value, bytes) else _canonical_json(value).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CandidateRunError(f"required evidence input is unavailable: {path.name}") from exc


def _run_process(argv: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        return subprocess.run(
            list(argv), check=False, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CandidateRunError(f"candidate process failed: {argv[0]}") from exc


def _docker_image_digest() -> str:
    inspected = _run_process(
        ("docker", "image", "inspect", "--format", "{{.Id}}", DOCKER_IMAGE), timeout=30.0
    )
    image_id = inspected.stdout.strip().lower()
    match = _IMMUTABLE_IMAGE.fullmatch(image_id)
    if inspected.returncode != 0 or match is None:
        raise CandidateRunError(f"trusted Docker image is unavailable: {DOCKER_IMAGE}")
    return match.group(1)


def _probe_argv(
    repo_root: Path, *, artifact_override: Path | None = None
) -> tuple[str, ...]:
    image_digest = _docker_image_digest()
    repo_source = str(repo_root.resolve())
    artifact_source = str(artifact_override.resolve()) if artifact_override else None
    if any(character in repo_source for character in ",\r\n") or (
        artifact_source is not None
        and any(character in artifact_source for character in ",\r\n")
    ):
        raise CandidateRunError(
            "Docker bind source paths containing commas or line breaks are unsupported"
        )
    mounts = [
        "--mount", f"type=bind,source={repo_source},target=/workspace,readonly",
    ]
    if artifact_override is not None:
        mounts.extend([
            "--mount",
            f"type=bind,source={artifact_source},target=/workspace/backend/main.py,readonly",
        ])
    return (
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--cpus", "0.50", "--memory", "1g", "--pids-limit", "128",
        *mounts,
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m",
        "--tmpfs", "/root:rw,noexec,nosuid,size=128m",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--workdir", "/workspace", f"sha256:{image_digest}",
        "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", *PROBE_TEST_SELECTORS,
    )


def _canonical_probe_command(argv: tuple[str, ...]) -> tuple[str, ...]:
    """Redact host-specific mount paths without conflating the two mounts."""

    canonical: list[str] = []
    for item in argv:
        if item.startswith("type=bind,") and "target=/workspace/backend/main.py" in item:
            canonical.append(
                "type=bind,source=<artifact-mount>,target=/workspace/backend/main.py,readonly"
            )
        elif item.startswith("type=bind,") and "target=/workspace" in item:
            canonical.append("type=bind,source=<repo-mount>,target=/workspace,readonly")
        else:
            canonical.append(item)
    return tuple(canonical)


def _run_fixed_probes(
    repo_root: Path,
    *,
    phase: str = "candidate",
    artifact_override: Path | None = None,
) -> tuple[list[dict[str, Any]], str]:
    if phase not in {"baseline", "candidate"}:
        raise CandidateRunError("probe phase must be baseline or candidate")
    argv = _probe_argv(repo_root, artifact_override=artifact_override)
    image_ref = next((item for item in argv if _IMMUTABLE_IMAGE.fullmatch(item)), None)
    if image_ref is None:
        raise CandidateRunError("probe command lacks an immutable Docker image reference")
    canonical_command = _canonical_probe_command(argv)
    command_digest = _digest(canonical_command)
    runs: list[dict[str, Any]] = []
    for index in range(PROBE_RUN_COUNT):
        started = time.monotonic()
        try:
            result = _run_process(argv, timeout=180.0)
            code: int | None = result.returncode
            output = (result.stdout + "\n" + result.stderr).encode("utf-8", errors="replace")
            failure = None
        except CandidateRunError as exc:
            code = None
            output = str(exc).encode("utf-8", errors="replace")
            failure = "infrastructure_error"
        runs.append({
            "phase": phase,
            "run": index + 1,
            "exit_code": code,
            "duration_ms": max(0, round((time.monotonic() - started) * 1000)),
            "output_digest": hashlib.sha256(output).hexdigest(),
            "passed": code == 0,
            "failure_kind": failure,
            "image_digest": image_ref.removeprefix("sha256:"),
            "command": list(canonical_command),
            "command_digest": command_digest,
        })
    return runs, command_digest


def _git_output(repo_root: Path, *arguments: str) -> bytes:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=repo_root,
            check=False,
            capture_output=True,
            timeout=30.0,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CandidateRunError("could not read immutable Git baseline evidence") from exc
    if result.returncode != 0 or not result.stdout:
        raise CandidateRunError("immutable Git baseline evidence is unavailable")
    return result.stdout


def _validated_git_commit_oid(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) not in {40, 64} or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise CandidateRunError("baseline source revision is not a full Git commit OID")
    return normalized


def _warm_runtime_baseline_bytes(repo_root: Path, source_revision: str) -> bytes:
    revision = _validated_git_commit_oid(source_revision)
    return _git_output(repo_root, "show", f"{revision}:backend/main.py")


def load_warm_runtime_baseline_artifact(
    repo_root: Path | None = None,
    *,
    source_revision: str | None = None,
) -> dict[str, str]:
    """Independently derive immutable baseline metadata from one full commit OID."""

    root = repo_root or Path(__file__).resolve().parents[1]
    requested_revision = source_revision or "HEAD"
    resolved = _git_output(
        root, "rev-parse", "--verify", f"{requested_revision}^{{commit}}"
    )
    try:
        resolved_revision = _validated_git_commit_oid(resolved.decode("ascii"))
    except UnicodeDecodeError as exc:
        raise CandidateRunError("Git baseline commit OID is not ASCII") from exc
    if source_revision is not None and resolved_revision != _validated_git_commit_oid(
        source_revision
    ):
        raise CandidateRunError("Git baseline revision did not resolve to the bound commit")
    artifact = _warm_runtime_baseline_bytes(root, resolved_revision)
    return {
        "artifact_path": "backend/main.py",
        "source_revision": resolved_revision,
        "artifact_digest": hashlib.sha256(artifact).hexdigest(),
    }


def _git_diff_evidence(repo_root: Path) -> dict[str, Any]:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        result = subprocess.run(
            ("git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", "backend/main.py"),
            cwd=repo_root, check=False, capture_output=True, timeout=30.0, creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CandidateRunError("could not resolve the concrete backend/main.py diff") from exc
    if result.returncode != 0:
        raise CandidateRunError("git could not resolve the concrete backend/main.py diff")
    return {
        "base": "HEAD",
        "artifact_path": "backend/main.py",
        "diff_digest": hashlib.sha256(result.stdout).hexdigest(),
        "diff_bytes": len(result.stdout),
    }


def _http_json(path: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    data = None if payload is None else _canonical_json(dict(payload)).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:11434{path}", data=data,
        headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600.0) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise CandidateRunError(f"trusted Ollama verification failed at {path}") from exc
    if not isinstance(value, Mapping):
        raise CandidateRunError(f"trusted Ollama verification returned malformed data at {path}")
    return value


def _verify_ollama_residency() -> dict[str, Any]:
    failure: str | None = None
    try:
        generated = _http_json("/api/generate", {
            "model": MODEL, "prompt": "Reply with READY.", "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"num_ctx": REQUESTED_CONTEXT, "num_predict": 1, "temperature": 0},
        })
        generation_done = generated.get("done") is True
        if not generation_done:
            failure = "generation_not_complete"
    except CandidateRunError as exc:
        generation_done = False
        failure = str(exc)

    observed_context = 0
    resident = False
    try:
        models = _http_json("/api/ps").get("models")
        if not isinstance(models, list):
            raise CandidateRunError("Ollama process status omitted models")
        for item in models:
            if isinstance(item, Mapping) and (item.get("name") == MODEL or item.get("model") == MODEL):
                resident = True
                try:
                    observed_context = int(item.get("context_length") or 0)
                except (TypeError, ValueError):
                    observed_context = 0
                break
    except CandidateRunError as exc:
        failure = failure or str(exc)

    observation = {
        "generation_done": generation_done,
        "resident": resident,
        "model": MODEL,
        "requested_context": REQUESTED_CONTEXT,
        "observed_context": observed_context,
        "keep_alive": KEEP_ALIVE,
        "verified": generation_done and resident and observed_context >= REQUESTED_CONTEXT,
        "failure": failure,
    }
    observation["observation_digest"] = _digest(observation)
    return observation



def _review_comparison(
    *,
    baseline_digest: str,
    source_digest: str,
    test_digest: str,
    baseline_runs: Sequence[Mapping[str, Any]],
    candidate_runs: Sequence[Mapping[str, Any]],
    required_probe_runs: int = PROBE_RUN_COUNT,
) -> dict[str, Any]:
    """Build a score only from the two freshly executed, digest-bound phases."""

    def observation(
        artifact_digest: str, runs: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        passed = sum(1 for run in runs if run.get("passed") is True)
        total = len(runs)
        return {
            "artifact_digest": artifact_digest,
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "score": passed / total if total else 0.0,
            "measurement_source": f"live-{required_probe_runs}-fixed-container-probes",
            "output_digest": _digest(list(runs)),
        }

    baseline = observation(baseline_digest, baseline_runs)
    candidate = observation(source_digest, candidate_runs)
    baseline_replayable = len(baseline_runs) == required_probe_runs and all(
        run.get("failure_kind") is None
        and not isinstance(run.get("exit_code"), bool)
        and isinstance(run.get("exit_code"), int)
        for run in baseline_runs
    )
    candidate_replayable = len(candidate_runs) == required_probe_runs and all(
        run.get("passed") is True
        and run.get("failure_kind") is None
        and not isinstance(run.get("exit_code"), bool)
        and run.get("exit_code") == 0
        for run in candidate_runs
    )
    improved = (
        baseline_replayable
        and candidate_replayable
        and candidate["score"] > baseline["score"]
    )
    comparison = {
        "status": (
            "paired-replayable"
            if baseline_replayable and candidate_replayable
            else "baseline-replay-failed"
            if not baseline_replayable
            else "candidate-replay-failed"
        ),
        "qualification": "measured-improvement" if improved else "no-measured-improvement",
        "suite": {
            "id": "warm-runtime-focused-contract-v1",
            "kind": "fixed-public-contract",
            "suite_digest": test_digest,
            "test_count": len(PROBE_TEST_SELECTORS),
            "heldout": False,
        },
        "baseline_replayable": baseline_replayable,
        "improved": improved,
        "retained_observations": {"baseline": baseline, "candidate": candidate},
        "current_candidate": candidate,
        "measurement_source": "live-paired-fixed-container-probes",
    }
    comparison["comparison_digest"] = _digest(comparison)
    return comparison


def _attestation_key() -> bytes:
    key = os.environ.get(ATTESTATION_KEY_ENV, "").encode("utf-8")
    if len(key) < 32:
        raise CandidateRunError(f"{ATTESTATION_KEY_ENV} must contain at least 32 bytes")
    return key


def _dsse_pae(payload_type: str, payload: bytes) -> bytes:
    kind = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" " + str(len(payload)).encode() + b" " + payload


def _sign_attestation(statement: Mapping[str, Any], key: bytes) -> dict[str, Any]:
    payload_type = "application/vnd.in-toto+json"
    payload = _canonical_json(dict(statement)).encode("utf-8")
    signature = hmac.new(key, _dsse_pae(payload_type, payload), hashlib.sha256).digest()
    envelope = {
        "payloadType": payload_type,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [{
            "keyid": hashlib.sha256(key).hexdigest()[:16],
            "sig": base64.b64encode(signature).decode("ascii"),
        }],
    }
    attestation = {
        "statement": dict(statement),
        "envelope": envelope,
        "statement_digest": hashlib.sha256(payload).hexdigest(),
        "signature": {
            "algorithm": "hmac-sha256",
            "value": hmac.new(key, payload, hashlib.sha256).hexdigest(),
        },
        "signer": "trusted-host-hmac-sha256",
        "claim_limit": "Binds recorded inputs and results; it does not prove their truth.",
    }
    attestation["attestation_digest"] = _digest(attestation)
    return attestation


def _validated_loop_binding(loop: Mapping[str, Any]) -> dict[str, str]:
    lineage = loop.get("candidate_lineage")
    values = {
        "proposal_id": loop.get("loop_id"),
        "baseline_digest": loop.get("baseline_digest"),
        "baseline_source_revision": (
            lineage.get("baseline_source_revision") if isinstance(lineage, Mapping) else None
        ),
        "baseline_artifact_digest": (
            lineage.get("baseline_artifact_digest") if isinstance(lineage, Mapping) else None
        ),
        "candidate_digest": lineage.get("candidate_digest") if isinstance(lineage, Mapping) else None,
    }
    if not isinstance(values["proposal_id"], str) or not values["proposal_id"].strip():
        raise CandidateRunError("candidate loop omitted its proposal id")
    values["baseline_source_revision"] = _validated_git_commit_oid(
        str(values["baseline_source_revision"] or "")
    )
    for name in ("baseline_digest", "baseline_artifact_digest", "candidate_digest"):
        if not isinstance(values[name], str) or _HEX_DIGEST.fullmatch(values[name]) is None:
            raise CandidateRunError(f"candidate loop has malformed {name}")
    return {name: str(value) for name, value in values.items()}


def run_improvement_candidate(candidate_kind: str, *, loop: Mapping[str, Any]) -> dict[str, Any]:
    """Run the sole allowlisted candidate and return host-built screening evidence."""

    if candidate_kind != CANDIDATE_KIND:
        raise UnsupportedCandidateError(f"unsupported improvement candidate: {candidate_kind}")
    if not isinstance(loop, Mapping):
        raise CandidateRunError("candidate loop must be an object")
    objective = loop.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        raise CandidateRunError("candidate loop omitted its warm-runtime objective")

    binding = _validated_loop_binding(loop)
    key = _attestation_key()
    repo_root = Path(__file__).resolve().parents[1]
    invocation_id = str(uuid.uuid4())
    lineage = loop.get("candidate_lineage")
    evidence_contract_version = (
        lineage.get("evidence_contract_version", 2)
        if isinstance(lineage, Mapping)
        else None
    )
    if evidence_contract_version != 2:
        raise CandidateRunError("candidate loop has an unsupported evidence contract")
    baseline_artifact = (
        lineage.get("baseline_artifact") if isinstance(lineage, Mapping) else None
    )
    if not isinstance(baseline_artifact, Mapping):
        raise CandidateRunError("loop omitted its replayable baseline artifact metadata")
    if set(baseline_artifact) != {
        "artifact_path", "source_revision", "artifact_digest",
    }:
        raise CandidateRunError("loop baseline artifact metadata is malformed")
    if (
        baseline_artifact.get("artifact_path") != "backend/main.py"
        or baseline_artifact.get("source_revision") != binding["baseline_source_revision"]
        or baseline_artifact.get("artifact_digest") != binding["baseline_artifact_digest"]
    ):
        raise CandidateRunError("loop baseline artifact metadata does not match its binding")
    derived_baseline = load_warm_runtime_baseline_artifact(
        repo_root, source_revision=binding["baseline_source_revision"]
    )
    if dict(baseline_artifact) != derived_baseline:
        raise CandidateRunError("loop baseline provenance does not match immutable Git bytes")
    baseline_bytes = _warm_runtime_baseline_bytes(
        repo_root, binding["baseline_source_revision"]
    )
    baseline_artifact_digest = hashlib.sha256(baseline_bytes).hexdigest()
    if baseline_artifact_digest != binding["baseline_artifact_digest"]:
        raise CandidateRunError("loop baseline digest does not match immutable Git bytes")
    try:
        candidate_bytes = (repo_root / "backend" / "main.py").read_bytes()
    except OSError as exc:
        raise CandidateRunError("candidate backend/main.py bytes are unavailable") from exc
    source_digest = hashlib.sha256(candidate_bytes).hexdigest()
    if binding["candidate_digest"] != source_digest:
        raise CandidateRunError("loop candidate digest does not match current backend/main.py bytes")
    if source_digest == baseline_artifact_digest:
        raise CandidateRunError("baseline and candidate artifacts must be distinct")
    diff = _git_diff_evidence(repo_root)
    test_file_digest = _file_digest(repo_root / PROBE_TEST_PATH)
    test_digest = _digest({
        "path": PROBE_TEST_PATH,
        "file_digest": test_file_digest,
        "selectors": list(PROBE_TEST_SELECTORS),
    })
    evaluator_digest = _file_digest(repo_root / "backend" / "improvement_evaluation.py")
    with tempfile.TemporaryDirectory(prefix=".obus-paired-", dir=repo_root) as directory:
        artifact_directory = Path(directory)
        baseline_path = artifact_directory / "baseline-main.py"
        candidate_path = artifact_directory / "candidate-main.py"
        baseline_path.write_bytes(baseline_bytes)
        candidate_path.write_bytes(candidate_bytes)
        # ABBA counterbalancing makes each arm occupy both early and late probe blocks.
        # It keeps the sealed probe command unchanged while limiting order drift.
        baseline_runs_first, baseline_command_digest = _run_fixed_probes(
            repo_root,
            phase="baseline",
            artifact_override=baseline_path,
        )
        candidate_runs_first, command_digest = _run_fixed_probes(
            repo_root,
            phase="candidate",
            artifact_override=candidate_path,
        )
        candidate_runs_second, candidate_second_command_digest = _run_fixed_probes(
            repo_root,
            phase="candidate",
            artifact_override=candidate_path,
        )
        baseline_runs_second, baseline_second_command_digest = _run_fixed_probes(
            repo_root,
            phase="baseline",
            artifact_override=baseline_path,
        )
    baseline_runs = [
        {**run, "run": index}
        for index, run in enumerate(
            [*baseline_runs_first, *baseline_runs_second], start=1
        )
    ]
    runs = [
        {**run, "run": index}
        for index, run in enumerate(
            [*candidate_runs_first, *candidate_runs_second], start=1
        )
    ]
    expected_probe_runs = PROBE_RUN_COUNT * 2
    arm_execution_blocks = (
        ("baseline", PROBE_RUN_COUNT),
        ("candidate", PROBE_RUN_COUNT),
        ("candidate", PROBE_RUN_COUNT),
        ("baseline", PROBE_RUN_COUNT),
    )
    if len({
        baseline_command_digest,
        command_digest,
        candidate_second_command_digest,
        baseline_second_command_digest,
    }) != 1:
        raise CandidateRunError("counterbalanced probes did not use the same sealed command manifest")
    for phase_runs, expected_command_digest in (
        (baseline_runs, baseline_command_digest),
        (runs, command_digest),
    ):
        if len(phase_runs) != expected_probe_runs or any(
            not isinstance(run.get("command"), list)
            or run.get("command_digest") != expected_command_digest
            or _digest(run["command"]) != expected_command_digest
            for run in phase_runs
        ):
            raise CandidateRunError(
                "probe command digest does not match the recorded canonical command"
            )
    if baseline_command_digest != command_digest:
        raise CandidateRunError("paired probes did not use the same sealed command manifest")
    image_digests = {
        str(run.get("image_digest")) for run in [*baseline_runs, *runs]
    }
    if len(image_digests) != 1 or not _HEX_DIGEST.fullmatch(next(iter(image_digests))):
        raise CandidateRunError("paired probe runs do not share one immutable Docker image digest")
    image_digest = next(iter(image_digests))
    harness_manifest = {
        "schema_version": 1,
        "candidate_kind": CANDIDATE_KIND,
        "sandbox_kind": "docker-network-none-read-only",
        "image_digest": image_digest,
        "executed_image_ref": f"sha256:{image_digest}",
        "command_digest": command_digest,
        "probe_runs": expected_probe_runs,
        "arm_execution_order": [arm for arm, _ in arm_execution_blocks],
        "probe_runs_per_block": PROBE_RUN_COUNT,
        "test_path": PROBE_TEST_PATH,
        "test_file_digest": test_file_digest,
        "test_selectors": list(PROBE_TEST_SELECTORS),
        "test_digest": test_digest,
        "evaluator_digest": evaluator_digest,
        "model": MODEL,
        "requested_context": REQUESTED_CONTEXT,
    }
    harness_manifest_digest = _digest(harness_manifest)
    baseline_manifest = {
        "schema_version": 1,
        "phase": "baseline",
        "artifact_path": "backend/main.py",
        "source_revision": binding["baseline_source_revision"],
        "artifact_digest": baseline_artifact_digest,
        "harness_manifest_digest": harness_manifest_digest,
    }
    candidate_manifest = {
        "schema_version": 1,
        "phase": "candidate",
        "artifact_path": "backend/main.py",
        "artifact_digest": source_digest,
        "harness_manifest_digest": harness_manifest_digest,
    }
    baseline_manifest_digest = _digest(baseline_manifest)
    candidate_manifest_digest = _digest(candidate_manifest)
    residency = _verify_ollama_residency()
    comparison = _review_comparison(
        baseline_digest=baseline_artifact_digest,
        source_digest=source_digest,
        test_digest=test_digest,
        baseline_runs=baseline_runs,
        candidate_runs=runs,
        required_probe_runs=expected_probe_runs,
    )

    evidence_summary = {
        "invocation_id": invocation_id,
        "evidence_contract_version": 2,
        "candidate_kind": CANDIDATE_KIND,
        "objective": objective.strip(),
        "artifact_path": "backend/main.py",
        "baseline_source_revision": binding["baseline_source_revision"],
        "baseline_artifact_digest": baseline_artifact_digest,
        "candidate_digest": source_digest,
        "source_digest": source_digest,
        "diff_digest": diff["diff_digest"],
        "diff_bytes": diff["diff_bytes"],
        "sandbox_kind": "docker-network-none-read-only",
        "image_digest": image_digest,
        "executed_image_ref": f"sha256:{image_digest}",
        "baseline_probe_runs": expected_probe_runs,
        "baseline_probe_passes": sum(1 for run in baseline_runs if run["passed"]),
        "probe_runs": expected_probe_runs,
        "probe_passes": sum(1 for run in runs if run["passed"]),
        "arm_execution_order": [arm for arm, _ in arm_execution_blocks],
        "model": MODEL,
        "requested_context": REQUESTED_CONTEXT,
        "observed_context": residency["observed_context"],
        "residency_verified": residency["verified"],
        "test_digest": test_digest,
        "test_file_digest": test_file_digest,
        "test_selectors": list(PROBE_TEST_SELECTORS),
        "evaluator_digest": evaluator_digest,
        "baseline_command_digest": baseline_command_digest,
        "command_digest": command_digest,
        "baseline_output_digest": _digest(baseline_runs),
        "output_digest": _digest(runs),
        "harness_manifest": harness_manifest,
        "harness_manifest_digest": harness_manifest_digest,
        "baseline_manifest": baseline_manifest,
        "baseline_manifest_digest": baseline_manifest_digest,
        "candidate_manifest": candidate_manifest,
        "candidate_manifest_digest": candidate_manifest_digest,
        "comparison": comparison,
        "comparison_digest": comparison["comparison_digest"],
        "residency_observation_digest": residency["observation_digest"],
    }
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": "backend/main.py", "digest": {"sha256": source_digest}},
            {
                "name": f"baseline:{binding['baseline_source_revision']}:backend/main.py",
                "digest": {"sha256": baseline_artifact_digest},
            },
        ],
        "predicateType": "https://obus.local/attestation/improvement-candidate/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": CANDIDATE_KIND,
                "externalParameters": {},
                "internalParameters": {
                    "objective": objective.strip(), "model": MODEL,
                    "requestedContext": REQUESTED_CONTEXT, "probeRuns": expected_probe_runs,
                    "armExecutionOrder": [arm for arm, _ in arm_execution_blocks],
                },
                "resolvedDependencies": [
                    {"uri": f"docker-image:sha256:{image_digest}", "digest": {"sha256": image_digest}},
                    {"uri": "file:backend/main.py", "digest": {"sha256": source_digest}},
                    {
                        "uri": f"baseline:{binding['baseline_source_revision']}:backend/main.py",
                        "digest": {"sha256": baseline_artifact_digest},
                    },
                    {
                        "uri": "manifest:paired-harness",
                        "digest": {"sha256": harness_manifest_digest},
                    },
                    {
                        "uri": "manifest:baseline-arm",
                        "digest": {"sha256": baseline_manifest_digest},
                    },
                    {
                        "uri": "manifest:candidate-arm",
                        "digest": {"sha256": candidate_manifest_digest},
                    },
                    {"uri": "git-diff:HEAD:backend/main.py", "digest": {"sha256": diff["diff_digest"]}},
                    {"uri": f"file:{PROBE_TEST_PATH}", "digest": {"sha256": test_file_digest}},
                {"uri": "test-suite:warm-runtime-focused-contract-v1", "digest": {"sha256": test_digest}},
                    {"uri": "file:backend/improvement_evaluation.py", "digest": {"sha256": evaluator_digest}},
                ],
            },
            "runDetails": {
                "builder": {"id": "https://obus.local/builders/trusted-host/v1"},
                "metadata": {"invocationId": invocation_id},
            },
            "binding": binding,
            "evidence": evidence_summary,
            "limitations": ["This attestation binds evidence; it does not prove that evidence is true."],
        },
    }
    attestation = _sign_attestation(statement, key)
    receipt = build_improvement_screening_receipt(
        binding=binding,
        evidence_summary=evidence_summary,
        attestation=attestation,
        baseline_artifact=baseline_artifact,
        baseline_probe_runs=baseline_runs,
        probe_runs=runs,
        residency=residency,
    )
    return {
        "candidate_kind": CANDIDATE_KIND,
        "receipt": receipt,
        "receipt_digest": _digest(receipt),
        "attestation": attestation,
        "attestation_digest": attestation["attestation_digest"],
        "evidence_summary": {field: evidence_summary[field] for field in _SAFE_EVIDENCE_FIELDS},
    }


__all__ = [
    "ATTESTATION_KEY_ENV", "CANDIDATE_KIND", "CandidateRunError",
    "UnsupportedCandidateError", "run_improvement_candidate",
]
