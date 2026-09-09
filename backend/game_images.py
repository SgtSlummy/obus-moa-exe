"""Fenced, low-priority local SD artwork. No tools, retrieval, cloud or downloads."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import urllib.request
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from PIL import Image

CONTRACT = 'raph-obus-game-image-v1'
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
SD_URL = 'http://127.0.0.1:7860/sdapi/v1/txt2img'
MODEL_HASH = '6ce0161689'

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ImageScope(Strict):
    campaign: str = Field(min_length=1, max_length=100)
    owner: str = Field(min_length=1, max_length=100)
    audience: Literal['public', 'private', 'gm']
    characterId: str = Field(max_length=100)
    sceneId: str = Field(min_length=1, max_length=100)
    revision: int = Field(strict=True, ge=0, le=9007199254740991)

    @model_validator(mode='after')
    def require_character(self):
        if self.audience == 'private' and not self.characterId.strip():
            raise ValueError('Private artwork requires a character')
        if self.audience == 'public' and self.characterId:
            raise ValueError('Public artwork has no private character scope')
        return self

class ImageFence(Strict):
    contract: Literal['raph-obus-game-runtime-v1']
    bootEpoch: str = Field(min_length=1, max_length=100)
    generation: str = Field(min_length=1, max_length=100)
    sessionPolicyRevision: int = Field(strict=True, ge=0)

class ImageJob(Strict):
    contract: Literal['raph-obus-game-image-v1']
    scope: ImageScope
    session: str = Field(min_length=1, max_length=100)
    requestId: str = Field(min_length=1, max_length=100)
    runtime: ImageFence
    prompt: str = Field(min_length=1, max_length=1600)
    negativePrompt: str = Field(default='', max_length=800)
    seed: int = Field(default=-1, strict=True, ge=-1, le=2147483647)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPException(503, 'local_image_provider_redirect_rejected')

def validate_png(encoded: str) -> bytes:
    try:
        if not isinstance(encoded, str) or len(encoded) > MAX_IMAGE_BYTES * 4 // 3 + 8:
            raise ValueError()
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_IMAGE_BYTES or raw[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError()
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.size != (512, 512):
                raise ValueError()
            image.load()
            # Re-encode pixels only: remove provider metadata/prompts before delivery.
            output = io.BytesIO()
            image.convert('RGB').save(output, format='PNG')
            return output.getvalue()
    except Exception:
        raise HTTPException(503, 'local_image_invalid_png') from None

def local_generate(job: ImageJob) -> bytes:
    payload = {'prompt': job.prompt, 'negative_prompt': job.negativePrompt,
               'width': 512, 'height': 512, 'steps': 24, 'batch_size': 1, 'n_iter': 1,
               'seed': job.seed, 'cfg_scale': 7, 'sampler_name': 'Euler a',
               'send_images': True, 'save_images': False,
               'do_not_save_samples': True, 'do_not_save_grid': True}
    request = urllib.request.Request(SD_URL, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=120) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError()
        result = json.loads(raw)
        info = json.loads(result.get('info', '{}'))
        if info.get('sd_model_hash') != MODEL_HASH or len(result.get('images', [])) != 1:
            raise ValueError()
        return validate_png(result['images'][0])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'local_image_provider_unavailable') from None

def run_image(job: ImageJob, *, require_runtime, inference, state_lock, active_requests, generate=None):
    scope = job.scope
    require_runtime(scope.campaign, job.session, job.runtime)
    # Never wait ahead of queued gameplay. If busy, caller keeps approved artwork.
    with state_lock:
        if any(any(counts.values()) for counts in active_requests.values()) or not inference.acquire(blocking=False):
            raise HTTPException(429, 'gameplay_has_priority')
    try:
        require_runtime(scope.campaign, job.session, job.runtime)
        raw = (generate or local_generate)(job)
        raw = validate_png(base64.b64encode(raw).decode('ascii'))
        require_runtime(scope.campaign, job.session, job.runtime)
        return {'contract': CONTRACT, 'status': 'completed', 'requestId': job.requestId,
                'scope': scope.model_dump(), 'session': job.session, 'runtime': job.runtime.model_dump(),
                'image_base64': base64.b64encode(raw).decode('ascii'), 'mime_type': 'image/png',
                'receipt': {'provider': 'local-stable-diffusion', 'modelHash': MODEL_HASH,
                            'width': 512, 'height': 512, 'steps': 24,
                            'sha256': hashlib.sha256(raw).hexdigest(), 'tools': False,
                            'cloud': False, 'memory': False, 'promptPersisted': False}}
    finally:
        inference.release()
