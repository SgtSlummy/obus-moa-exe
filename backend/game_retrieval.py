"""Bounded, optional semantic ranking for already-authorized game sources.

The caller must perform campaign and audience/owner authorization before calling
rank_sources. This module never searches another store. It defensively discards
other campaigns and tombstones, and returns original dictionaries from the
current eligible list only. The database remains authoritative.

OBUS_GAME_EMBEDDING_MODEL opts in to an explicitly named local GGUF embedding
model. No model is downloaded. All HTTP uses the fixed loopback Ollama service,
without proxies or redirects. A failed local-model check or embedding request
returns lexical matches. Empty queries never invoke a model.

At most the first 2048 supplied records are inspected, and the strongest 32
lexical candidates (stable source-ref ties) receive semantic ranking. Text is
bounded to 16000 characters across one query/document batch, 2000 per document,
and 1000 for the query. This is bounded reranking, not whole-campaign vector
search. A four-second deadline includes model inspection and embeddings. The
caller must still enforce its own returned-source and output-text budgets.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import http.client
import json
import math
import os
import re
import socket
import threading
import time

MAX_SCANNED_SOURCES = 2048
MAX_CANDIDATES = 32
MAX_QUERY_CHARS = 1000
MAX_SOURCE_CHARS = 2000
MAX_TOTAL_TEXT_CHARS = 16000
MAX_REQUEST_BYTES = 131072
MAX_RESPONSE_BYTES = 2000000
MAX_VECTOR_DIMENSIONS = 2048
MAX_CACHE_ENTRIES = 128
RETRIEVAL_SECONDS = 4.0
SEMANTIC_MIN_COSINE = 0.35

_CACHE: OrderedDict[tuple, tuple[float, ...]] = OrderedDict()
_CACHE_LOCK = threading.Lock()
_EMBED_LOCK = threading.Lock()


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Game retrieval deadline elapsed")
    return remaining


def _request_json(path: str, payload: dict, deadline: float, limit: int) -> dict:
    """One direct loopback request; socket shutdown bounds slow response reads."""
    if path not in ("/api/show", "/api/embed"):
        raise ValueError("Unsupported local embedding operation")
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(body) > MAX_REQUEST_BYTES:
        raise ValueError("Embedding request exceeds byte budget")
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=_remaining(deadline))
    timer = None
    try:
        connection.connect()
        active_socket = connection.sock
        active_socket.settimeout(_remaining(deadline))

        def abort():
            # HTTPConnection may detach its socket for Connection: close. Keep
            # the original socket so the deadline still interrupts body reads.
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()

        timer = threading.Timer(_remaining(deadline), abort)
        timer.daemon = True
        timer.start()
        connection.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Local embedding service did not accept the request")
        length = response.getheader("Content-Length")
        if length is not None and (not length.isdigit() or int(length) > limit):
            raise ValueError("Invalid embedding response length")
        data = bytearray()
        while True:
            _remaining(deadline)
            chunk = response.read1(min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("Embedding response exceeds byte budget")
        _remaining(deadline)
        decoded = json.loads(data)
        if not isinstance(decoded, dict):
            raise ValueError("Embedding response must be an object")
        return decoded
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()


def _require_local_model(model: str, deadline: float) -> str | None:
    # A local proxy address is not sufficient proof of a local model. Reject
    # cloud-backed metadata and require a concrete local GGUF architecture.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", model) or "cloud" in model.lower() or "://" in model:
        raise ValueError("An explicit local embedding model is required")
    metadata = _request_json("/api/show", {"model": model, "verbose": False}, deadline, 262144)
    details = metadata.get("details")
    info = metadata.get("model_info")
    capabilities = metadata.get("capabilities")
    if not isinstance(details, dict) or details.get("format") != "gguf":
        raise ValueError("Embedding model is not a verified local GGUF model")
    if not isinstance(info, dict) or not isinstance(info.get("general.architecture"), str) or not info["general.architecture"]:
        raise ValueError("Embedding model architecture is unavailable")
    if not isinstance(capabilities, list) or "embedding" not in capabilities:
        raise ValueError("Selected model does not advertise embeddings")
    if any(value for key, value in metadata.items() if key.startswith("remote_")) or any(value for key, value in details.items() if key.startswith("remote_")):
        raise ValueError("Remote embedding destinations are forbidden")
    # Tags can be repointed without changing vector dimensions. Only cache when
    # every weight source names an immutable SHA256 blob; otherwise re-embed.
    modelfile = metadata.get("modelfile", "")
    weight_lines = re.findall(r"(?im)^\s*(?:FROM|ADAPTER)\s+(.+)$", modelfile) if isinstance(modelfile, str) else []
    if not weight_lines or not all(re.search(r"sha256[-:][a-fA-F0-9]{64}\b", line) for line in weight_lines):
        return None
    identity = {key: metadata.get(key) for key in ("modelfile", "parameters", "template", "details", "model_info")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


def _vectors(response: dict, count: int) -> list[tuple[float, ...]]:
    raw = response.get("embeddings")
    if not isinstance(raw, list) or len(raw) != count:
        raise ValueError("Embedding count does not match the request")
    vectors = []
    dimensions = None
    for row in raw:
        if not isinstance(row, list) or not 1 <= len(row) <= MAX_VECTOR_DIMENSIONS:
            raise ValueError("Invalid embedding dimensions")
        if dimensions is not None and len(row) != dimensions:
            raise ValueError("Inconsistent embedding dimensions")
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in row):
            raise ValueError("Embeddings must contain finite numbers")
        magnitude = math.hypot(*row)
        if not math.isfinite(magnitude) or magnitude == 0:
            raise ValueError("Embedding norm is invalid")
        dimensions = len(row)
        vectors.append(tuple(value / magnitude for value in row))
    return vectors


def _source_key(campaign: str, source: dict, model: str, identity: str | None, document: str) -> tuple:
    digest = hashlib.sha256((source["text"] + "\0" + document).encode("utf-8")).digest()
    return (campaign, source["ref"], source["revision"], model, identity, digest,
            source.get("audience"), source.get("owner"))


def rank_sources(campaign: str, query: str, eligible_sources) -> list[dict]:
    """Return current source objects ranked by hybrid relevance, or lexical matches.

    Semantic-only matches require cosine >= 0.35. Lexical matches remain eligible
    regardless of cosine. Production enablement requires a host model benchmark;
    this initial relevance floor is deliberately explicit and deterministic.
    """
    if not isinstance(campaign, str) or not campaign or not isinstance(query, str) or not query.strip():
        return []
    query = query.strip()[:MAX_QUERY_CHARS]
    words = set(re.findall(r"\w{3,}", query.lower()))
    candidates = []
    for index, source in enumerate(eligible_sources):
        if index >= MAX_SCANNED_SOURCES:
            break
        if not isinstance(source, dict) or source.get("campaign") != campaign or source.get("deleted", False):
            continue
        text = source.get("text")
        ref, revision = source.get("ref"), source.get("revision")
        if not isinstance(text, str) or not text or len(text) > 16000 or not isinstance(ref, str) or not 1 <= len(ref) <= 160 or type(revision) is not int or revision < 0:
            continue
        lexical = sum(word in text.lower() for word in words)
        candidates.append((source, lexical))
    candidates.sort(key=lambda item: (-item[1], item[0]["ref"], item[0]["revision"], item[0]["text"]))
    candidates = candidates[:MAX_CANDIDATES]
    fallback = [source for source, lexical in candidates if lexical]
    from backend.game_mempalace import rank_current_sources
    memory = rank_current_sources(campaign, query, [source for source, _ in candidates])
    if memory is not None:
        lexical_by_id = {id(source): lexical for source, lexical in candidates}
        ranked_memory = []
        for source, cosine in memory:
            lexical = lexical_by_id[id(source)]
            if lexical or cosine >= SEMANTIC_MIN_COSINE:
                ranked_memory.append((source, 0.85 * cosine + 0.15 * lexical / max(1, len(words))))
        ranked_memory.sort(key=lambda item: (-item[1], item[0]["ref"], item[0]["revision"]))
        return [source for source, _ in ranked_memory]
    model = os.environ.get("OBUS_GAME_EMBEDDING_MODEL", "").strip()
    if not candidates or not model:
        with _CACHE_LOCK:
            for key in list(_CACHE):
                if key[0] == campaign:
                    del _CACHE[key]
        return fallback
    # Embeddings have lower priority than game/STT work. Concurrent retrieval
    # uses deterministic lexical results instead of growing an unbounded queue.
    if not _EMBED_LOCK.acquire(blocking=False):
        return fallback
    try:
        deadline = time.monotonic() + RETRIEVAL_SECONDS
        identity = _require_local_model(model, deadline)
        nomic = model.split(":", 1)[0] == "nomic-embed-text"
        query_text = ("search_query: " if nomic else "") + query
        prefix = "search_document: " if nomic else ""
        per_document = min(MAX_SOURCE_CHARS, (MAX_TOTAL_TEXT_CHARS - len(query_text)) // len(candidates) - len(prefix))
        documents = [prefix + source["text"][:per_document] for source, _ in candidates]
        keys = [_source_key(campaign, source, model, identity, document) for (source, _), document in zip(candidates, documents)]
        with _CACHE_LOCK:
            # Revisions, content and access changes invalidate affected cached
            # vectors. Cache entries never introduce a source into this result.
            current_keys = set(keys)
            for old in list(_CACHE):
                if old[3] != model or old[4] != identity or (old[0] == campaign and old not in current_keys):
                    del _CACHE[old]
            cached = [_CACHE.get(key) if identity is not None else None for key in keys]
        missing = [index for index, vector in enumerate(cached) if vector is None]
        response = _request_json("/api/embed", {"model": model, "input": [query_text] + [documents[index] for index in missing], "truncate": False}, deadline, MAX_RESPONSE_BYTES)
        embedded = _vectors(response, 1 + len(missing))
        query_vector = embedded[0]
        for index, vector in zip(missing, embedded[1:]):
            cached[index] = vector
        if any(len(vector) != len(query_vector) for vector in cached):
            raise ValueError("Cached embedding dimensions changed")
        _remaining(deadline)
        if identity is not None:
            with _CACHE_LOCK:
                for key, vector in zip(keys, cached):
                    _CACHE[key] = vector
                    _CACHE.move_to_end(key)
                while len(_CACHE) > MAX_CACHE_ENTRIES:
                    _CACHE.popitem(last=False)
        ranked = []
        for (source, lexical), vector in zip(candidates, cached):
            cosine = sum(left * right for left, right in zip(query_vector, vector))
            if lexical or cosine >= SEMANTIC_MIN_COSINE:
                score = 0.85 * cosine + 0.15 * lexical / max(1, len(words))
                ranked.append((source, score))
        ranked.sort(key=lambda item: (-item[1], item[0]["ref"], item[0]["revision"]))
        return [source for source, _ in ranked]
    except (OSError, ValueError, TypeError, OverflowError, http.client.HTTPException):
        return fallback
    finally:
        _EMBED_LOCK.release()
