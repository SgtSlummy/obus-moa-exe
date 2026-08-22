"""
FastAPI Backend for OBus MOA Runtime
Supports Tarot cards, Solomon's Keys, Decks, and routing
"""
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
import json
import mimetypes
import math
import os
import re
from pathlib import Path
from typing import List, Optional
import asyncio
import base64
import copy
import html
import hashlib
import functools
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid

app = FastAPI(title="OBus MOA Runtime", version="1.0.0")

# Data storage paths
DATA_DIR = Path(os.environ.get('OCCULTBUS_HOME', Path.home() / '.occultbus'))
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = DATA_DIR / 'obus_state.json'
MEMORY_FILE = DATA_DIR / 'memory.json'
UI_BUILD = "obus-modern-8"
OLLAMA_URL = "http://127.0.0.1:11434"
MOA_ROUTER_ROOT = Path(os.environ.get("MOA_ROUTER_ROOT", Path.home() / "MoA-source"))
MOA_ROUTER_SCRIPT = MOA_ROUTER_ROOT / "moa_router.py"


# ==================== DECK ROUTING ====================

# Deck definitions based on cross-examination of optimal decks per task type
ALL_DECKS = [
    {
        "id": "rider-waite-smith",
        "name": "Rider–Waite–Smith",
        "symbol": "🃏",
        "description": "Classic deck with accessible archetypes. Broad coverage across all domains.",
        "style": "clear symbol archetypes, accessible language, broad coverage",
        "best_for": ["general_routing", "creative_briefs", "copywriting", "campaigns", "user_facing_strategy"],
        "image_pack": "/static/tarot/rws/",
        "enabled": True,
        "priority": 5
    },
    {
        "id": "thoth",
        "name": "Thoth",
        "symbol": "📚",
        "description": "Dense esoteric correspondences. Analytical, abstract, structural thinking.",
        "style": "dense esoteric correspondences, analytical, abstract, structural",
        "best_for": ["systems_architecture", "deep_analysis", "research_synthesis", "technical_planning", "multi_agent_decomposition"],
        "image_pack": "/static/tarot/thoth/",
        "enabled": True,
        "priority": 3
    },
    {
        "id": "marseille",
        "name": "Tarot de Marseille",
        "symbol": "♎",
        "description": "Historical minimalist design. Crisp archetypes, logical clarity.",
        "style": "minimalist, historical, crisp archetypes, logical",
        "best_for": ["logic_checks", "legal_policy_reasoning", "audit_trails", "simple_deterministic_decisions"],
        "image_pack": "/static/tarot/marseille/",
        "enabled": True,
        "priority": 4
    },
    {
        "id": "wild-unknown",
        "name": "Wild Unknown",
        "symbol": "🐾",
        "description": "Animal-centric visual style. Atmospheric, intuitive, symbolic artistic work.",
        "style": "visual, atmospheric, intuitive, symbolic",
        "best_for": ["visual_storyboards", "brand_moodboards", "emotion_led_creative_work", "narrative_tone"],
        "image_pack": "/static/tarot/wild-unknown/",
        "enabled": True,
        "priority": 2
    },
    {
        "id": "hermetic",
        "name": "Hermetic Tarot",
        "symbol": "🔺",
        "description": "Authoritative symbolism. Analytical, correspondence-driven esoteric reasoning.",
        "style": "symbol-dense, analytical, correspondence-driven, esoteric",
        "best_for": ["security_review", "threat_modeling", "occult_esoteric_research", "symbol_heavy_reasoning"],
        "image_pack": "/static/tarot/hermetic/",
        "enabled": True,
        "priority": 1
    },
    {
        "id": "golden-dawn",
        "name": "Golden Dawn",
        "symbol": "✶",
        "description": "Rich correspondences and color symbolism. Structured ceremonial logic, system mapping.",
        "style": "structured correspondences, ceremonial logic, system mapping, complex",
        "best_for": ["agent_orchestration", "ritualized_workflows", "complex_multi_step_planning", "classification"],
        "image_pack": "/static/tarot/golden-dawn/",
        "enabled": True,
        "priority": 2
    },
    {
        "id": "urban-tarot",
        "name": "Urban Tarot",
        "symbol": "🏙️",
        "description": "Modern urban aesthetic. Practical business contexts, startup scenarios.",
        "style": "contemporary, pragmatic, business, urban",
        "best_for": ["startup_planning", "product_launches", "market_positioning", "modern_business_scenarios"],
        "image_pack": "/static/tarot/urban/",
        "enabled": True,
        "priority": 3
    }
]

# Keyword mapping for auto-deck selection
DECK_KEYWORDS = {
    "hermetic": ["security", "attack", "threat", "security review", "audit", "vulnerability", "pentest", "risk", "occult", "esoteric", "symbol"],
    "thoth": ["architecture", "systems", "research synthesis", "planning", "decomposition", "technical", "deep", "intellectual", "abstract"],
    "marseille": ["logic", "legal", "policy", "compliance", "audit", "deterministic", "rational", "audit trail"],
    "wild-unknown": ["storyboard", "visual", "moodboard", "brand feel", "atmospheric", "intuitive", "narrative", "emotional"],
    "golden-dawn": ["orchestration", "workflow", "classification", "multi-step", "complex", "ceremonial", "agent"],
    "urban-tarot": ["startup", "product", "launch", "market", "business", "commercial", "scaling", "modern"],
    "rider-waite-smith": ["general", "brief", "campaign", "user", "client", "copy", "creative", "strategy"]
}


def select_deck_for_prompt(prompt: str) -> dict:
    """Auto-select the best deck based on prompt content"""
    prompt_lower = prompt.lower()
    
    for deck_id, keywords in DECK_KEYWORDS.items():
        if any(keyword in prompt_lower for keyword in keywords):
            return next((d for d in ALL_DECKS if d["id"] == deck_id), 
                       next((d for d in ALL_DECKS if d["id"] == "rider-waite-smith")))
    
    return next((d for d in ALL_DECKS if d["id"] == "rider-waite-smith"))


# ==================== TAROT CARDS ====================

from backend.card_catalog import DEFAULT_CARDS
from backend.forge_catalog import FORGE_NAME, PROJECTS, PROJECT_BY_ID
from backend.memory_hub import default_memory_hub


# ==================== SOLOMON'S KEYS ====================

def key_template(key_id: str, name: str, provider: str, model: str, base_url: str,
                 env_var: Optional[str], context: int, capabilities: list,
                 symbol: str = "🗝️", local: bool = False, aggregate: bool = False,
                 state: str = "staged") -> dict:
    return {"id": key_id, "name": name, "provider": provider, "model": model,
            "symbol": symbol, "base_url": base_url, "env_var": env_var,
            "oauth": False, "verified": local, "approved": local, "active": local,
            "can_aggregate": aggregate, "local": local, "state": state,
            "capabilities": capabilities, "max_context_tokens": context,
            "sigil": f"/static/art/keys/{key_id}.svg"}


