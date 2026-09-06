"""Private Obus game agent. Run: python -m uvicorn backend.game_agent:app --host 127.0.0.1 --port 38175.

Obus owns every model call, scoped retrieval and routing decision here. This
service shares the existing Obus catalogue; it does not restart the dashboard.
"""
from __future__ import annotations
from contextlib import contextmanager
import asyncio
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading
import urllib.request
import uuid
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from backend.persistent_agents import _http_json, _NO_REDIRECT_OPENER, _validated_provider_base_url, execute_remote_provider
from backend.game_runtime import GameRuntimeAuthority, RuntimeDenied

CONTRACT = 'raph-obus-game-v1'
STT_CONTRACT = 'raph-obus-game-stt-v1'
RUNTIME_CONTRACT = 'raph-obus-game-runtime-v1'
ROOT = Path(os.environ.get('OBUS_GAME_DATA_DIR', Path.home() / '.occultbus' / 'game-agent'))
CORE = os.environ.get('OBUS_GAME_CORE_URL', 'http://127.0.0.1:38173').rstrip('/')
LOCK = threading.RLock()
INFERENCE = threading.Lock()
STT_LOCK = threading.Lock()
STT_REQUESTS = threading.Lock()
STT_MODEL = None
STT_MODEL_PATH = ""
MAX_STT_AUDIO_BYTES = 6_000_000
RUNTIME: GameRuntimeAuthority | None = None


def runtime_authority() -> GameRuntimeAuthority:
    global RUNTIME
    if RUNTIME is None or RUNTIME.root != ROOT:
        RUNTIME = GameRuntimeAuthority(ROOT)
    return RUNTIME

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')
class Scope(Strict):
    campaign: str = Field(min_length=1, max_length=100)
    owner: str = Field(min_length=1, max_length=100)
    role: Literal['host', 'player']
class Policy(Strict):
    mode: Literal['local', 'local-free'] = 'local-free'
    codex: bool = False
    exportable: bool = False
    escalationEligible: bool = False
    namespace: str = Field(min_length=1, max_length=100)
    tools: Literal[False] = False
    personal_memory: Literal[False] = False
    auto_memory: Literal[False] = False
class RuntimeFence(Strict):
    contract: Literal['raph-obus-game-runtime-v1']
    bootEpoch: str
    generation: str
    sessionPolicyRevision: int = Field(ge=0)
class Job(Strict):
    contract: Literal['raph-obus-game-v1']
    scope: Scope
    session: str = Field(min_length=1, max_length=100)
    requestId: str = Field(min_length=1, max_length=100)
    task: Literal['narration','dialogue','intent','summary','final','council','counsel','prepare','contradiction','cue']
    instructions: str = Field(max_length=8000)
    evidence: dict | list
    policy: Policy
    runtime: RuntimeFence
    max_tokens: int = Field(default=900, ge=16, le=6000)
class Source(Strict):
    campaign: str = Field(min_length=1, max_length=100)
    ref: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=0)
    audience: Literal['party','host','private']
    owner: str = Field(default='', max_length=100)
    text: str = Field(max_length=16000)
    provenance: str = Field(min_length=1, max_length=160)
    exportable: bool = False
    deleted: bool = False


