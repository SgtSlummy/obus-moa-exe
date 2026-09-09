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
import io
import threading
import time
import urllib.request
import uuid
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from backend.game_evidence import (
    EvidenceDenied, EvidenceReference, EvidenceSnapshot,
    initialize_schema as initialize_evidence_schema, resolve_evidence, save_snapshot,
)
from backend.persistent_agents import _http_json, _NO_REDIRECT_OPENER, _validated_provider_base_url
from backend.game_providers import complete_free, complete_local as complete_game_local, _free_pin, GameProviderError, GameProviderRejected
from backend.game_runtime import GameRuntimeAuthority, RuntimeDenied
from backend import game_dispatch, game_evidence_uploads
from backend.game_evidence_selection import SelectionRequest, resolve_selection
from backend.game_prompt_policy import classify_job, render_template, PromptPolicyDenied
from backend.game_retrieval import MAX_SCANNED_SOURCES, rank_sources
from backend.game_mempalace import memory_status

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
ACTIVE_GAME_REQUESTS: dict[tuple[str, str], dict[str, int]] = {}


@contextmanager
def _tracked_dispatch(campaign: str, session: str, gate):
    """Count process-local work per scope and clear counts on every exit."""
    identity = (campaign, session)
    state = 'queuedCount'
    with LOCK:
        counts = ACTIVE_GAME_REQUESTS.setdefault(identity, {'queuedCount': 0, 'dispatchedCount': 0})
        counts[state] += 1
    try:
        with gate:
            with LOCK:
                counts['queuedCount'] -= 1
                counts['dispatchedCount'] += 1
                state = 'dispatchedCount'
            yield
    finally:
        with LOCK:
            counts[state] -= 1
            if not any(counts.values()):
                ACTIVE_GAME_REQUESTS.pop(identity, None)


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
    promptTemplate: Literal['session-summary-v1'] | None = None
    evidence: dict | list
    policy: Policy
    runtime: RuntimeFence
    max_tokens: int = Field(default=900, ge=16, le=6000)
class EvidenceRequest(Strict):
    contract: Literal['raph-obus-game-evidence-refs-v1']
    revision: int = Field(strict=True, ge=0, le=9007199254740991)
    references: list[EvidenceReference] = Field(min_length=1, max_length=32)

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
        initialize_evidence_schema(db)
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
    query = query[:1000] if isinstance(query, str) else ''
    if not query.strip():
        return []
    words = sorted(set(re.findall(r'\w{3,}', query.lower())))[:64]
    # Only constant SQL fragments are composed; every query word stays a parameter.
    score = ' + '.join("CASE WHEN instr(lower(json_extract(body, '$.text')), ?) > 0 THEN 1 ELSE 0 END" for _ in words) or 'length(ref) * 0'
    # Filter access and tombstones before ranking or limiting the candidate set.
    # Database scoring preserves lexical matches beyond the first source refs.
    with LOCK, database() as db:
        rows = db.execute(
            "SELECT body FROM sources WHERE campaign=? AND (audience='party' OR (audience='host' AND ?='host') OR (audience='private' AND owner=?)) "
            "AND COALESCE(json_extract(body, '$.deleted'), 0)=0 "
            f"ORDER BY ({score}) DESC, ref LIMIT ?",
            (scope.campaign, scope.role, scope.owner, *words, MAX_SCANNED_SOURCES),
        ).fetchall()
    eligible = [source for row in rows if not (source := json.loads(row['body']))['deleted']]
    ranked = rank_sources(scope.campaign, query, eligible)
    # Memory work can take time. Recheck the current database and ACLs before
    # exposing any cached hit; return only records unchanged since selection.
    with LOCK, database() as db:
        current = {}
        for source in ranked:
            row = db.execute(
                "SELECT body FROM sources WHERE campaign=? AND ref=? AND "
                "(audience='party' OR (audience='host' AND ?='host') OR (audience='private' AND owner=?))",
                (scope.campaign, source['ref'], scope.role, scope.owner),
            ).fetchone()
            if row and json.loads(row['body']) == source and not source['deleted']:
                current[source['ref']] = source
    out, budget = [], 5000
    for source in ranked:
        if source['ref'] not in current:
            continue
        text = source['text'][:budget]
        if not text or len(out) == 6:
            break
        out.append({**source, 'text': text})
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
    # Host pins choose a route; the game transport separately enforces its free
    # variant, zero-price ceiling, downstream destination and response cost.
    try:
        with (ROOT / 'free-routes.json').open(encoding='utf-8') as configured_file:
            encoded = configured_file.read(65537)
        if len(encoded) > 65536:
            return []
        configured = json.loads(encoded)
    except (OSError, UnicodeError, ValueError):
        return []
    result = []
    for pin in configured if isinstance(configured, list) else []:
        if not isinstance(pin, dict) or any(pin.get(flag) is not True for flag in ('zero_charge', 'no_fallback', 'no_tools')):
            continue
        for key in keys:
            if not isinstance(key, dict) or key.get('connected') is not True or key.get('verified') is not True:
                continue
            if key.get('provider') != 'openrouter' or key.get('base_url') != 'https://openrouter.ai/api/v1':
                continue
            if all(key.get(field) == pin.get(field) for field in ('id', 'provider', 'model', 'base_url')):
                candidate = {**key, 'game_free_pin': dict(pin)}
                try:
                    _free_pin(candidate)
                except GameProviderError:
                    continue
                result.append(candidate)
                if len(result) == 8:
                    return result
    return result

