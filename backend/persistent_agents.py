"""Persistent OBus agent models, routing, provider adapters, and typed orchestration plans."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.process_utils import silent_process_kwargs

MAX_PERSISTENT_AGENTS = 30
MAX_AGENT_STEPS = 8
MAX_AGENT_HISTORY = 50
MAX_PARALLEL_AGENT_RUNS = 8

def normalized_room_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-") or "room"


CAPABILITY_TERMS = {
    "coding": {"code", "coding", "implement", "python", "javascript", "rust", "debug", "fix"},
    "research": {"research", "investigate", "find", "sources", "compare"},
    "analysis": {"analyze", "analysis", "evaluate", "review", "reason"},
    "security": {"security", "threat", "risk", "audit", "privacy", "safe"},
    "creative": {"creative", "design", "story", "visual", "campaign"},
    "planning": {"plan", "architecture", "strategy", "roadmap", "system"},
    "tools": {"tool", "execute", "run", "build", "operate"},
    "writing": {"write", "draft", "copy", "explain", "document"},
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersistentAgentCreate(StrictModel):
    name: Optional[str] = Field(default=None, max_length=120)
    card_id: Optional[str] = None
    objective: str = Field(min_length=1, max_length=12000)
    provider_mode: str = "auto"
    key_id: Optional[str] = None
    room_id: Optional[str] = None
    forum_thread_id: Optional[str] = None
    max_steps: int = Field(default=1, ge=1, le=MAX_AGENT_STEPS)
    auto_start: bool = False

    @field_validator("provider_mode")
    @classmethod
    def provider_mode_valid(cls, value: str) -> str:
        if value not in {"auto", "manual"}:
            raise ValueError("provider_mode must be auto or manual")
        return value


class PersistentAgentRunRequest(StrictModel):
    prompt: Optional[str] = Field(default=None, max_length=12000)


class RuntimeOrchestratorRequest(StrictModel):
    objective: str = Field(min_length=1, max_length=12000)
    max_agents: int = Field(default=6, ge=1, le=MAX_PERSISTENT_AGENTS)
    execute: bool = True


class OrchestratorAgentAction(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    card_id: str
    objective: str = Field(min_length=1, max_length=12000)
    max_steps: int = Field(default=1, ge=1, le=MAX_AGENT_STEPS)
    auto_start: bool = False


class OrchestratorRoomAction(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    card_ids: list[str] = Field(min_length=1, max_length=10)
    mode: str = "collaborative"
    prompt: str = Field(min_length=1, max_length=12000)
    run: bool = False

    @field_validator("card_ids")
    @classmethod
    def card_ids_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("card_ids must be unique")
        return value

    @field_validator("mode")
    @classmethod
    def mode_valid(cls, value: str) -> str:
        if value not in {"collaborative", "adversarial"}:
            raise ValueError("mode must be collaborative or adversarial")
        return value


class OrchestratorForumAction(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=12000)
    room_names: list[str] = Field(min_length=2, max_length=20)
    run: bool = False

    @field_validator("room_names")
    @classmethod
    def room_names_unique(cls, value: list[str]) -> list[str]:
        normalized = [normalized_room_name(item) for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("room_names must be unique after normalization")
        return value


class OrchestratorPlan(StrictModel):
    agents: list[OrchestratorAgentAction] = Field(default_factory=list, max_length=MAX_PERSISTENT_AGENTS)
    rooms: list[OrchestratorRoomAction] = Field(default_factory=list, max_length=20)
    forums: list[OrchestratorForumAction] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def room_names_unique(self):
        normalized = [normalized_room_name(room.name) for room in self.rooms]
        if len(normalized) != len(set(normalized)):
            raise ValueError("orchestrator room names must be unique")
        return self


def derive_task_capabilities(prompt: str) -> set[str]:
    words = set(re.findall(r"[a-z_]+", prompt.lower()))
    return {capability for capability, terms in CAPABILITY_TERMS.items() if words & terms}


def select_persistent_agent_key(card: dict[str, Any], prompt: str, state: dict[str, Any], statuses: dict[str, dict], key_loads: dict[str, int], manual_key_id: str | None = None, excluded: set[str] | None = None) -> dict[str, Any]:
    excluded = excluded or set()
    now = time.time()
    eligible = [
        key for key in state.get("keys", [])
        if key.get("id") not in excluded
        and key.get("state") == "ready"
        and statuses.get(key.get("id"), {}).get("connected")
        and float(key.get("cooldown_until") or 0) <= now
    ]
    if manual_key_id:
        chosen = next((key for key in eligible if key.get("id") == manual_key_id), None)
        if not chosen:
            raise RuntimeError(f"Requested Key is not ready and connected: {manual_key_id}")
        return chosen
    if not eligible:
        raise RuntimeError("No ready and connected Solomon Key is available")
    card_caps = set(card.get("capabilities", []))
    task_caps = derive_task_capabilities(prompt)
    prompt_words = set(re.findall(r"[a-z_]+", prompt.lower()))

    def score(key: dict[str, Any]) -> tuple[float, int, int]:
        caps = set(key.get("capabilities", []))
        overlap = len(card_caps & caps) * 5 + len(task_caps & caps) * 7 + len(prompt_words & caps) * 2
        quality = 8 if not key.get("local") else 0
        context = min(int(key.get("max_context_tokens", 0)) // 65536, 4)
        load_penalty = int(key_loads.get(key["id"], 0)) * 6
        return overlap + quality + context - load_penalty, -int(key_loads.get(key["id"], 0)), int(not key.get("local"))

    return max(eligible, key=score)


def extract_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S | re.I)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        candidate = text[start:end + 1] if start >= 0 and end > start else ""
    value = json.loads(candidate)
    if not isinstance(value, dict):
        raise ValueError("Orchestrator output must be a JSON object")
    return value


def parse_orchestrator_plan(raw: str, max_agents: int) -> OrchestratorPlan:
    data = extract_json_object(raw)
    agents = data.get("agents", []) if isinstance(data.get("agents", []), list) else []
    for agent in agents:
        if isinstance(agent, dict):
            try:
                agent["max_steps"] = max(1, min(MAX_AGENT_STEPS, int(agent.get("max_steps", 1))))
            except (TypeError, ValueError):
                agent["max_steps"] = 1
    plan = OrchestratorPlan.model_validate(data)
    if len(plan.agents) > max_agents:
        raise ValueError(f"Orchestrator requested {len(plan.agents)} agents; maximum for this request is {max_agents}")
    return plan


def _chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def _http_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "OBus-Persistent-Agent/1.0", **headers}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def execute_remote_provider(key: dict[str, Any], prompt: str) -> str:
    provider = str(key.get("provider", "")).lower()
    env_var = key.get("env_var")
    secret = os.getenv(env_var) if env_var else None
    if not secret:
        raise RuntimeError(f"Authorization reference is unavailable: {env_var or 'not configured'}")
    model = str(key.get("model") or "")
    base_url = str(key.get("base_url") or "").rstrip("/")
    if provider == "anthropic":
        result = _http_json(base_url + "/messages", {"x-api-key": secret, "anthropic-version": "2023-06-01"}, {"model": model, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]})
        return "\n".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text").strip()
    if provider in {"google", "gemini"}:
        url = base_url + f"/models/{urllib.parse.quote(model, safe='')}:generateContent"
        result = _http_json(url, {"x-goog-api-key": secret}, {"contents": [{"parts": [{"text": prompt}]}]})
        return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    if provider == "huggingface":
        url = base_url + "/models/" + urllib.parse.quote(model, safe="/")
        result = _http_json(url, {"Authorization": f"Bearer {secret}"}, {"inputs": prompt, "parameters": {"max_new_tokens": 1024}})
        if isinstance(result, list):
            return str(result[0].get("generated_text", "")).strip()
        return str(result.get("generated_text", "")).strip()
    if provider == "azure":
        url = base_url + f"/openai/deployments/{urllib.parse.quote(model, safe='')}/chat/completions?api-version=2024-10-21"
        result = _http_json(url, {"api-key": secret}, {"messages": [{"role": "user", "content": prompt}], "max_tokens": 2048})
    else:
        result = _http_json(_chat_url(base_url), {"Authorization": f"Bearer {secret}"}, {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2048})
    return str(result.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()


def execute_codex_prompt(command_builder: Callable[..., list[str] | None], key: dict[str, Any], prompt: str, workdir: Path) -> str:
    command = command_builder("exec", "--skip-git-repo-check", "--ephemeral", "--ignore-rules", "--sandbox", "read-only", "--color", "never", "-m", str(key.get("model") or ""))
    if not command:
        raise RuntimeError("Codex CLI is not installed")
    workdir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="obus-agent-", suffix=".txt", delete=False, dir=workdir) as temp:
        output_path = Path(temp.name)
    command.extend(["--output-last-message", str(output_path), prompt])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, cwd=workdir, encoding="utf-8", errors="replace", **silent_process_kwargs())
        output = output_path.read_text(encoding="utf-8", errors="replace").strip() if output_path.exists() else ""
        if result.returncode != 0 or not output:
            raise RuntimeError("Codex execution failed")
        return output
    finally:
        output_path.unlink(missing_ok=True)