def token():
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / 'service-token'
    try:
        with path.open('x', encoding='utf-8') as handle:
            handle.write(secrets.token_hex(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except FileExistsError:
        pass
    return path.read_text(encoding='utf-8').strip()

@contextmanager
def database():
    ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ROOT / 'game.sqlite', timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript('CREATE TABLE IF NOT EXISTS sources(campaign TEXT,ref TEXT,revision INTEGER,audience TEXT,owner TEXT,exportable INTEGER,body TEXT,PRIMARY KEY(campaign,ref)); CREATE TABLE IF NOT EXISTS game_jobs(campaign TEXT,session TEXT,owner TEXT,request TEXT,fingerprint TEXT,body TEXT,PRIMARY KEY(campaign,session,owner,request)); CREATE TABLE IF NOT EXISTS stt_jobs(campaign TEXT,session TEXT,owner TEXT,request TEXT,fingerprint TEXT,body TEXT,PRIMARY KEY(campaign,session,owner,request));')
    try:
        with db:
            yield db
    finally:
        db.close()

def ingest(source: Source):
    with LOCK, database() as db:
        old = db.execute('SELECT revision FROM sources WHERE campaign=? AND ref=?', (source.campaign, source.ref)).fetchone()
        if old and old['revision'] > source.revision:
            return
        # Tombstones preserve the revision guard against late source updates.
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?) ON CONFLICT(campaign,ref) DO UPDATE SET revision=excluded.revision,audience=excluded.audience,owner=excluded.owner,exportable=excluded.exportable,body=excluded.body', (source.campaign, source.ref, source.revision, source.audience, source.owner, int(source.exportable), source.model_dump_json()))

def retrieve(scope: Scope, query: str):
    import re
    words = set(re.findall(r'\w{3,}', query.lower()))
    with LOCK, database() as db:
        rows = db.execute("SELECT body FROM sources WHERE campaign=? AND (audience='party' OR (audience='host' AND ?='host') OR (audience='private' AND owner=?))", (scope.campaign, scope.role, scope.owner)).fetchall()
    eligible = [json.loads(row['body']) for row in rows]
    ranked = sorted((s for s in eligible if not s['deleted']), key=lambda s: (-sum(w in s['text'].lower() for w in words), s['ref']))
    out, budget = [], 5000
    for s in ranked:
        if not any(w in s['text'].lower() for w in words):
            continue
        text = s['text'][:budget]
        if not text or len(out) == 6:
            break
        out.append({**s, 'text': text})
        budget -= len(text)
    return out

def catalogue():
    req = urllib.request.Request(CORE + '/api/dashboard')
    if os.environ.get('OBUS_ACCESS_TOKEN'):
        req.add_header('X-OBus-Access', os.environ['OBUS_ACCESS_TOKEN'])
    with _NO_REDIRECT_OPENER.open(req, timeout=10) as response:
        raw = response.read(1000001)
    if len(raw) > 1000000:
        raise RuntimeError('Obus catalogue too large')
    return json.loads(raw).get('providers', [])

def approved_free(keys):
    # Explicit Obus operator attestations pin a concrete provider/model/endpoint.
    # Generic OmniRoute auto/best-free and coding-agent proxies are NOT proof of
    # zero-cost, tool-free, destination-restricted execution.
    path = ROOT / 'free-routes.json'
    if not path.exists():
        return []
    configured = json.loads(path.read_text(encoding='utf-8'))
    result = []
    for pin in configured if isinstance(configured, list) else []:
        if pin.get('zero_charge') is not True or pin.get('no_fallback') is not True or pin.get('no_tools') is not True:
            continue
        for key in keys:
            if all(key.get(k) == pin.get(k) for k in ['id','provider','model','base_url']) and key.get('connected') and key.get('verified'):
                try:
                    _validated_provider_base_url(key['provider'], key['base_url'])
                    if key['provider'] not in {'codex','ollama'}:
                        result.append(key)
                except RuntimeError:
                    pass
    return result

def complete_local(key, prompt, maximum):
    base = _validated_provider_base_url('ollama', key['base_url'])
    if urllib.parse.urlsplit(base).hostname not in {'127.0.0.1','localhost','::1'}:
        raise RuntimeError('Local provider is not loopback')
    result = _http_json(base + '/api/chat', {}, {'model': key['model'], 'stream': False, 'think': False,
        'messages': [{'role': 'system', 'content': 'You are the Obus Raphael game agent. Use supplied authorized evidence only. Do not execute tools or decide mechanical outcomes.'}, {'role':'user','content':prompt}],
        'options': {'num_ctx':8192,'num_predict':maximum,'temperature':0.3}, 'keep_alive':'5m'}, timeout=90)
    if result.get('message', {}).get('tool_calls'):
        raise RuntimeError('Tool response not allowed')
    return result.get('message', {}).get('content', '')

def _require_runtime(campaign: str, session: str, fence: RuntimeFence) -> None:
    snapshot = runtime_authority().snapshot(campaign, session)
    if not snapshot.generation:
        raise HTTPException(409, "runtime_host_generation_required")
    if (snapshot.boot_epoch, snapshot.generation, snapshot.policy_revision) != (fence.bootEpoch, fence.generation, fence.sessionPolicyRevision):
        raise HTTPException(409, "runtime_fence_stale")
    if not snapshot.enabled:
        raise HTTPException(409, "game_ai_disabled")
    if snapshot.mode != "local" or snapshot.codex or snapshot.exportable:
        raise HTTPException(409, "runtime_policy_not_local_only")


async def _host_control_async(request: Request, action) -> dict:
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "runtime_body_invalid") from None
    if not isinstance(body, dict):
        raise HTTPException(400, "runtime_body_invalid")
    authority = runtime_authority()
    try:
        authority.verify_host(request.method, request.url.path, body, request.headers)
        return await asyncio.to_thread(action, body)
    except RuntimeDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