def complete_local(key, prompt, maximum):
    # The game-specific adapter verifies a concrete local model and checks the
    # returned model/provenance before exposing text to the existing job API.
    return complete_game_local(key, prompt, maximum)['text']

def _require_runtime(campaign: str, session: str, fence: RuntimeFence):
    try:
        return runtime_authority().require_dispatch(
            campaign, session, boot_epoch=fence.bootEpoch,
            generation=fence.generation, policy_revision=fence.sessionPolicyRevision,
        )
    except RuntimeDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


@contextmanager
def _receipt_transaction(campaign: str, session: str, fence: RuntimeFence):
    # Initialize the game schema before taking the runtime writer lock. The
    # authority owns both validation and the receipt transaction's commit.
    with database():
        pass
    try:
        with runtime_authority().receipt_transaction(
            campaign, session, boot_epoch=fence.bootEpoch,
            generation=fence.generation, policy_revision=fence.sessionPolicyRevision,
        ) as db:
            yield db
    except RuntimeDenied as exc:
        raise HTTPException(status_code=exc.status, detail=exc.code) from exc


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


def _reference_request(job: Job) -> EvidenceRequest | SelectionRequest | None:
    if not isinstance(job.evidence, dict) or 'contract' not in job.evidence:
        return None
    try:
        model = SelectionRequest if job.evidence.get('contract') == 'raph-obus-game-evidence-refs-v2' else EvidenceRequest
        return model.model_validate(job.evidence)
    except ValidationError:
        raise HTTPException(422, 'evidence_references_invalid') from None


def _resolve_job_evidence(db, job: Job, request: EvidenceRequest | SelectionRequest, *, external: bool = False):
    # All source/consent reads share one snapshot. The final call runs inside
    # the authority-owned receipt transaction, excluding concurrent syncs.
    if not db.in_transaction:
        db.execute('BEGIN')
    try:
        if isinstance(request, SelectionRequest):
            return resolve_selection(db, job.scope.campaign, job.session, job.scope.owner,
                                     job.scope.role, request, external=external)
        return resolve_evidence(
            db, job.scope.campaign, job.session, job.scope.owner, job.scope.role,
            request.revision, request.references, external=external,
        )
    except EvidenceDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


@contextmanager
def _evidence_transaction(campaign: str, session: str, fence: RuntimeFence):
    # Consent/corrections must reach the authority even while model use is off.
    # This separate guard never grants permission to save inference receipts.
    with database():
        pass
    try:
        with runtime_authority().evidence_transaction(
            campaign, session, boot_epoch=fence.bootEpoch,
            generation=fence.generation, policy_revision=fence.sessionPolicyRevision,
        ) as db:
            yield db
    except RuntimeDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


