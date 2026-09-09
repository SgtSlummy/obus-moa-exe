"""Private MemPalace index for current, already-authorized game sources.

The source database and its ACLs remain authoritative. The worker can rank only
content-addressed IDs supplied by this request; it never searches developer
memory, returns stored text, mines transcripts, or calls an external model.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading

_LOCK = threading.Lock()
_LAST_STATUS = 'not_queried'
MAX_INPUT_BYTES = 1024 * 1024
MODEL_FILES = ('config.json', 'model.onnx', 'special_tokens_map.json',
               'tokenizer_config.json', 'tokenizer.json', 'vocab.txt')


def _config():
    root = Path(os.environ.get('OBUS_GAME_DATA_DIR', Path.home() / '.occultbus' / 'game-agent'))
    path = Path(os.environ.get('OBUS_GAME_MEMORY_CONFIG', root / 'mempalace.json'))
    try:
        if path.stat().st_size > 8192:
            return None
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict) or set(value) != {'enabled', 'python', 'palace_path', 'model_path'} or value['enabled'] is not True:
            return None
        for key in ('python', 'palace_path', 'model_path'):
            if not isinstance(value[key], str):
                return None
            target = Path(value[key])
            if not target.is_absolute() or any('onedrive' in part.lower() for part in target.parts):
                return None
        if not Path(value['python']).is_file():
            return None
        if not all((Path(value['model_path']) / 'onnx' / name).is_file() for name in MODEL_FILES):
            return None
        return value
    except (OSError, ValueError, TypeError):
        return None


def memory_status():
    configured = _config() is not None
    return {'engine': 'mempalace' if configured else 'legacy', 'configured': configured,
            'backend': 'sqlite_exact' if configured else None,
            'isolation': 'current-authorized-content-ids', 'local_only': True,
            'last_query_status': _LAST_STATUS, 'authoritative_store': 'game.sqlite'}


def _identity(campaign, source):
    # Includes provenance, ACL, revision and complete text. A correction,
    # tombstone or access change can never reuse an old source identity.
    encoded = json.dumps({'campaign': campaign, 'source': source}, sort_keys=True,
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def rank_current_sources(campaign, query, candidates):
    """Return ranked (current source object, cosine) pairs, or None on failure.

    Called only after campaign/role/owner filtering. None requests the existing
    lexical/local-embedding fallback; an empty list is a successful empty search.
    """
    global _LAST_STATUS
    config = _config()
    if config is None:
        return None
    if not isinstance(campaign, str) or not campaign or not isinstance(query, str) or not query.strip():
        return []
    if not isinstance(candidates, list) or len(candidates) > 32:
        return None
    by_id = {}
    embedding_chars = min(2000, (16000 - len(query[:1000])) // max(1, len(candidates)))
    try:
        for source in candidates:
            if (not isinstance(source, dict) or source.get('campaign') != campaign
                    or source.get('deleted', False) or not isinstance(source.get('text'), str)
                    or not 0 < len(source['text']) <= 16000
                    or type(source.get('revision')) is not int or source['revision'] < 0):
                return None
            by_id[_identity(campaign, {**source, '_embedding_chars': embedding_chars})] = source
        if not by_id:
            return []
        payload = json.dumps({'campaign': campaign, 'query': query[:1000], 'embedding_chars': embedding_chars,
                              'sources': [{'id': key, 'text': source['text'],
                                           'ref': source['ref'], 'revision': source['revision']}
                                          for key, source in by_id.items()]}, ensure_ascii=False)
        if len(payload.encode('utf-8')) > MAX_INPUT_BYTES:
            return None
        if not _LOCK.acquire(blocking=False):
            return None
        try:
            env = {**os.environ, 'ANONYMIZED_TELEMETRY': 'False', 'OTEL_SDK_DISABLED': 'true',
                   'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
            completed = subprocess.run(
                [config['python'], '-I', '-X', 'utf8', str(Path(__file__).resolve()),
                 '--worker', config['palace_path'], config['model_path']],
                input=payload, text=True, encoding='utf-8', capture_output=True,
                timeout=15, check=True, env=env,
                cwd=str(Path(__file__).resolve().parent),
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            if len(completed.stdout) > 16000:
                raise ValueError('Oversized memory response')
            result = json.loads(completed.stdout)
            if not isinstance(result, dict) or set(result) != {'hits'} or not isinstance(result['hits'], list) or len(result['hits']) > len(by_id):
                raise ValueError('Invalid memory response')
            ranked, seen = [], set()
            for hit in result['hits']:
                if (not isinstance(hit, dict) or set(hit) != {'id', 'cosine'}
                        or hit['id'] not in by_id or hit['id'] in seen
                        or type(hit['cosine']) not in (float, int)
                        or not -1.000001 <= hit['cosine'] <= 1.000001
                        or not math.isfinite(hit['cosine'])):
                    raise ValueError('Invalid or unauthorized memory hit')
                seen.add(hit['id'])
                ranked.append((by_id[hit['id']], hit['cosine']))
            _LAST_STATUS = 'ready'
            return ranked
        finally:
            _LOCK.release()
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        _LAST_STATUS = 'fallback'
        return None


def _worker(palace_root, model_root):
    # Import the installed MemPalace only in its isolated Python environment.
    from mempalace.backends.base import PalaceRef
    from mempalace.backends.sqlite_exact import SQLiteExactBackend
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError('Memory input exceeds limit')
    request = json.loads(raw)
    sources = request['sources']
    if not 1 <= len(sources) <= 32:
        raise ValueError('Invalid memory candidate count')
    model_root = Path(model_root)
    def require_cached():
        if not all((model_root / 'onnx' / name).is_file() for name in MODEL_FILES):
            raise ValueError('Offline embedding model is unavailable')
    require_cached()
    embedding = ONNXMiniLM_L6_V2(preferred_providers=['CPUExecutionProvider'])
    embedding.DOWNLOAD_PATH = model_root
    # Explicitly prohibit the library's automatic model download path.
    embedding._download_model_if_not_exists = require_cached
    campaign_id = hashlib.sha256(request['campaign'].encode('utf-8')).hexdigest()
    path = str(Path(palace_root) / campaign_id)
    backend = SQLiteExactBackend()
    try:
        collection = backend.get_collection(
            palace=PalaceRef(id=campaign_id, local_path=path),
            collection_name='operator_game_vectors_minilm_v1', create=True)
        ids = [source['id'] for source in sources]
        ref_keys = {source['id']: hashlib.sha256(source['ref'].encode('utf-8')).hexdigest() for source in sources}
        # Retire superseded cache entries for active refs. Tombstoned refs are
        # absent from the allowed query set; no source/query text is cached.
        prior = collection.get(where={'ref_key': {'$in': list(ref_keys.values())}}, include=[])
        obsolete = [key for key in prior.ids if key not in ids]
        if obsolete:
            collection.delete(ids=obsolete)
        existing = set(collection.get(ids=ids, include=[]).ids)
        missing = [source for source in sources if source['id'] not in existing]
        # Match the existing ranking budget: <=16000 embedding input characters.
        per_document = request['embedding_chars']
        if type(per_document) is not int or not 1 <= per_document <= 2000 or per_document * len(sources) + len(request['query']) > 16000:
            raise ValueError('Invalid embedding text budget')
        texts = [request['query']] + [source['text'][:per_document] for source in missing]
        vectors = [vector.tolist() for vector in embedding(texts)]
        if missing:
            collection.upsert(
                ids=[source['id'] for source in missing],
                documents=['' for source in missing],
                metadatas=[{'source_key': source['id'], 'ref_key': ref_keys[source['id']],
                            'revision': source['revision'], 'campaign_hash': campaign_id,
                            'embedding_model': 'all-MiniLM-L6-v2', 'embedding_chars': per_document}
                           for source in missing], embeddings=vectors[1:])
        result = collection.query(query_embeddings=[vectors[0]], n_results=len(ids),
                                  where={'source_key': {'$in': ids}}, include=['distances'])
        print(json.dumps({'hits': [{'id': key, 'cosine': 1.0 - distance}
                                  for key, distance in zip(result.ids[0], result.distances[0])]}))
    finally:
        backend.close()


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] != '--worker':
        raise SystemExit('This module is a private game memory worker.')
    _worker(sys.argv[2], sys.argv[3])