def run_job(job: Job, get_keys=catalogue, local=complete_local, remote=execute_remote_provider):
    if job.policy.codex:
        raise HTTPException(409, 'Codex escalation is not supported by this game agent')
    _require_runtime(job.scope.campaign, job.session, job.runtime)
    if job.policy.mode != 'local' or job.policy.exportable:
        raise HTTPException(409, 'runtime policy permits local-only dispatch')
    if job.policy.namespace != job.scope.campaign or len(json.dumps(job.evidence)) > 50000:
        raise HTTPException(400, 'Invalid campaign evidence')
    fingerprint = hashlib.sha256(job.model_dump_json().encode()).hexdigest()
    identity = (job.scope.campaign, job.session, job.scope.owner, job.requestId)
    with INFERENCE:
        with database() as db:
            prior = db.execute('SELECT fingerprint,body FROM game_jobs WHERE campaign=? AND session=? AND owner=? AND request=?', identity).fetchone()
        if prior:
            if prior['fingerprint'] != fingerprint:
                raise HTTPException(409, 'Request ID conflict')
            return json.loads(prior['body'])
        sources = retrieve(job.scope, str(job.evidence.get('question','')) if isinstance(job.evidence,dict) else job.task)
        prompt = json.dumps({'task':job.task,'instructions':job.instructions,'evidence':job.evidence,'retrieved':sources}, ensure_ascii=False)
        _require_runtime(job.scope.campaign, job.session, job.runtime)
        keys = get_keys()
        locals_ = [k for k in keys if k.get('id') == 'key-local-ollama' and k.get('provider') == 'ollama' and k.get('connected') and k.get('verified')]
        routes = [(k, 'local') for k in locals_]
        if job.policy.mode == 'local-free' and job.policy.exportable and all(s['exportable'] for s in sources):
            routes += [(k,'free') for k in approved_free(keys)]
        # Existing Codex CLI adapter can execute read-only tools; it is excluded
        # until Obus has a proven tool-free inference adapter. Logged-in != safe.
        trace, text, selected = [], '', None
        for key, destination in routes:
            for attempt in range(2 if destination == 'local' else 1):
                stage = {'provider':key['id'],'model':key['model'],'destination':destination,'cost':'zero' if destination == 'free' else 'local','attempt':attempt+1}
                _require_runtime(job.scope.campaign, job.session, job.runtime)
                try:
                    text = local(key,prompt,job.max_tokens) if destination == 'local' else remote(key,prompt)
                    if not isinstance(text,str) or not text.strip() or len(text)>16000 or '<script' in text.lower():
                        raise RuntimeError('Invalid output')
                    stage['status']='ready'; trace.append(stage); selected=key; break
                except Exception:
                    stage['status']='failed'; trace.append(stage); text=''
            if text:
                break
        if not text:
            raise HTTPException(503, 'No eligible Obus game provider completed the request')
        # A master-policy or session-fence change during inference cannot allow a
        # late result to become a durable receipt.
        _require_runtime(job.scope.campaign, job.session, job.runtime)
        result={'text':text.strip(),'routeId':str(uuid.uuid4()),'model':selected['model'],'trace':trace,'sources':[{'ref':s['ref'],'revision':s['revision']} for s in sources], 'retention': {'request_evidence_persisted': False, 'general_memory_writes': False, 'route_journal_writes': False, 'game_receipt_persisted': True}}
        with database() as db:
            db.execute('INSERT INTO game_jobs VALUES(?,?,?,?,?,?)', (*identity,fingerprint,json.dumps(result)))
        return result

def _game_stt_model_path() -> Path:
    configured = str(os.environ.get("OBUS_GAME_STT_MODEL_PATH") or "").strip()
    return Path(configured) if configured else ROOT / "models" / "faster-whisper-tiny"