def _save_evidence_snapshot(body: dict) -> dict:
    try:
        snapshot = EvidenceSnapshot.model_validate(body)
    except ValidationError:
        raise HTTPException(422, 'evidence_snapshot_invalid') from None
    fence = RuntimeFence.model_validate(snapshot.runtime.model_dump())
    try:
        with _evidence_transaction(snapshot.campaign, snapshot.session, fence) as db:
            saved = save_snapshot(db, snapshot)
            if saved.get('status') == 'saved' and game_dispatch.schema_ready(db):
                game_dispatch.cancel_evidence_changed(db, campaign=snapshot.campaign, session=snapshot.session,
                                                      now_ms=int(time.time() * 1000))
            return saved
    except EvidenceDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


def _upload_evidence(body: dict) -> dict:
    try:
        command = game_evidence_uploads.parse_command(body)
        # Migration and backup must finish before taking the runtime writer lock.
        game_evidence_uploads.prepare_store(ROOT / 'game.sqlite')
        fence = RuntimeFence.model_validate(command.runtime.model_dump())
        with _evidence_transaction(command.campaign, command.session, fence) as db:
            result = game_evidence_uploads.apply_command(db, command.model_dump(), int(time.time() * 1000))
            changed = command.operation == 'begin' and result['status'] in {'pending', 'deferred'}
            changed = changed or result.get('receipt', {}).get('status') == 'saved'
            if changed and game_dispatch.schema_ready(db):
                game_dispatch.cancel_evidence_changed(db, campaign=command.campaign, session=command.session,
                                                      now_ms=int(time.time() * 1000))
            return result
    except EvidenceDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


def _external_allowed(job, classified, snapshot):
    return bool(classified.external_capable and job.policy.mode == 'local-free'
                and job.policy.exportable and not job.policy.codex
                and snapshot.enabled and snapshot.mode == 'local-free'
                and snapshot.exportable and not snapshot.codex)


def _render_job(classified, resolved):
    try:
        return render_template(classified, resolved)
    except PromptPolicyDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