DEFAULT_KEYS = [
    key_template("key-local-ollama", "Local Ollama", "ollama", "llama3.2:latest", "http://127.0.0.1:11434", None, 131072, ["coding", "tools", "reasoning", "analysis", "research", "synthesis"], "🔮", True, True, "ready"),
    key_template("key-codex-oauth", "Codex / OpenAI", "codex", "gpt-5.6-sol", "https://api.openai.com/v1", "OPENAI_API_KEY", 131072, ["coding", "tools", "analysis", "synthesis", "reasoning"], "✦", False, True),
    key_template("key-nous-oauth", "Nous / Solar", "nous", "upstage/solar-pro4:free", "https://api.upstage.com/v1", "NOUS_API_KEY", 131072, ["research", "analysis", "writing"], "☀️"),
    key_template("key-nvidia-nim", "NVIDIA NIM", "nvidia", "nvidia/nemotron-3-super-120b-a12b", "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", 131072, ["reasoning", "architecture", "planning", "tools"], "◈"),
    key_template("key-anthropic", "Anthropic", "anthropic", "claude-sonnet", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY", 200000, ["analysis", "writing", "coding", "reasoning"], "△"),
    key_template("key-google-gemini", "Google Gemini", "google", "gemini-pro", "https://generativelanguage.googleapis.com/v1beta", "GOOGLE_API_KEY", 1048576, ["multimodal", "analysis", "research", "coding"], "✺"),
    key_template("key-openrouter", "OpenRouter", "openrouter", "auto", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", 131072, ["routing", "analysis", "coding", "research"], "⌘"),
    key_template("key-mistral", "Mistral AI", "mistral", "mistral-large", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", 131072, ["coding", "reasoning", "multilingual"], "◇"),
    key_template("key-groq", "Groq", "groq", "llama", "https://api.groq.com/openai/v1", "GROQ_API_KEY", 131072, ["fast", "coding", "reasoning"], "⚡"),
    key_template("key-xai", "xAI", "xai", "grok", "https://api.x.ai/v1", "XAI_API_KEY", 131072, ["reasoning", "research", "tools"], "✕"),
    key_template("key-together", "Together AI", "together", "auto", "https://api.together.xyz/v1", "TOGETHER_API_KEY", 131072, ["open_models", "coding", "reasoning"], "⊕"),
    key_template("key-fireworks", "Fireworks AI", "fireworks", "auto", "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY", 131072, ["fast", "coding", "reasoning"], "✹"),
    key_template("key-deepseek", "DeepSeek", "deepseek", "deepseek-chat", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", 131072, ["coding", "reasoning", "math"], "⬡"),
    key_template("key-cerebras", "Cerebras", "cerebras", "llama", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", 131072, ["fast", "reasoning", "coding"], "◎"),
    key_template("key-huggingface", "Hugging Face", "huggingface", "inference", "https://api-inference.huggingface.co", "HF_TOKEN", 32768, ["open_models", "embeddings", "research"], "HF"),
    key_template("key-azure-openai", "Azure OpenAI", "azure", "deployment", "https://example.openai.azure.com", "AZURE_OPENAI_API_KEY", 131072, ["coding", "analysis", "enterprise"], "AZ")
]


# ==================== STATE MANAGEMENT ====================

def normalize_state(state: dict) -> dict:
    state = copy.deepcopy(state or {})
    existing_keys = {item.get("id"): item for item in state.get("keys", [])}
    merged_keys = []
    for template in DEFAULT_KEYS:
        value = copy.deepcopy(template)
        value.update(existing_keys.pop(template["id"], {}))
        value.setdefault("sigil", template["sigil"])
        value.setdefault("max_context_tokens", template["max_context_tokens"])
        value.setdefault("capabilities", template["capabilities"])
        value.setdefault("state", template["state"])
        merged_keys.append(value)
    for custom in existing_keys.values():
        custom.setdefault("max_context_tokens", 131072)
        custom.setdefault("capabilities", ["general"])
        custom.setdefault("state", "staged")
        custom.setdefault("sigil", f"/static/art/keys/{custom['id']}.svg")
        merged_keys.append(custom)
    state["keys"] = merged_keys

    existing_cards = {item.get("id"): item for item in state.get("cards", [])}
    merged_cards = []
    for template in DEFAULT_CARDS:
        value = copy.deepcopy(template)
        previous = existing_cards.pop(template["id"], {})
        value.update(previous)
        value["image"] = template["image"]
        if "assignment_mode" not in previous:
            value["assignment_mode"] = "auto"
            value["assigned_key_id"] = None
        merged_cards.append(value)
    merged_cards.extend(existing_cards.values())
    state["cards"] = merged_cards
    state.setdefault("aggregator_key_id", "key-codex-oauth")
    return state


def load_state() -> dict:
    """Load and migrate state without ever storing secret values."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return normalize_state(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass
    return normalize_state({})


def save_state(state: dict):
    """Save state to JSON file"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w', encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ==================== API MODELS ====================

class CardUpdate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    key_id: Optional[str] = None
    assignment_mode: Optional[str] = None
    reversed: Optional[bool] = None
    active: Optional[bool] = None
    capabilities: Optional[List[str]] = None
    can_aggregate: Optional[bool] = None


class KeyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    env_var: Optional[str] = None
    verified: Optional[bool] = None
    approved: Optional[bool] = None
    state: Optional[str] = None
    symbol: Optional[str] = None
    capabilities: Optional[List[str]] = None
    max_context_tokens: Optional[int] = None
    local: Optional[bool] = None
    can_aggregate: Optional[bool] = None


class KeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    provider: str
    model: str
    base_url: str
    env_var: Optional[str] = None
    state: str = "staged"
    symbol: str = "🗝️"
    capabilities: List[str] = ["general"]
    max_context_tokens: int = 131072
    local: bool = False
    can_aggregate: bool = False


class LoginRequest(BaseModel):
    provider: str
    token: Optional[str] = None
    url: Optional[str] = None


class SettingsUpdate(BaseModel):
    rag_enabled: Optional[bool] = None
    selected_model: Optional[str] = None
    selected_deck: Optional[str] = None


class RouteRequest(BaseModel):
    prompt: str
    deck_mode: Optional[str] = "auto"
    rag_enabled: Optional[bool] = True
    model: Optional[str] = None


class GitHubAppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    installation_id: str
    owner: str
    repo: str
    branch: str = "main"
    memory_path: str = "obus/memory.json"
    private_key_path: str
    app_slug: Optional[str] = None


class ForgeSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_ids: List[str]
    agent_ids: List[str]
    auto_assign: bool = True


def get_settings(state: Optional[dict] = None) -> dict:
    state = state or load_state()
    defaults = {
        "rag_enabled": True,
        "selected_model": "llama3.2:latest",
        "selected_deck": "auto",
    }
    defaults.update(state.get("settings", {}))
    return defaults


def get_memory() -> list:
    if not MEMORY_FILE.exists():
        return []
    try:
        value = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def get_memory_hub():
    """Build a fresh read-only view so tests and custom OBus homes stay scoped."""
    hub = default_memory_hub()
    hub.obus_memory = MEMORY_FILE
    return hub


def merge_memory_chunks(local: list, remote: list) -> list:
    """Merge shared memory deterministically; remote versions replace matching IDs."""
    ordered = []
    positions = {}
    for item in local + remote:
        if not isinstance(item, dict):
            continue
        identity = str(item.get("id") or hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest())
        value = copy.deepcopy(item)
        value.setdefault("id", identity)
        if identity in positions:
            ordered[positions[identity]] = value
        else:
            positions[identity] = len(ordered)
            ordered.append(value)
    return ordered


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def github_app_jwt(config: dict) -> str:
    """Create a short-lived GitHub App JWT from a referenced PEM file."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    key_path = Path(config["private_key_path"]).expanduser()
    if not key_path.is_file():
        raise RuntimeError(f"Private-key file not found: {key_path}")
    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": str(config["app_id"])}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64url(signature)}"


def github_json(url: str, method: str = "GET", token: Optional[str] = None, payload: Optional[dict] = None) -> dict:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "OBus-MOA"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def github_installation_token(config: dict) -> str:
    jwt = github_app_jwt(config)
    response = github_json(
        f"https://api.github.com/app/installations/{config['installation_id']}/access_tokens",
        method="POST", token=jwt, payload={},
    )
    token = response.get("token")
    if not token:
        raise RuntimeError("GitHub did not return an installation token")
    return token


def github_memory_get(config: dict, token: str) -> tuple[list, Optional[str]]:
    path = str(config.get("memory_path", "obus/memory.json")).lstrip("/")
    url = f"https://api.github.com/repos/{config['owner']}/{config['repo']}/contents/{path}?ref={config.get('branch', 'main')}"
    try:
        response = github_json(url, token=token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return [], None
        raise
    content = base64.b64decode(response.get("content", "")).decode("utf-8")
    document = json.loads(content)
    chunks = document.get("chunks", document if isinstance(document, list) else [])
    return chunks if isinstance(chunks, list) else [], response.get("sha")


def github_memory_put(config: dict, token: str, chunks: list, sha: Optional[str] = None) -> dict:
    path = str(config.get("memory_path", "obus/memory.json")).lstrip("/")
    url = f"https://api.github.com/repos/{config['owner']}/{config['repo']}/contents/{path}"
    document = {"version": 1, "updated_at": int(time.time()), "chunks": chunks}
    payload = {
        "message": "Sync OBus shared memory",
        "content": base64.b64encode(json.dumps(document, indent=2, ensure_ascii=False).encode("utf-8")).decode("ascii"),
        "branch": config.get("branch", "main"),
    }
    if sha:
        payload["sha"] = sha
    return github_json(url, method="PUT", token=token, payload=payload)


def codex_command(*args: str) -> Optional[list[str]]:
    local_root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes"
    native_candidates = list((local_root / "node" / "node_modules" / "@openai" / "codex" / "node_modules").glob("@openai/codex-*/vendor/*/bin/codex.exe"))
    bundled_candidate = local_root / "node" / "codex.cmd"
    executable = str(native_candidates[0]) if native_candidates else (shutil.which("codex.exe") or shutil.which("codex.cmd") or shutil.which("codex"))
    if not executable and bundled_candidate.is_file():
        executable = str(bundled_candidate)
    if not executable:
        return None
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", executable, *args]
    return [executable, *args]


def sanitize_auth_output(value: str) -> str:
    value = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)
    value = re.sub(r"(?i)(access[_ -]?token|authorization|bearer)\s*[:=]\s*\S+", r"\1: [REDACTED]", value)
    value = re.sub(r"\b(sk-[A-Za-z0-9_-]{12,}|gh[opusr]_[A-Za-z0-9_]{12,})\b", "[REDACTED]", value)
    return value[-8000:]


CODEX_DEVICE_URL = "https://auth.openai.com/codex/device"


def parse_codex_device_output(value: str) -> dict:
    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)
    url_match = re.search(r"https://auth\.openai\.com/codex/device(?:\?[^\s]*)?", clean)
    code_match = re.search(r"\b[A-Z0-9]{4}-[A-Z0-9]{5}", clean)
    return {
        "verification_url": url_match.group(0) if url_match else None,
        "user_code": code_match.group(0) if code_match else None,
    }


CODEX_LOGIN_JOBS: dict[str, dict] = {}
FORGE_INSTALL_JOBS: dict[str, dict] = {}


def run_codex_login(job_id: str) -> None:
    command = codex_command("login", "--device-auth")
    if not command:
        CODEX_LOGIN_JOBS[job_id].update(status="error", output="Codex CLI is not installed")
        return
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        CODEX_LOGIN_JOBS[job_id].update(pid=process.pid, status="running")
        lines = []
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)
            output = sanitize_auth_output("".join(lines))
            CODEX_LOGIN_JOBS[job_id]["output"] = output
            CODEX_LOGIN_JOBS[job_id].update(parse_codex_device_output(output))
        code = process.wait()
        CODEX_LOGIN_JOBS[job_id]["status"] = "complete" if code == 0 else "error"
        CODEX_LOGIN_JOBS[job_id]["return_code"] = code
    except Exception as exc:
        CODEX_LOGIN_JOBS[job_id].update(status="error", output=str(exc))


def find_local_binary(name: str) -> Optional[str]:
    candidates = [shutil.which(name), shutil.which(f"{name}.exe"), shutil.which(f"{name}.cmd")]
    local = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes"
    candidates.extend([
        str(local / "bin" / f"{name}.exe"), str(local / "node" / f"{name}.cmd"),
        str(Path.home() / ".local" / "bin" / f"{name}.exe"), str(Path.home() / ".local" / "bin" / name),
        str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / name / f"{name}.exe"),
    ])
    return next((value for value in candidates if value and Path(value).is_file()), None)


@functools.lru_cache(maxsize=32)
def isolated_import_status(module: str) -> tuple[bool, str]:
    integrations = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes" / "integrations"
    interpreters = [integrations / "python-libraries" / "Scripts" / "python.exe", DATA_DIR / "forge" / ".venv" / "Scripts" / "python.exe"]
    for interpreter in interpreters:
        if not interpreter.is_file():
            continue
        try:
            result = subprocess.run([str(interpreter), "-c", f"import {module}; print('ready')"], capture_output=True, text=True, timeout=45, encoding="utf-8", errors="replace")
            if result.returncode == 0:
                return True, str(interpreter)
        except Exception:
            pass
    return False, ""


def forge_project_status(project: dict) -> dict:
    binary = project.get("status_binary")
    path = find_local_binary(binary) if binary else None
    integrations = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes" / "integrations"
    source = integrations / "source" / project["repo"].replace("/", "__")
    evidence = []
    blocker = ""
    operational = False
    if path:
        status = "installed"
        operational = True
        evidence.append(f"binary: {path}")
    elif project["id"] in {"gptcache", "llmlingua", "outlines", "crewai"}:
        module = {"gptcache": "gptcache", "llmlingua": "llmlingua", "outlines": "outlines", "crewai": "crewai"}[project["id"]]
        ready, interpreter = isolated_import_status(module)
        status = "installed" if ready else "not_installed"
        operational = ready
        if ready:
            evidence.append(f"import {module}: {interpreter}")
        else:
            blocker = "Isolated Python import failed"
    elif project["id"] == "vllm":
        interpreter = integrations / "vllm" / "Scripts" / "python.exe"
        if interpreter.is_file():
            try:
                result = subprocess.run([str(interpreter), "-c", "import vllm,torch; print(vllm.__version__,torch.__version__,torch.cuda.is_available())"], capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
                evidence.append(f"native install: {result.stdout.strip()}")
            except Exception:
                pass
            status = "installed_blocked"
            blocker = "CUDA is unavailable in the native Windows vLLM environment; WSL2 or Docker is required"
        else:
            status = "external_setup"
            blocker = "WSL2 or Docker is required"
    elif project["id"] == "caveman" and (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes" / "skills" / "productivity" / "caveman").is_dir():
        status, operational = "installed", True
        evidence.append("Hermes Caveman skill suite")
    elif project["id"] == "ponytail-skills" and (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes" / "skills" / "software-development" / "karpathy-ponytail").is_dir():
        status, operational = "installed", True
        evidence.append("Hermes karpathy-ponytail skill")
    elif project["id"] == "oh-my-hermes" and (Path.home() / ".omh" / "skills").is_dir():
        status, operational = "installed", True
        evidence.append("Oh My Hermes skills and enabled OMH plugin")
    elif project["id"] == "superpowers":
        core = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes" / "skills" / "software-development"
        operational = all((core / name).is_dir() for name in ("systematic-debugging", "test-driven-development", "plan"))
        status = "partial" if operational else "source_ready"
        evidence.append("Adapted Superpowers core workflows" if operational else "Source clone only")
        blocker = "Full plugin blocked by Hermes security scan" if operational else "Security review required"
    elif project["integration"] in {"knowledge_catalog", "development_framework"}:
        status = "available"
        operational = project["integration"] == "knowledge_catalog"
        evidence.append("Source catalog available" if source.is_dir() else "Catalog metadata available")
    elif project["windows_mode"] in {"catalog_only", "no_install", "review_required", "manual_review", "plugin_review", "wsl_or_docker", "docker", "node_source"}:
        status = "source_ready" if source.is_dir() else "external_setup"
        blocker = {
            "wsl_or_docker": "WSL2 or Docker is required", "docker": "A healthy Docker Linux engine is required",
            "catalog_only": "Catalog-only; not an OBus runtime module", "no_install": "No installation is required",
            "review_required": "Plugin review is required", "manual_review": "Skill review is required",
            "plugin_review": "Plugin blocked or requires security review", "node_source": "Standalone source application; build and runtime review required",
        }.get(project["windows_mode"], "External setup required")
        if source.is_dir():
            evidence.append(f"source: {source}")
    else:
        status = "source_ready" if source.is_dir() else "not_installed"
        blocker = "Source is present but runtime integration is not verified" if source.is_dir() else "Not installed"
        if source.is_dir():
            evidence.append(f"source: {source}")
    return {**project, "status": status, "operational": operational, "evidence": evidence, "blocker": blocker, "binary_path": path, "source_present": source.is_dir()}


def forge_install_plan(project: dict) -> list[str]:
    if project.get("installer") == "uv_tool" and project.get("package"):
        return ["uv", "tool", "install", project["package"]]
    if project["integration"] == "python_library" and project.get("package"):
        venv_python = str(DATA_DIR / "forge" / ".venv" / "Scripts" / "python.exe")
        return ["uv", "pip", "install", "--python", venv_python, project["package"]]
    raise ValueError("This project requires external setup or review; no automatic install is allowed")


def run_forge_install(job_id: str, project_id: str) -> None:
    project = PROJECT_BY_ID[project_id]
    try:
        plan = forge_install_plan(project)
        uv = find_local_binary("uv")
        if not uv:
            raise RuntimeError("uv is not installed")
        if project["integration"] == "python_library":
            venv = DATA_DIR / "forge" / ".venv"
            if not (venv / "Scripts" / "python.exe").is_file():
                create = subprocess.run([uv, "venv", str(venv)], capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
                if create.returncode != 0:
                    raise RuntimeError(sanitize_auth_output((create.stdout or "") + (create.stderr or "")))
            command = [uv, *plan[1:]]
        else:
            command = [uv, *plan[1:]]
        FORGE_INSTALL_JOBS[job_id]["status"] = "running"
        result = subprocess.run(command, capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
        output = sanitize_auth_output((result.stdout or "") + (result.stderr or ""))
        FORGE_INSTALL_JOBS[job_id].update(status="complete" if result.returncode == 0 else "error", output=output, return_code=result.returncode)
    except Exception as exc:
        FORGE_INSTALL_JOBS[job_id].update(status="error", output=str(exc))


def get_ollama_status() -> dict:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = [item.get("name", "") for item in payload.get("models", [])]
        contexts = {
            item.get("name", ""): int(item.get("details", {}).get("context_length") or 0)
            for item in payload.get("models", [])
        }
        return {"connected": True, "models": models, "model_contexts": contexts, "url": OLLAMA_URL}
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"connected": False, "models": [], "model_contexts": {}, "url": OLLAMA_URL, "error": str(exc)}


def provider_statuses(state: Optional[dict] = None) -> list:
    state = state or load_state()
    ollama = get_ollama_status()
    providers = []
    for key in state.get("keys", DEFAULT_KEYS):
        configured = bool(key.get("local")) or bool(key.get("env_var") and os.getenv(key["env_var"]))
        connection_ok = ollama["connected"] if key.get("provider") == "ollama" else bool(key.get("verified") and configured)
        connected = bool(connection_ok and key.get("state", "staged") == "ready")
        context_tokens = int(key.get("max_context_tokens") or 131072)
        detected_context = ollama.get("model_contexts", {}).get(key.get("model")) if key.get("provider") == "ollama" else None
        if detected_context:
            context_tokens = detected_context
        providers.append({
            "id": key["id"],
            "name": key["name"],
            "provider": key["provider"],
            "model": key["model"],
            "symbol": key.get("symbol", "🗝️"),
            "sigil": key.get("sigil", f"/static/art/keys/{key['id']}.svg"),
            "base_url": key.get("base_url", ""),
            "env_var": key.get("env_var"),
            "state": key.get("state", "staged"),
            "capabilities": key.get("capabilities", []),
            "max_context_tokens": context_tokens,
            "configured": configured,
            "connected": connected,
            "status": "ready" if connected else ("configured" if configured else "not configured"),
            "local": bool(key.get("local")),
            "can_aggregate": bool(key.get("can_aggregate")),
        })
    return providers


# ==================== ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main SPA"""
    static_path = Path(__file__).parent / 'static' / 'index.html'
    if static_path.exists():
        return HTMLResponse(content=static_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>OBus UI Not Found</h1>", status_code=404)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "obus-moa"}


@app.get("/status")
async def status():
    """System status"""
    state = load_state()
    return {
        "cards": len(state.get("cards", [])),
        "keys": len(state.get("keys", [])),
        "verified_keys": len([k for k in state.get("keys", []) if k.get("verified")]),
        "active_assignments": len([c for c in state.get("cards", []) if c.get("active")]),
        "aggregator_key_id": state.get("aggregator_key_id"),
        "uptime": "00:00:00"
    }


@app.get("/api/dashboard")
async def dashboard():
    """Return live, secret-safe data used to render every dashboard component."""
    state = load_state()
    memory = get_memory()
    return {
        "build": UI_BUILD,
        "ollama": get_ollama_status(),
        "providers": provider_statuses(state),
        "cards": state.get("cards", DEFAULT_CARDS),
        "decks": [d for d in ALL_DECKS if d.get("enabled", True)],
        "settings": get_settings(state),
        "memory": {
            "chunks": len(memory),
            "characters": sum(len(str(item.get("text", ""))) for item in memory if isinstance(item, dict)),
        },
        "memory_hub": get_memory_hub().status(),
    }


@app.get("/api/integrations/memory")
async def memory_integrations():
    """Return secret-safe status for every discovered local memory system."""
    return get_memory_hub().status()


@app.get("/api/memory/search")
async def search_memory_hub(query: str, limit: int = 20):
    """Search local OBus, Hermes, and available Mem0 memory text."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    return {"query": query, "results": get_memory_hub().search(query, limit=limit)}


@app.put("/api/settings")
async def update_settings(update: SettingsUpdate):
    state = load_state()
    settings = get_settings(state)
    for field, value in update.model_dump(exclude_none=True).items():
        settings[field] = value
    state["settings"] = settings
    save_state(state)
    return settings


def safe_github_config(config: dict) -> dict:
    return {
        "configured": all(config.get(key) for key in ("app_id", "installation_id", "owner", "repo", "private_key_path")),
        "app_id": config.get("app_id", ""), "installation_id": config.get("installation_id", ""),
        "owner": config.get("owner", ""), "repo": config.get("repo", ""),
        "branch": config.get("branch", "main"), "memory_path": config.get("memory_path", "obus/memory.json"),
        "app_slug": config.get("app_slug"),
        "key_reference_configured": bool(config.get("private_key_path")),
        "key_file_exists": bool(config.get("private_key_path") and Path(config["private_key_path"]).expanduser().is_file()),
    }


@app.get("/api/integrations/github-app")
async def github_app_status():
    return safe_github_config(load_state().get("github_memory", {}))


@app.put("/api/integrations/github-app")
async def configure_github_app(update: GitHubAppConfig):
    value = update.model_dump()
    key_reference = value["private_key_path"]
    if "BEGIN " in key_reference.upper() or "\n" in key_reference or "\r" in key_reference:
        raise HTTPException(status_code=400, detail="Provide a private-key file path, never PEM content")
    if not value["app_id"].isdigit() or not value["installation_id"].isdigit():
        raise HTTPException(status_code=400, detail="App ID and installation ID must be numeric")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value["owner"]) or not re.fullmatch(r"[A-Za-z0-9_.-]+", value["repo"]):
        raise HTTPException(status_code=400, detail="Invalid GitHub owner or repository")
    memory_path = value["memory_path"].replace("\\", "/").lstrip("/")
    if ".." in memory_path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid memory path")
    value["memory_path"] = memory_path
    state = load_state()
    state["github_memory"] = value
    save_state(state)
    return safe_github_config(value)


@app.post("/api/integrations/github-app/test")
async def test_github_app():
    config = load_state().get("github_memory", {})
    if not safe_github_config(config)["configured"]:
        raise HTTPException(status_code=400, detail="Configure the GitHub App first")
    try:
        token = await asyncio.to_thread(github_installation_token, config)
        repo = await asyncio.to_thread(github_json, f"https://api.github.com/repos/{config['owner']}/{config['repo']}", "GET", token, None)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub App test failed: {exc}") from exc
    return {"success": True, "repository": repo.get("full_name", f"{config['owner']}/{config['repo']}")}


@app.post("/api/memory/github/push")
async def push_github_memory():
    config = load_state().get("github_memory", {})
    if not safe_github_config(config)["configured"]:
        raise HTTPException(status_code=400, detail="Configure the GitHub App first")
    try:
        token = await asyncio.to_thread(github_installation_token, config)
        remote, sha = await asyncio.to_thread(github_memory_get, config, token)
        merged = merge_memory_chunks(remote, get_memory())
        result = await asyncio.to_thread(github_memory_put, config, token, merged, sha)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub memory push failed: {exc}") from exc
    return {"success": True, "chunks": len(merged), "commit": result.get("commit", {}).get("sha")}


@app.post("/api/memory/github/pull")
async def pull_github_memory():
    config = load_state().get("github_memory", {})
    if not safe_github_config(config)["configured"]:
        raise HTTPException(status_code=400, detail="Configure the GitHub App first")
    try:
        token = await asyncio.to_thread(github_installation_token, config)
        remote, _ = await asyncio.to_thread(github_memory_get, config, token)
        merged = merge_memory_chunks(get_memory(), remote)
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub memory pull failed: {exc}") from exc
    return {"success": True, "chunks": len(merged)}


@app.get("/api/integrations/codex/status")
async def codex_status():
    command = codex_command("login", "status")
    if not command:
        return {"available": False, "logged_in": False, "message": "Codex CLI is not installed"}
    try:
        result = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        output = sanitize_auth_output((result.stdout or "") + (result.stderr or "")).strip()
        return {"available": True, "logged_in": result.returncode == 0, "message": output or "Codex login status checked"}
    except Exception as exc:
        return {"available": True, "logged_in": False, "message": str(exc)}


@app.post("/api/integrations/codex/login")
async def start_codex_login():
    if not codex_command("login", "--device-auth"):
        raise HTTPException(status_code=503, detail="Codex CLI is not installed")
    job_id = uuid.uuid4().hex
    CODEX_LOGIN_JOBS[job_id] = {"status": "starting", "output": "Starting Codex device login…", "verification_url": CODEX_DEVICE_URL, "user_code": None}
    threading.Thread(target=run_codex_login, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": "starting", "verification_url": CODEX_DEVICE_URL}


@app.get("/api/integrations/codex/login/{job_id}")
async def poll_codex_login(job_id: str):
    job = CODEX_LOGIN_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Login job not found")
    return {key: value for key, value in job.items() if key != "pid"}


@app.get("/api/forge/catalog")
async def forge_catalog():
    state = load_state()
    selected = set(state.get("forge", {}).get("selected_projects", []))
    projects = []
    for project in PROJECTS:
        value = forge_project_status(project)
        value["selected"] = project["id"] in selected
        value["installable"] = bool(project.get("installer") == "uv_tool" or (project["integration"] == "python_library" and project.get("package")))
        projects.append(value)
    return {"name": FORGE_NAME, "projects": projects, "selected_projects": sorted(selected), "selected_agents": state.get("forge", {}).get("agent_ids", []), "auto_assign": state.get("forge", {}).get("auto_assign", True)}


@app.put("/api/forge/selection")
async def update_forge_selection(update: ForgeSelection):
    unknown_projects = [value for value in update.project_ids if value not in PROJECT_BY_ID]
    if unknown_projects:
        raise HTTPException(status_code=400, detail=f"Unknown projects: {', '.join(unknown_projects)}")
    state = load_state()
    cards = {card["id"]: card for card in state["cards"]}
    unknown_agents = [value for value in update.agent_ids if value not in cards]
    if unknown_agents:
        raise HTTPException(status_code=400, detail=f"Unknown agents: {', '.join(unknown_agents)}")
    selected_projects = [PROJECT_BY_ID[value] for value in update.project_ids]
    cross_cutting = {"headroom", "gptcache", "llmlingua", "mempalace", "rtk", "codeburn"}
    assignments = {}
    for agent_id in update.agent_ids:
        card = cards[agent_id]
        card_caps = set(card.get("capabilities", []))
        tools = []
        for project in selected_projects:
            project_caps = set(project.get("capabilities", []))
            semantic_memory = project["category"] in {"memory", "rag"} and bool(card_caps & {"research", "analysis", "knowledge", "retrieval", "debugging"})
            compatible = bool(card_caps & project_caps) or semantic_memory or project["id"] in cross_cutting
            if compatible or not update.auto_assign:
                tools.append(project["id"])
        card["tool_ids"] = tools
        assignments[agent_id] = tools
    state["forge"] = {"name": FORGE_NAME, "selected_projects": list(dict.fromkeys(update.project_ids)), "agent_ids": update.agent_ids, "auto_assign": update.auto_assign}
    save_state(state)
    return {"name": FORGE_NAME, "selected_projects": state["forge"]["selected_projects"], "assignments": assignments}


@app.get("/api/forge/install/{project_id}/plan")
async def get_forge_install_plan(project_id: str):
    project = PROJECT_BY_ID.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        argv = forge_install_plan(project)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project": project_id, "argv": argv, "isolated": True}


@app.post("/api/forge/install/{project_id}")
async def start_forge_install(project_id: str):
    project = PROJECT_BY_ID.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        forge_install_plan(project)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job_id = uuid.uuid4().hex
    FORGE_INSTALL_JOBS[job_id] = {"status": "starting", "output": "Preparing isolated install…", "project_id": project_id}
    threading.Thread(target=run_forge_install, args=(job_id, project_id), daemon=True).start()
    return {"job_id": job_id, "status": "starting", "project_id": project_id}


@app.get("/api/forge/install/jobs/{job_id}")
async def poll_forge_install(job_id: str):
    job = FORGE_INSTALL_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Install job not found")
    return job


@app.get("/api/forge/recommend")
async def forge_recommend():
    recommended_ids = ["llmfit", "vllm", "gptcache", "llmlingua", "headroom", "rtk", "gortex", "mempalace", "outlines"]
    command = find_local_binary("llmfit")
    system = {"gpu": "NVIDIA RTX 3090 class", "vram_gb": 24, "ram_gb": 48}
    models = []
    if command:
        try:
            result = await asyncio.to_thread(subprocess.run, [command, "recommend", "--json"], capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
            payload = json.loads(result.stdout) if result.returncode == 0 else {}
            raw_system = payload.get("system", {})
            system = {
                "gpu": raw_system.get("gpu_name"), "vram_gb": raw_system.get("gpu_vram_gb"),
                "ram_gb": raw_system.get("total_ram_gb"), "backend": raw_system.get("backend"),
            }
            for model in payload.get("models", [])[:5]:
                models.append({key: model.get(key) for key in ("name", "best_quant", "estimated_tps", "memory_required_gb", "fit_label", "runtime", "context_length")})
        except Exception:
            pass
    return {
        "system": system, "models": models,
        "projects": [forge_project_status(PROJECT_BY_ID[value]) for value in recommended_ids],
        "architecture": [
            "Use LLMFit for model selection", "Run vLLM through WSL2 or Docker on Windows",
            "Add GPTCache and LLMLingua before inference", "Use Headroom/RTK/Gortex for context economy",
            "Use MemPalace for local shared memory", "Use Outlines for structured outputs",
        ],
    }


@app.get("/api/credits")
async def credits():
    """Return honest provider availability without inventing token balances."""
    return {
        item["id"]: {
            "status": item["status"],
            "connected": item["connected"],
            "remaining": None,
            "unlimited": item["local"],
        }
        for item in provider_statuses()
    }


@app.delete("/api/memory")
async def clear_memory():
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text("[]", encoding="utf-8")
    return {"success": True, "chunks": 0, "characters": 0}


@app.post("/api/providers/{key_id}/test")
async def test_provider(key_id: str):
    provider = next((item for item in provider_statuses() if item["id"] == key_id), None)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if provider["provider"] == "ollama":
        result = get_ollama_status()
        return {"success": result["connected"], **result}
    return {
        "success": provider["connected"],
        "connected": provider["connected"],
        "configured": provider["configured"],
        "message": ("Provider connection verified" if provider["connected"] else
                    "Authorization reference found but live provider is not verified" if provider["configured"] else
                    "Provider authorization is not configured"),
    }


# ==================== DECK ENDPOINTS ====================

@app.get("/api/decks")
async def get_decks():
    """Get all decks"""
    return [d for d in ALL_DECKS if d.get("enabled", True)]


@app.get("/api/decks/{deck_id}")
async def get_deck(deck_id: str):
    """Get a specific deck"""
    deck = next((d for d in ALL_DECKS if d["id"] == deck_id), None)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@app.put("/api/decks/{deck_id}")
async def update_deck(deck_id: str, update: dict = Body(...)):
    """Update a deck configuration"""
    for i, deck in enumerate(ALL_DECKS):
        if deck["id"] == deck_id:
            ALL_DECKS[i].update(update)
            return ALL_DECKS[i]
    raise HTTPException(status_code=404, detail="Deck not found")


# ==================== CARD ENDPOINTS ====================

@app.get("/api/cards")
async def get_cards():
    """Get all tarot cards"""
    state = load_state()
    cards = state.get("cards", DEFAULT_CARDS)
    
    # Get active assignments and key info
    for card in cards:
        key_id = card.get("assigned_key_id")
        key = next((k for k in state.get("keys", []) if k["id"] == key_id), None)
        card["key_name"] = key["name"] if key else "Unassigned"
        card["key_symbol"] = key["symbol"] if key else ""
    
    return cards


@app.post("/api/cards")
async def create_card(card: dict = Body(...)):
    """Create a new tarot card"""
    state = load_state()
    new_card = {
        "id": f"card-{len(state['cards']) + 1}",
        "name": card.get("name", "New Card"),
        "symbol": card.get("symbol", "🔮"),
        "persona": card.get("persona", "Agent"),
        "image": f"/static/tarot/{card.get('id', 'new')}.svg",
        "reversed": False,
        "active": False,
        "assigned_key_id": card.get("key_id"),
        "capabilities": card.get("capabilities", []),
        "can_aggregate": card.get("can_aggregate", False),
        "decks": card.get("decks", [])
    }
    state["cards"].append(new_card)
    save_state(state)
    return new_card


@app.put("/api/cards/{card_id}")
async def update_card(card_id: str, update: CardUpdate = Body(...)):
    """Update a tarot card"""
    state = load_state()
    card = next((c for c in state["cards"] if c["id"] == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    if update.name: card["name"] = update.name
    if update.symbol: card["symbol"] = update.symbol
    if update.assignment_mode is not None:
        if update.assignment_mode not in {"auto", "manual"}:
            raise HTTPException(status_code=400, detail="assignment_mode must be auto or manual")
        card["assignment_mode"] = update.assignment_mode
        if update.assignment_mode == "auto":
            card["assigned_key_id"] = None
    if update.key_id is not None:
        if not any(key["id"] == update.key_id for key in state["keys"]):
            raise HTTPException(status_code=404, detail="Key not found")
        card["assignment_mode"] = "manual"
        card["assigned_key_id"] = update.key_id
    if card.get("assignment_mode") == "manual" and not card.get("assigned_key_id"):
        raise HTTPException(status_code=400, detail="Manual pairing requires a Key")
    if update.reversed is not None: card["reversed"] = update.reversed
    if update.active is not None: card["active"] = update.active
    if update.capabilities: card["capabilities"] = update.capabilities
    if update.can_aggregate is not None: card["can_aggregate"] = update.can_aggregate
    
    save_state(state)
    return card


# ==================== KEY ENDPOINTS ====================

@app.post("/api/keys")
async def create_key(create: KeyCreate):
    """Create a reference-only Solomon's Key; raw credential values are forbidden."""
    if create.state not in {"ready", "staged", "disabled"}:
        raise HTTPException(status_code=400, detail="state must be ready, staged, or disabled")
    if create.max_context_tokens <= 0:
        raise HTTPException(status_code=400, detail="Context window must be positive")
    state = load_state()
    slug = re.sub(r"[^a-z0-9]+", "-", f"{create.provider}-{create.name}".lower()).strip("-") or "custom"
    base_id = f"key-{slug}"
    key_id = base_id
    suffix = 2
    ids = {item["id"] for item in state["keys"]}
    while key_id in ids:
        key_id = f"{base_id}-{suffix}"
        suffix += 1
    key = create.model_dump()
    key.update({
        "id": key_id, "oauth": False, "verified": bool(create.local),
        "approved": bool(create.local), "active": bool(create.local),
        "sigil": f"/api/keys/{key_id}/sigil.svg",
    })
    state["keys"].append(key)
    save_state(state)
    return key

@app.get("/api/keys")
async def get_keys():
    """Get all Solomon's keys"""
    state = load_state()
    return state.get("keys", DEFAULT_KEYS)


@app.put("/api/keys/{key_id}")
async def update_key(key_id: str, update: KeyUpdate = Body(...)):
    """Update a Solomon's key"""
    state = load_state()
    key = next((k for k in state["keys"] if k["id"] == key_id), None)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    changes = update.model_dump(exclude_unset=True)
    if changes.get("state") not in {None, "ready", "staged", "disabled"}:
        raise HTTPException(status_code=400, detail="state must be ready, staged, or disabled")
    if changes.get("max_context_tokens") is not None and changes["max_context_tokens"] <= 0:
        raise HTTPException(status_code=400, detail="Context window must be positive")
    key.update(changes)
    save_state(state)
    return key


@app.delete("/api/keys/{key_id}")
async def delete_key(key_id: str):
    state = load_state()
    before = len(state["keys"])
    state["keys"] = [key for key in state["keys"] if key["id"] != key_id]
    if len(state["keys"]) == before:
        raise HTTPException(status_code=404, detail="Key not found")
    for card in state["cards"]:
        if card.get("assigned_key_id") == key_id:
            card["assigned_key_id"] = None
            card["assignment_mode"] = "auto"
    if state.get("aggregator_key_id") == key_id:
        state["aggregator_key_id"] = "key-local-ollama"
    save_state(state)
    return {"success": True, "deleted": key_id}


@app.get("/api/keys/{key_id}/sigil.svg")
async def custom_key_sigil(key_id: str):
    key = next((item for item in load_state()["keys"] if item["id"] == key_id), None)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    seed = sum((index + 1) * ord(char) for index, char in enumerate(key_id))
    hue = seed % 360
    points = []
    for index in range(8):
        angle = (seed % 23 + index * 137.5) * math.pi / 180
        radius = 34 + ((seed >> (index % 8)) % 22)
        points.append(f"{100 + radius * math.cos(angle):.1f},{100 + radius * math.sin(angle):.1f}")
    provider_label = html.escape(str(key["provider"]).upper())
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><defs><radialGradient id="g"><stop stop-color="hsl({hue} 90% 65%)"/><stop offset="1" stop-color="#080b16"/></radialGradient></defs><rect width="200" height="200" rx="28" fill="#080b16"/><circle cx="100" cy="100" r="78" fill="url(#g)" opacity=".25" stroke="hsl({hue} 90% 70%)" stroke-width="2"/><circle cx="100" cy="100" r="58" fill="none" stroke="#f5c451"/><polygon points="{' '.join(points)}" fill="none" stroke="hsl({hue} 90% 75%)" stroke-width="3"/><path d="M58 100h84M100 58v84M70 70l60 60M130 70l-60 60" stroke="#f5c451" opacity=".75"/><circle cx="100" cy="100" r="9" fill="#f5c451"/><text x="100" y="181" text-anchor="middle" fill="#dce5ff" font-family="Segoe UI" font-size="10">{provider_label}</text></svg>'''
    return HTMLResponse(svg, media_type="image/svg+xml")


@app.post("/api/keys/{key_id}/verify")
async def verify_key(key_id: str):
    """Verify a Solomon's key"""
    state = load_state()
    key = next((k for k in state["keys"] if k["id"] == key_id), None)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    if key.get("env_var"):
        from os import getenv
        env_value = getenv(key["env_var"])
        if not env_value:
            return {"status": "missing_env", "message": f"Set environment variable {key['env_var']}"}
    
    key["verified"] = True
    key["approved"] = True
    save_state(state)
    
    return {"status": "success", "message": f"Key {key['name']} verified and approved"}


# ==================== AUTHENTICATION ====================

@app.post("/api/login")
async def login(req: LoginRequest):
    """Handle login for various providers"""
    state = load_state()
    
    if req.provider == "codex":
        key = next((k for k in state["keys"] if k["id"] == "key-codex-oauth"), None)
        if key:
            key["verified"] = True
            key["approved"] = True
            save_state(state)
            return {"success": True, "message": "Codex OAuth configured successfully", "key_id": "key-codex-oauth"}
    elif req.provider == "ollama":
        try:
            import urllib.request
            url = req.url or "http://localhost:11434"
            req_url = f"{url}/api/tags"
            urllib.request.urlopen(req_url, timeout=5)
            
            key = next((k for k in state["keys"] if k["id"] == "key-local-ollama"), None)
            if key:
                key["verified"] = True
                key["approved"] = True
                key["base_url"] = url
                key["active"] = True
                state["aggregator_key_id"] = "key-local-ollama"
                save_state(state)
                return {"success": True, "message": "Local Ollama connected successfully", "key_id": "key-local-ollama"}
        except Exception as e:
            return {"success": False, "message": f"Could not connect to Ollama: {str(e)}"}
    elif req.provider in ["nvidia", "nous"]:
        key_id_map = {"nvidia": "key-nvidia-nim", "nous": "key-nous-oauth"}
        if key_id_map.get(req.provider):
            key = next((k for k in state["keys"] if k["id"] == key_id_map[req.provider]), None)
            if key and req.token:
                key["verified"] = True
                key["approved"] = True
                save_state(state)
                return {"success": True, "message": f"{req.provider} configured successfully", "key_id": key_id_map[req.provider]}
    
    return {"success": False, "message": "Login failed or incomplete configuration"}


# ==================== AGGREGATOR ====================

@app.post("/api/aggregator/select")
async def select_aggregator(key_id: str = Body(..., embed=True)):
    """Select an aggregator key"""
    state = load_state()
    key = next((k for k in state["keys"] if k["id"] == key_id), None)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    if not key.get("can_aggregate"):
        raise HTTPException(status_code=400, detail="Key cannot be used as aggregator")
    
    state["aggregator_key_id"] = key_id
    save_state(state)
    return {"message": f"Aggregator set to {key['name']}"}


# ==================== ROUTING PLAN ====================

def select_cards_for_prompt(cards: list, prompt: str, limit: int = 5) -> list:
    words = set(re.findall(r"[a-z_]+", prompt.lower()))
    expansions = {
        "security": {"security", "threat_modeling", "risk", "adversarial"},
        "threat": {"security", "threat_modeling", "risk", "adversarial"},
        "incident": {"incident", "failure", "recovery", "debugging"},
        "debug": {"debugging", "analysis", "failure"},
        "research": {"research", "analysis", "investigation"},
        "code": {"coding", "building", "tools"},
        "creative": {"creative", "design", "narrative"},
        "legal": {"legal", "policy", "audit"},
    }
    task_caps = set(words)
    for word in words:
        task_caps.update(expansions.get(word, set()))
    scored = []
    for index, card in enumerate(cards):
        caps = set(card.get("capabilities", []))
        name_words = set(re.findall(r"[a-z_]+", f"{card.get('name', '')} {card.get('agent_type', '')}".lower()))
        score = len(task_caps & caps) * 5 + len(words & name_words) * 2
        if card.get("active"):
            score += 1
        scored.append((score, -index, card))
    scored.sort(reverse=True, key=lambda value: (value[0], value[1]))
    if scored and scored[0][0] == 0:
        return cards[:limit]
    return [value[2] for value in scored[:limit]]

def match_cards_to_keys(cards: list, state: dict, prompt: str) -> list:
    """Create temporary card-to-Key assignments from readiness and capability overlap."""
    statuses = {item["id"]: item for item in provider_statuses(state)}
    eligible = [
        key for key in state["keys"]
        if key.get("state", "staged") == "ready" and statuses.get(key["id"], {}).get("connected")
    ]
    if not eligible:
        return []
    prompt_words = set(re.findall(r"[a-z_]+", prompt.lower()))
    assignments = []
    use_counts = {key["id"]: 0 for key in eligible}
    for card in cards:
        chosen = None
        pairing = "auto"
        if card.get("assignment_mode") == "manual":
            chosen = next((key for key in eligible if key["id"] == card.get("assigned_key_id")), None)
            if chosen:
                pairing = "manual"
        if chosen is None:
            card_caps = set(card.get("capabilities", []))
            def score(key: dict) -> tuple:
                key_caps = set(key.get("capabilities", []))
                overlap = len(card_caps & key_caps)
                task_overlap = len(prompt_words & key_caps)
                diversity = -use_counts[key["id"]]
                return overlap * 4 + task_overlap * 2 + diversity, key.get("local", False)
            chosen = max(eligible, key=score)
        use_counts[chosen["id"]] += 1
        configured_tools = card.get("tool_ids", [])
        ready_tools = [tool_id for tool_id in configured_tools if tool_id in PROJECT_BY_ID and forge_project_status(PROJECT_BY_ID[tool_id]).get("operational")]
        assignments.append({
            "agent_id": card["id"], "agent_title": card["name"],
            "persona": card["persona"], "provider": chosen["name"],
            "model": chosen["model"], "llm_key": chosen["id"],
            "pairing_mode": pairing, "confidence": 1.0 if pairing == "manual" else 0.85,
            "active_in_deck": True, "capabilities": card.get("capabilities", []),
            "tool_ids": ready_tools,
            "configured_tool_ids": configured_tools,
            "max_context_tokens": chosen.get("max_context_tokens", 131072),
            "sigil": chosen.get("sigil"),
        })
    return assignments

@app.get("/api/plan")
async def plan_route(prompt: str, deck_mode: Optional[str] = None):
    """Get MOA routing plan with deck selection"""
    state = load_state()
    
    # Determine deck
    if deck_mode and deck_mode != "auto":
        deck = next((d for d in ALL_DECKS if d["id"] == deck_mode), None)
    else:
        deck = select_deck_for_prompt(prompt)
    if deck is None:
        raise HTTPException(status_code=400, detail="Unknown deck")
    
    # Get cards from selected deck
    deck_cards = [c for c in state["cards"] if deck["id"] in c.get("decks", [])]
    selected_cards = select_cards_for_prompt(deck_cards or state["cards"], prompt, limit=5)
    dynamic_assignments = match_cards_to_keys(selected_cards, state, prompt)
    ready_aggregators = [
        key for key in state["keys"]
        if key.get("can_aggregate") and key.get("state") == "ready"
        and next((status["connected"] for status in provider_statuses(state) if status["id"] == key["id"]), False)
    ]
    aggregator = next((key for key in ready_aggregators if key["id"] == state.get("aggregator_key_id")), None)
    if aggregator is None and ready_aggregators:
        aggregator = ready_aggregators[0]
    hub_results = get_memory_hub().search(prompt, limit=4)
    hub_characters = sum(len(str(item.get("text", ""))) for item in hub_results)
    
    return {
        "prompt": prompt,
        "selected_deck": {
            "id": deck["id"],
            "name": deck["name"],
            "symbol": deck["symbol"],
            "style": deck["style"],
            "best_for": deck["best_for"]
        },
        "moa": {
            "mode": "tarot-router",
            "dispatch": "parallel",
            "max_parallel": 20
        },
        "agents_task_capabilities": ["analysis", "research", "coding"],
        "agents": {
            "dynamic_assignments": dynamic_assignments,
            "aggregator": {
                "agent_id": "aggregator",
                "agent_title": "Synthesis (High Priestess)",
                "provider": aggregator["name"],
                "model": aggregator["model"],
                "llm_key": aggregator["id"],
                "max_context_tokens": aggregator.get("max_context_tokens", 131072),
            } if aggregator else None
        },
        "rag": {
            "enabled": True,
            "snippets": 4 + len(hub_results),
            "characters": 3200 + hub_characters,
            "source": "local_sqlite+memory_hub",
            "hub_results": hub_results,
        }
    }


@app.post("/api/route/plan")
async def plan_route_post(request: RouteRequest):
    """POST contract used by the desktop UI."""
    plan = await plan_route(request.prompt, request.deck_mode)
    plan["rag"]["enabled"] = bool(request.rag_enabled)
    return plan


def build_moa_router_command(prompt: str, model: str) -> Optional[list[str]]:
    """Build a local-only MoA subprocess command when the source router is present."""
    python_executable = os.environ.get("MOA_ROUTER_PYTHON") or shutil.which("python")
    if not python_executable or not MOA_ROUTER_SCRIPT.is_file():
        return None
    return [
        python_executable,
        str(MOA_ROUTER_SCRIPT),
        prompt,
        "--base-url", f"{OLLAMA_URL}/v1",
        "--models", ",".join([model, model, model]),
        "--aggregator", model,
        "--max-tokens", "512",
        "--temperature", "0",
        "--parallel-workers", "3",
    ]


def generate_with_moa_router(prompt: str, model: str, plan: dict) -> str:
    command = build_moa_router_command(prompt, model)
    if command is None:
        raise RuntimeError("Local MoA router is not installed")
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Local MoA router failed to start: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown router error").strip()[-1200:]
        raise RuntimeError(f"Local MoA router failed: {detail}")
    marker = "--- Routed answer ---"
    answer = result.stdout.split(marker, 1)[-1].strip() if marker in result.stdout else result.stdout.strip()
    if not answer:
        raise RuntimeError("Local MoA router returned an empty response")
    return answer


def generate_with_ollama(prompt: str, model: str, plan: dict) -> str:
    agent_names = ", ".join(
        item["agent_title"] for item in plan["agents"].get("dynamic_assignments", [])
    )
    deck = plan["selected_deck"]["name"]
    system_context = (
        "You are the OBus final local aggregator. Give a direct, useful answer. "
        f"The selected Tarot deck is {deck}; the specialist personas are {agent_names}."
    )
    request_body = json.dumps({
        "model": model,
        "prompt": f"{system_context}\n\nUser task:\n{prompt}",
        "stream": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama execution failed: {exc}") from exc
    answer = str(payload.get("response", "")).strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty response")
    return answer


@app.post("/api/route/run")
async def run_route(request: RouteRequest):
    """Execute the planned route through the selected local Ollama model."""
    plan = await plan_route(request.prompt, request.deck_mode)
    settings = get_settings()
    model = request.model or settings["selected_model"]
    if model not in get_ollama_status().get("models", []):
        raise HTTPException(status_code=503, detail=f"Ollama model is not installed: {model}")
    try:
        routed_prompt = request.prompt
        if request.rag_enabled and plan.get("rag", {}).get("hub_results"):
            memory_lines = "\n".join(
                f"- {item.get('source')}: {item.get('text', '')}"
                for item in plan["rag"]["hub_results"]
            )
            routed_prompt = f"{request.prompt}\n\nRelevant local memory context:\n{memory_lines}"
        moa_command = build_moa_router_command(routed_prompt, model)
        if moa_command is not None:
            answer = await asyncio.to_thread(generate_with_moa_router, routed_prompt, model, plan)
            engine = "local-moa-router"
        else:
            answer = await asyncio.to_thread(generate_with_ollama, routed_prompt, model, plan)
            engine = "ollama-single"
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "status": "complete",
        "engine": engine,
        "model": model,
        "selected_deck": plan["selected_deck"],
        "agents": plan["agents"],
        "final": answer,
    }


@app.post("/api/execute")
async def execute_task(payload: dict = Body(...)):
    """Execute task through MOA routing"""
    prompt = payload.get("prompt", "")
    deck_mode = payload.get("deck_mode", "auto")
    
    return {
        "task": prompt[:100] + "..." if len(prompt) > 100 else prompt,
        "status": "complete",
        "final": f"Task complete: {prompt[:50]}...",
        "reports": []
    }


@app.get("/api/assignments")
async def get_assignments():
    """Get current card-key assignments grouped by deck"""
    state = load_state()
    
    # Build groups
    groups = {}
    for card in state.get("cards", []):
        key_id = card.get("assigned_key_id")
        if key_id:
            if key_id not in groups:
                groups[key_id] = {"card": None, "keys": [], "deck": []}
            groups[key_id]["keys"].append(card)
            groups[key_id]["deck"] = card.get("decks", [])
    
    for key_id, info in list(groups.items()):
        key = next((k for k in state.get("keys", []) if k["id"] == key_id), None)
        if key:
            info["key"] = key
    
    return groups


# Python's Windows MIME registry can omit WebP; register it before StaticFiles.
mimetypes.add_type("image/webp", ".webp")
# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)