def local_stt_status() -> dict[str, object]:
    model_path = _game_stt_model_path()
    try:
        import faster_whisper  # noqa: F401
        dependency_available = True
    except ImportError:
        dependency_available = False
    model_available = (model_path / "model.bin").is_file() and (model_path / "config.json").is_file()
    return {
        "mode": "local-only",
        "engine": "faster-whisper",
        "dependency_available": dependency_available,
        "model_available": model_available,
        "ready": dependency_available and model_available,
        "model_source": "OBUS_GAME_STT_MODEL_PATH" if os.environ.get("OBUS_GAME_STT_MODEL_PATH") else "private-game-data",
        "runtime_envelope_required": True,
        "route_ready": False,
        "reason": "Scoped STT dispatch requires an active private game-host runtime lease.",
    }


def _scoped_stt_audio(body: object) -> bytes:
    required = {"contract", "scope", "session", "requestId", "runtime", "audio_base64", "mime_type"}
    if not isinstance(body, dict) or set(body) != required:
        raise HTTPException(400, "Scoped STT v1 envelope required")
    scope = body.get("scope")
    runtime = body.get("runtime")
    if body.get("contract") != STT_CONTRACT or not isinstance(scope, dict) or set(scope) != {"campaign", "owner", "role"}:
        raise HTTPException(400, "Invalid scoped STT envelope")
    if not all(isinstance(scope.get(field), str) and 0 < len(scope[field]) <= 100 for field in ("campaign", "owner")) or scope.get("role") not in {"host", "player"}:
        raise HTTPException(400, "Invalid scoped STT scope")
    if not all(isinstance(body.get(field), str) and 0 < len(body[field]) <= 100 for field in ("session", "requestId")):
        raise HTTPException(400, "Invalid scoped STT identifiers")
    if not isinstance(runtime, dict) or set(runtime) != {"contract", "bootEpoch", "generation", "sessionPolicyRevision"} or runtime.get("contract") != RUNTIME_CONTRACT:
        raise HTTPException(400, "Invalid STT runtime envelope")
    if not all(isinstance(runtime.get(field), str) for field in ("bootEpoch", "generation")) or not isinstance(runtime.get("sessionPolicyRevision"), int) or isinstance(runtime.get("sessionPolicyRevision"), bool) or runtime["sessionPolicyRevision"] < 0:
        raise HTTPException(400, "Invalid STT runtime fence")
    try:
        uuid.UUID(runtime["bootEpoch"])
        uuid.UUID(runtime["generation"])
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Invalid STT runtime fence") from None
    return body, _decode_stt_request({"audio_base64": body["audio_base64"], "mime_type": body["mime_type"]})


def _decode_stt_request(body: object) -> bytes:
    if not isinstance(body, dict) or set(body) != {"audio_base64", "mime_type"}:
        raise HTTPException(400, "Invalid audio request")
    encoded = body.get("audio_base64")
    if body.get("mime_type") != "audio/wav" or not isinstance(encoded, str) or len(encoded) > 8_500_000:
        raise HTTPException(400, "Invalid audio request")
    try:
        audio = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid audio encoding") from None
    if len(audio) > MAX_STT_AUDIO_BYTES or len(audio) < 44 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise HTTPException(400, "Invalid WAV audio")
    return audio