def _route_digest(key):
    descriptor = {name: key.get(name) for name in ('id', 'provider', 'model', 'base_url', 'game_free_pin')}
    return hashlib.sha256(json.dumps(descriptor, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


@contextmanager
def _dispatch_transaction(job):
    # Back up an existing store before introducing the ledger. Never migrate
    # while holding the runtime writer lock or a receipt transaction.
    game_dispatch.prepare_dispatch_store(ROOT / 'game.sqlite')
    with database():
        pass
    try:
        with runtime_authority().dispatch_transaction(
            job.scope.campaign, job.session, boot_epoch=job.runtime.bootEpoch,
            generation=job.runtime.generation, policy_revision=job.runtime.sessionPolicyRevision,
            external=True,
        ) as guarded:
            yield guarded
    except (RuntimeDenied, game_dispatch.DispatchDenied) as exc:
        raise HTTPException(exc.status, exc.code) from exc


def _prepare_free_dispatch(job, key, classified, reference_request, fingerprint, get_keys):
    route_digest = _route_digest(key)
    with _dispatch_transaction(job) as (db, snapshot):
        if not _external_allowed(job, classified, snapshot):
            raise HTTPException(409, 'external_policy_denied')
        resolved = _resolve_job_evidence(db, job, reference_request, external=True)
        rendered = _render_job(classified, resolved)
        record = game_dispatch.enqueue(
            db, campaign=job.scope.campaign, session=job.session, owner=job.scope.owner,
            request_id=job.requestId, fingerprint=fingerprint, task=job.task,
            boot_epoch=snapshot.boot_epoch, generation=snapshot.generation,
            policy_revision=snapshot.policy_revision, evidence_revision=rendered.revision,
            evidence_digest=rendered.prompt_digest, route_id=key['id'], route_digest=route_digest,
            provider=key['game_free_pin']['downstream_provider_name'], model=key['model'],
            now_ms=int(time.time() * 1000),
            evidence_selection={'role': job.scope.role, 'request': reference_request.model_dump()}
                if isinstance(reference_request, SelectionRequest) else None,
        )
    if record['status'] == 'failed':
        return None
    # Recheck the provider pin outside the database lock, then consent and the
    # host fence inside it. Marking dispatched is the one-use admission point.
    if not any(_route_digest(candidate) == route_digest for candidate in approved_free(get_keys())):
        raise HTTPException(409, 'free_route_no_longer_allowed')
    with _dispatch_transaction(job) as (db, snapshot):
        if not _external_allowed(job, classified, snapshot):
            raise HTTPException(409, 'external_policy_denied')
        current = _render_job(classified, _resolve_job_evidence(db, job, reference_request, external=True))
        if current.prompt_digest != rendered.prompt_digest:
            raise HTTPException(409, 'evidence_changed_before_dispatch')
        game_dispatch.mark_dispatched(db, record['attemptId'], fingerprint=fingerprint, now_ms=int(time.time() * 1000))
    return current, record['attemptId']


def _record_dispatch_outcome(attempt_id, fingerprint, outcome, provenance=None):
    # This diagnostic-only transaction never acquires the runtime lock and
    # never stores model text. It can record an already admitted call after
    # policy withdrawal; it cannot create an inference receipt or another call.
    try:
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            game_dispatch.finish(db, attempt_id, fingerprint=fingerprint, outcome=outcome,
                                 provenance=provenance, now_ms=int(time.time() * 1000))
        return True
    except Exception:
        # An unresolved dispatched row is deliberately non-retryable.
        return False


def run_job(job: Job, get_keys=catalogue, local=complete_local, remote=complete_free):
    # Snapshot caller-owned models before any queue wait or provider callback.
    job = Job.model_validate(job.model_dump())
    if job.policy.codex:
        raise HTTPException(409, 'Codex escalation is not supported by this game agent')
    if job.policy.namespace != job.scope.campaign or len(json.dumps(job.evidence)) > 50000:
        raise HTTPException(400, 'Invalid campaign evidence')
    try:
        classified = classify_job(task=job.task, prompt_template=job.promptTemplate,
                                  instructions=job.instructions, evidence=job.evidence)
    except PromptPolicyDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc
    _require_runtime(job.scope.campaign, job.session, job.runtime)
    if not classified.external_capable and (job.policy.mode != 'local' or job.policy.exportable):
        raise HTTPException(409, 'legacy game requests require local-only dispatch')
    reference_request = _reference_request(job)
    # Optional template support must not change historical local fingerprints.
    serialized = job.model_dump_json(exclude={'promptTemplate'} if job.promptTemplate is None else set())
    fingerprint = hashlib.sha256(serialized.encode()).hexdigest()
    identity = (job.scope.campaign, job.session, job.scope.owner, job.requestId)
    with _tracked_dispatch(job.scope.campaign, job.session, INFERENCE):
        snapshot = _require_runtime(job.scope.campaign, job.session, job.runtime)
        with database() as db:
            resolved = _resolve_job_evidence(db, job, reference_request) if reference_request else None
            prior = db.execute('SELECT fingerprint,body FROM game_jobs WHERE campaign=? AND session=? AND owner=? AND request=?', identity).fetchone()
        if prior:
            if prior['fingerprint'] != fingerprint:
                raise HTTPException(409, 'Request ID conflict')
            result = json.loads(prior['body'])
            if any(stage.get('destination') == 'free' and stage.get('status') == 'ready' for stage in result.get('trace', [])):
                with _dispatch_transaction(job) as (db, current):
                    if not _external_allowed(job, classified, current):
                        raise HTTPException(409, 'external_policy_denied')
                    _render_job(classified, _resolve_job_evidence(db, job, reference_request, external=True))
            return result
        sources = resolved['sources'] if resolved else retrieve(job.scope, str(job.evidence.get('question','')) if isinstance(job.evidence,dict) else job.task)
        rendered = _render_job(classified, resolved) if classified.external_capable else None
        prompt = rendered.prompt if rendered else json.dumps({'task':job.task,'instructions':job.instructions,'evidence':job.evidence,'retrieved':sources}, ensure_ascii=False)
        snapshot = _require_runtime(job.scope.campaign, job.session, job.runtime)
        keys = [dict(key) for key in get_keys() if isinstance(key, dict)]
        locals_ = [key for key in keys if key.get('id') == 'key-local-ollama' and key.get('provider') == 'ollama' and key.get('connected') is True and key.get('verified') is True]
        routes = [(key, 'local') for key in locals_]
        if _external_allowed(job, classified, snapshot):
            routes += [(key, 'free') for key in approved_free(keys)]
        # No general Obus router, coding adapter, nested advisor or memory route
        # can be reached from this explicit, destination-checked attempt list.
        trace, text, selected, selected_attempt, selected_provenance = [], '', None, None, None
        for key, destination in routes:
            for attempt in range(2 if destination == 'local' else 1):
                active_attempt, provenance, provider_completed = None, None, False
                stage = {'provider':key['id'],'model':key['model'],'destination':destination,'cost':'zero' if destination == 'free' else 'local','attempt':attempt+1}
                _require_runtime(job.scope.campaign, job.session, job.runtime)
                request_prompt = prompt
                if destination == 'free':
                    prepared = _prepare_free_dispatch(job, key, classified, reference_request, fingerprint, get_keys)
                    if prepared is None:
                        continue
                    current_prompt, active_attempt = prepared
                    request_prompt = current_prompt.prompt
                elif reference_request:
                    with database() as db:
                        current_sources = _resolve_job_evidence(db, job, reference_request)
                        if classified.external_capable:
                            request_prompt = _render_job(classified, current_sources).prompt
                try:
                    if destination == 'local':
                        text = local(key, request_prompt, job.max_tokens)
                    else:
                        completion = remote(key, request_prompt, job.max_tokens)
                        pin = key.get('game_free_pin', {})
                        if (not isinstance(completion, dict)
                                or completion.get('route_id') != key['id']
                                or completion.get('model') != key['model']
                                or completion.get('provider') != pin.get('downstream_provider_name')
                                or completion.get('gateway') != 'openrouter'
                                or completion.get('endpoint') != 'https://openrouter.ai/api/v1/chat/completions'
                                or completion.get('destination') != 'external'
                                or completion.get('cost') != 'zero'
                                or completion.get('cost_basis') != 'free-variant+zero-price-ceiling+response-usage'):
                            raise RuntimeError('Invalid free-route provenance')
                        text = completion.get('text')
                        stage.update({name: completion[name] for name in (
                            'provider', 'model', 'endpoint', 'gateway', 'route_id', 'cost_basis',
                        )})
                        optional = {name: completion[name] for name in ('completion_tokens', 'response_id')
                                    if completion.get(name) is not None and completion.get(name) != ''}
                        stage.update(optional)
                        provenance = {name: completion[name] for name in (
                            'provider', 'model', 'gateway', 'route_id', 'destination', 'cost', 'cost_basis',
                        )}
                        provenance.update(optional)
                        provider_completed = True
                    if not isinstance(text,str) or not text.strip() or len(text)>16000 or '<script' in text.lower():
                        raise RuntimeError('Invalid output')
                    stage['status'] = 'ready'; trace.append(stage); selected = key
                    selected_attempt, selected_provenance = active_attempt, provenance
                    break
                except Exception as exc:
                    stage['status'] = 'failed'; trace.append(stage); text = ''
                    if active_attempt:
                        known_failure = provider_completed or isinstance(exc, GameProviderRejected)
                        outcome = 'failed' if known_failure else 'uncertain'
                        recorded = _record_dispatch_outcome(active_attempt, fingerprint, outcome, provenance)
                        if not known_failure or not recorded:
                            raise HTTPException(503, 'External dispatch outcome is uncertain; the request will not be exported again') from None
            if text:
                break
        if not text:
            raise HTTPException(503, 'No eligible Obus game provider completed the request')
        result={'text':text.strip(),'routeId':str(uuid.uuid4()),'model':selected['model'],'trace':trace,'sources':[{'ref':s['ref'],'revision':s['revision']} for s in sources], 'retention': {'request_evidence_persisted': False, 'general_memory_writes': False, 'route_journal_writes': False, 'game_receipt_persisted': True}}
        if reference_request:
            result['evidenceRevision'] = reference_request.revision
        try:
            _require_runtime(job.scope.campaign, job.session, job.runtime)
            with _receipt_transaction(job.scope.campaign, job.session, job.runtime) as db:
                if reference_request:
                    current_sources = _resolve_job_evidence(db, job, reference_request, external=selected_attempt is not None)
                    if classified.external_capable:
                        _render_job(classified, current_sources)
                if selected_attempt:
                    game_dispatch.finish(db, selected_attempt, fingerprint=fingerprint, outcome='completed',
                                         provenance=selected_provenance, now_ms=int(time.time() * 1000))
                db.execute('INSERT INTO game_jobs VALUES(?,?,?,?,?,?)', (*identity,fingerprint,json.dumps(result)))
        except Exception:
            if selected_attempt:
                _record_dispatch_outcome(selected_attempt, fingerprint, 'discarded', selected_provenance)
            raise
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
    global STT_MODEL, STT_MODEL_PATH
    with STT_LOCK:
        if STT_MODEL is None or STT_MODEL_PATH != str(model_path):
            from faster_whisper import WhisperModel
            STT_MODEL = WhisperModel(str(model_path), device="cpu", compute_type="int8")
            STT_MODEL_PATH = str(model_path)
        # Keep the stream alive while Faster-Whisper's lazy iterator decodes it.
        # Closing the buffer also releases it if decoding or iteration fails.
        with io.BytesIO(audio) as audio_stream:
            segments, _info = STT_MODEL.transcribe(audio_stream, vad_filter=True)
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
    if not transcript:
        raise RuntimeError("Private game local STT returned no speech")
    return transcript[:6000], model_path.name


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
    receipt = {"kind": "stt", "requestId": scoped["requestId"], "audioSha256": hashlib.sha256(audio).hexdigest(),
               "audio_bytes": len(audio), "retention": {"raw_audio_persisted": False, "request_evidence_persisted": False,
               "general_memory_writes": False, "route_journal_writes": False, "game_receipt_persisted": True,
               "transcript_persisted_in_game_receipt": False}}
    with _tracked_dispatch(scope["campaign"], scoped["session"], STT_REQUESTS):
        # Recheck after queueing, including receipt replay and direct callers.
        _require_runtime(scope["campaign"], scoped["session"], RuntimeFence.model_validate(scoped["runtime"]))
        with database() as db:
            prior = db.execute("SELECT fingerprint,body FROM stt_jobs WHERE campaign=? AND session=? AND owner=? AND request=?", identity).fetchone()
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise HTTPException(409, "STT request ID conflict")
            saved = json.loads(prior["body"])
            for key in ("engine", "model"):
                value = saved.get("receipt", {}).get(key)
                if isinstance(value, str) and len(value) <= 200:
                    receipt[key] = value
            replay = {"status": "completed_receipt_only", "receipt": receipt}
            encoded = json.dumps(replay, separators=(",", ":"))
            if encoded != prior["body"]:
                # Normalize an encountered legacy receipt without redisclosing
                # its stored transcript. This is not forensic SQLite erasure.
                with _receipt_transaction(scope["campaign"], scoped["session"], RuntimeFence.model_validate(scoped["runtime"])) as db:
                    db.execute("UPDATE stt_jobs SET body=? WHERE campaign=? AND session=? AND owner=? AND request=?", (encoded, *identity))
            return replay
        try:
            transcript, model = _transcribe_game_audio(audio)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        # The lease/policy is checked again after local work, before any receipt
        # can be persisted, so a late transcript cannot outlive its fence.
        _require_runtime(scope["campaign"], scoped["session"], RuntimeFence.model_validate(scoped["runtime"]))
        if not isinstance(transcript, str) or not transcript.strip():
            raise HTTPException(503, "Private game local STT returned no speech")
        transcript = transcript.strip()[:6000]
        receipt.update({"engine": "game-local-faster-whisper", "model": model})
        response = {"status":"completed","result":{"kind":"transcript","text":transcript,"engine":"game-local-faster-whisper","model":model,"trace":[{"stage":"local_stt","destination":"local","status":"ready"}]},"receipt":receipt}
        durable = {"status": "completed_receipt_only", "receipt": receipt}
        with _receipt_transaction(scope["campaign"], scoped["session"], RuntimeFence.model_validate(scoped["runtime"])) as db:
            db.execute("INSERT INTO stt_jobs VALUES(?,?,?,?,?,?)", (*identity, fingerprint, json.dumps(durable, separators=(",", ":"))))
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
        limit = game_evidence_uploads.MAX_HTTP_BYTES if request.url.path == '/api/game/evidence/upload' else 9000000
        async for chunk in request.stream():
            if len(body) + len(chunk) > limit:
                return JSONResponse(status_code=413,content={'error':'Request too large'})
            body.extend(chunk)
        request._body=bytes(body)
    return await call_next(request)
@app.get('/api/game/capabilities')
def capabilities():
    try:
        free_ready = bool(approved_free(catalogue()))
    except Exception:
        free_ready = False
    return {'contract':CONTRACT,'campaign_rag':True,'audience_filtering':True,'provider_allowlist':True,'codex_gate':True,'no_tools':True,'no_personal_memory':True,'no_auto_memory':True,'generic_remote_routes':False,'verified_free_route_fallback':True,'free_route_ready':free_ready,'free_route_readiness_basis':'eligible host pins and current catalogue status; inference availability is checked at dispatch','free_route_policy':'host-authorized local-free mode; classified reference-only templates; current external consent; one pinned zero-charge destination without tools or nested fallback','prompt_templates':['session-summary-v1'],'evidence_reference_contracts':['raph-obus-game-evidence-refs-v1','raph-obus-game-evidence-refs-v2'],'evidence_upload':{'contract':game_evidence_uploads.CONTRACT,'maxRequestBytes':game_evidence_uploads.MAX_HTTP_BYTES,'maxPageBytes':game_evidence_uploads.MAX_PAGE_BYTES,'maxPageSources':game_evidence_uploads.MAX_PAGE_SOURCES,'maxSources':game_evidence_uploads.MAX_DOCUMENT_SOURCES,'maxDocumentBytes':game_evidence_uploads.MAX_DOCUMENT_BYTES},'codex_available':False,'memory':memory_status(),'retrieval':'authorized MemPalace ranking with lexical/local fallback','semantic_rag_configured':bool(os.environ.get('OBUS_GAME_EMBEDDING_MODEL', '').strip()),'local_stt':local_stt_status()}


@app.get('/api/game/runtime')
def get_runtime(campaign: str, session: str):
    snapshot = runtime_authority().snapshot(campaign, session).public()
    with LOCK:
        counts = dict(ACTIVE_GAME_REQUESTS.get((campaign, session), {'queuedCount': 0, 'dispatchedCount': 0}))
    external = game_dispatch.public_recent(ROOT / 'game.sqlite', campaign=campaign, session=session)
    return {**snapshot, **counts, 'externalDispatch': external}


@app.put('/api/game/runtime/host-generation')
async def register_host_generation(request: Request):
    return (await _host_control_async(request, runtime_authority().register))["runtime"]


@app.post('/api/game/runtime/host-generation/renew')
async def renew_host_generation(request: Request):
    return (await _host_control_async(request, runtime_authority().renew))["runtime"]


@app.patch('/api/game/runtime')
async def patch_runtime_policy(request: Request):
    return (await _host_control_async(request, runtime_authority().patch_policy))["runtime"]


@app.post('/api/game/runtime/session/revoke')
async def revoke_runtime_session(request: Request):
    return await _host_control_async(request, runtime_authority().revoke_session)


@app.post('/api/game/evidence/snapshot')
async def sync_evidence_snapshot(request: Request):
    # Bound the stream itself before decoding JSON or verifying its signature.
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 512 * 1024:
            raise HTTPException(413, 'evidence_snapshot_too_large')
        chunks.append(chunk)
    try:
        body = json.loads(b''.join(chunks))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, 'evidence_snapshot_invalid') from None
    if not isinstance(body, dict):
        raise HTTPException(400, 'evidence_snapshot_invalid')
    try:
        runtime_authority().verify_host(request.method, request.url.path, body, request.headers)
        return await asyncio.to_thread(_save_evidence_snapshot, body)
    except RuntimeDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


@app.post('/api/game/evidence/upload')
async def upload_evidence(request: Request):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > game_evidence_uploads.MAX_HTTP_BYTES:
            raise HTTPException(413, 'evidence_upload_too_large')
        chunks.append(chunk)
    try:
        body = json.loads(b''.join(chunks))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, 'evidence_upload_invalid') from None
    if not isinstance(body, dict):
        raise HTTPException(400, 'evidence_upload_invalid')
    try:
        runtime_authority().verify_host(request.method, request.url.path, body, request.headers)
        return await asyncio.to_thread(_upload_evidence, body)
    except RuntimeDenied as exc:
        raise HTTPException(exc.status, exc.code) from exc


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
