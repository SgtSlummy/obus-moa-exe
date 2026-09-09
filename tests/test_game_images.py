import base64
import hashlib
import hmac
import io
import os
import threading
import secrets
import time
import uuid
import json
from types import SimpleNamespace
import pytest
from PIL import Image
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend import game_images
from backend.game_runtime import GameRuntimeAuthority

def png():
    stream = io.BytesIO(); Image.new('RGB', (512, 512), '#697061').save(stream, 'PNG'); return stream.getvalue()

def body():
    return {'contract': game_images.CONTRACT, 'scope': {'campaign': 'fixture-images', 'owner': 'fixture-host', 'audience': 'public', 'characterId': '', 'sceneId': 'fixture-room', 'revision': 1}, 'session': 'campaign', 'requestId': str(uuid.uuid4()),
            'runtime': {'contract': 'raph-obus-game-runtime-v1', 'bootEpoch': 'epoch', 'generation': 'generation', 'sessionPolicyRevision': 0}, 'prompt': 'Top-down seamless stone floor material, no objects, no text'}

def test_scopes_and_untrusted_provider_configuration_rejected():
    with pytest.raises(ValidationError): game_images.ImageJob.model_validate({'prompt': 'unscoped'})
    wrong = body(); wrong['providerUrl'] = 'https://example.invalid'
    with pytest.raises(ValidationError): game_images.ImageJob.model_validate(wrong)
    wrong = body(); wrong['scope']['audience'] = 'private'
    with pytest.raises(ValidationError): game_images.ImageJob.model_validate(wrong)

def test_gameplay_priority_and_lock_release_after_failure():
    gate = threading.Lock(); options = dict(require_runtime=lambda *_: None, inference=gate, state_lock=threading.RLock(), active_requests={('game', 'session'): {'queuedCount': 1}})
    with pytest.raises(HTTPException) as denied: game_images.run_image(game_images.ImageJob.model_validate(body()), **options)
    assert denied.value.status_code == 429 and not gate.locked()
    options['active_requests'] = {}
    with pytest.raises(HTTPException): game_images.run_image(game_images.ImageJob.model_validate(body()), **options, generate=lambda _: b'not png')
    assert not gate.locked()

def test_revocation_after_generation_suppresses_image():
    checks = []
    def require(*_):
        checks.append(True)
        if len(checks) == 3: raise HTTPException(409, 'runtime_fence_stale')
    gate = threading.Lock()
    with pytest.raises(HTTPException) as denied:
        game_images.run_image(game_images.ImageJob.model_validate(body()), require_runtime=require, inference=gate, state_lock=threading.RLock(), active_requests={}, generate=lambda _: png())
    assert denied.value.status_code == 409 and not gate.locked()

def test_png_dimensions_and_metadata_removed():
    source = png(); normalized = game_images.validate_png(base64.b64encode(source).decode())
    assert Image.open(io.BytesIO(normalized)).size == (512, 512)
    stream = io.BytesIO(); Image.new('RGB', (1024, 512)).save(stream, 'PNG')
    with pytest.raises(HTTPException): game_images.validate_png(base64.b64encode(stream.getvalue()).decode())

def test_local_game_catalogue_uses_only_registered_installed_local_model(monkeypatch):
    from backend import game_agent as agent
    calls = []
    registered = {'id': 'key-local-ollama', 'provider': 'ollama', 'base_url': 'http://127.0.0.1:11434', 'verified': True, 'state': 'ready', 'model': 'fixture-local'}
    def open_request(request, timeout):
        calls.append(request.full_url)
        value = [registered, {'id': 'cloud', 'provider': 'openrouter'}] if request.full_url.endswith('/api/keys') else {'models': [{'name': 'fixture-local'}]}
        return io.BytesIO(json.dumps(value).encode())
    monkeypatch.setattr(agent, '_NO_REDIRECT_OPENER', SimpleNamespace(open=open_request))
    keys = agent.local_catalogue()
    assert len(keys) == 1 and keys[0]['connected'] is True
    assert calls == [agent.CORE + '/api/keys', 'http://127.0.0.1:11434/api/tags']
    registered['base_url'] = 'http://[TOKEN REDACTED].1:11434'
    assert agent.local_catalogue()[0]['base_url'] == 'http://127.0.0.1:11434'
    registered['model'] = 'not-installed'
    assert agent.local_catalogue() == []

def test_game_catalogue_failures_are_sanitized(monkeypatch):
    from backend import game_agent as agent
    def fail(*_, **__): raise RuntimeError('secret upstream diagnostic')
    monkeypatch.setattr(agent, '_NO_REDIRECT_OPENER', SimpleNamespace(open=fail))
    with pytest.raises(HTTPException) as error: agent.local_catalogue()
    assert error.value.status_code == 503 and error.value.detail == 'game_catalogue_unavailable'

def test_signed_route_with_real_runtime_fence_and_fixture_provider(tmp_path, monkeypatch):
    from backend import game_agent as agent
    authority = GameRuntimeAuthority(tmp_path)
    generation = str(uuid.uuid4())
    runtime = authority.register({'contract': 'raph-obus-game-runtime-v1', 'campaign': 'fixture-images', 'session': 'campaign', 'generation': generation, 'expectedBootEpoch': authority.boot_epoch, 'expectedGeneration': None, 'opId': str(uuid.uuid4()), 'leaseSeconds': 120})['runtime']
    monkeypatch.setattr(agent, 'ROOT', tmp_path); monkeypatch.setattr(agent, 'RUNTIME', authority)
    if os.environ.get('OBUS_TEST_LOCAL_SD') != '1':
        monkeypatch.setattr(game_images, 'local_generate', lambda _: png())
    request = body(); request['runtime'] = {key: runtime[key] for key in ['contract', 'bootEpoch', 'generation', 'sessionPolicyRevision']}
    timestamp, nonce = str(int(time.time())), secrets.token_hex(32)
    signature = hmac.new(authority.host_key(), authority._signed_bytes('POST', '/api/game/images', timestamp, nonce, request), hashlib.sha256).hexdigest()
    headers = {'X-Obus-Game-Token': agent.token(), 'X-Obus-Game-Host-Timestamp': timestamp, 'X-Obus-Game-Host-Nonce': nonce, 'X-Obus-Game-Host-Signature': signature}
    with TestClient(agent.app) as client:
        assert client.post('/api/game/images', json=request, headers={'X-Obus-Game-Token': agent.token()}).status_code == 401
        response = client.post('/api/game/images', json=request, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json(); assert data['scope'] == request['scope']; assert data['receipt']['cloud'] is False
        assert 'prompt' not in data and 'fixture' not in data['image_base64']
        if os.environ.get('OBUS_TEST_LOCAL_SD') == '1':
            artifact = tmp_path / 'local-sd-fenced-fixture.png'
            artifact.write_bytes(base64.b64decode(data['image_base64']))
            print(f'Local SD fenced fixture artifact: {artifact}')