def _transcribe_game_audio(audio: bytes) -> tuple[str, str]:
    status = local_stt_status()
    model_path = _game_stt_model_path()
    if not status["ready"]:
        raise RuntimeError("Private game local STT is not ready; install Faster-Whisper and a private local model first")
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_audio:
            temporary_audio.write(audio)
            temporary_name = temporary_audio.name
        global STT_MODEL, STT_MODEL_PATH
        with STT_LOCK:
            if STT_MODEL is None or STT_MODEL_PATH != str(model_path):
                from faster_whisper import WhisperModel
                STT_MODEL = WhisperModel(str(model_path), device="cpu", compute_type="int8")
                STT_MODEL_PATH = str(model_path)
            segments, _info = STT_MODEL.transcribe(temporary_name, vad_filter=True)
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
        if not transcript:
            raise RuntimeError("Private game local STT returned no speech")
        return transcript[:8000], model_path.name
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def _transcribe_scoped_stt(scoped: dict, audio: bytes) -> dict:
    """Serialize one scoped STT request and persist only its receipt fingerprint."""
    scope = scoped["scope"]
    identity = (scope["campaign"], scoped["session"], scope["owner"], scoped["requestId"])
    fingerprint = hashlib.sha256(json.dumps({
        "scope": scope,
        "session": scoped["session"],
        "requestId": scoped["requestId"],
        "runtime": scoped["runtime"],
        "mime_type": scoped["mime_type"],
        "audio_sha256": hashlib.sha256(audio).hexdigest(),
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with STT_REQUESTS:
        with database() as db:
            prior = db.execute("SELECT fingerprint,body FROM stt_jobs WHERE campaign=? AND session=? AND owner=? AND request=?", identity).fetchone()
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise HTTPException(409, "STT request ID conflict")
            return json.loads(prior["body"])
        _require_runtime(scope["campaign"], scoped["session"], RuntimeFence.model_validate(scoped["runtime"]))
        try:
            transcript, model = _transcribe_game_audio(audio)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        # The lease/policy is checked again after local work, before any receipt
        # can be persisted, so a late transcript cannot outlive its fence.
        _require_runtime(scope["campaign"], scoped["session"], RuntimeFence.model_validate(scoped["runtime"]))
        response = {"status":"completed","result":{"kind":"transcript","text":transcript,"engine":"game-local-faster-whisper","model":model,"trace":[{"stage":"local_stt","destination":"local","status":"ready"}]},"receipt":{"audio_bytes":len(audio),"retention":{"raw_audio_persisted":False,"request_evidence_persisted":False,"general_memory_writes":False,"route_journal_writes":False,"game_receipt_persisted":True,"transcript_persisted_in_game_receipt":True}}}
        with database() as db:
            db.execute("INSERT INTO stt_jobs VALUES(?,?,?,?,?,?)", (*identity, fingerprint, json.dumps(response, separators=(",", ":"))))
        return response


from contextlib import asynccontextmanager
@asynccontextmanager
async def startup(application):
    token()
    yield

app = FastAPI(title='Obus Campaign Game Agent', lifespan=startup)
@app.middleware('http')
async def private_access(request: Request, call_next):
    if request.client and request.client.host not in {'127.0.0.1','::1','testclient'}:
        return JSONResponse(status_code=403,content={'error':'Local service only'})
    if not hmac.compare_digest(request.headers.get('X-Obus-Game-Token',''), token()):
        return JSONResponse(status_code=401,content={'error':'Game service authentication required'})
    if request.method in {'POST','PUT','PATCH'}:
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>9000000:
                return JSONResponse(status_code=413,content={'error':'Request too large'})
        request._body=bytes(body)
    return await call_next(request)
@app.get('/api/game/capabilities')
def capabilities():
    return {'contract':CONTRACT,'campaign_rag':True,'audience_filtering':True,'provider_allowlist':True,'codex_gate':True,'no_tools':True,'no_personal_memory':True,'no_auto_memory':True,'generic_remote_routes':False,'verified_free_route_fallback':False,'free_route_policy':'runtime authority permits local-only dispatch; no remote or fallback route is available','codex_available':False,'retrieval':'scoped lexical; embedding integration pending','local_stt':local_stt_status()}


@app.get('/api/game/runtime')
def get_runtime(campaign: str, session: str):
    return runtime_authority().snapshot(campaign, session).public()


@app.put('/api/game/runtime/host-generation')
async def register_host_generation(request: Request):
    return await _host_control_async(request, runtime_authority().register)


@app.post('/api/game/runtime/host-generation/renew')
async def renew_host_generation(request: Request):
    return await _host_control_async(request, runtime_authority().renew)


@app.patch('/api/game/runtime/policy')
async def patch_runtime_policy(request: Request):
    return await _host_control_async(request, runtime_authority().patch_policy)


@app.post('/api/game/runtime/session/revoke')
async def revoke_runtime_session(request: Request):
    return await _host_control_async(request, runtime_authority().revoke_session)


@app.post('/api/game/sources')
def put_source(source: Source):
    ingest(source)
    return {'saved':True}
@app.post('/api/game/route')
async def route(job: Job):
    return await asyncio.to_thread(run_job,job)
@app.post('/api/voice/transcribe')
async def transcribe(request: Request):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "Invalid audio request") from None
    scoped, audio = _scoped_stt_audio(body)
    _require_runtime(scoped["scope"]["campaign"], scoped["session"], RuntimeFence.model_validate(scoped["runtime"]))
    return await asyncio.to_thread(_transcribe_scoped_stt, scoped, audio)
