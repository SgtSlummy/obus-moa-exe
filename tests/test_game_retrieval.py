"""Controlled fixtures; never contact a model, provider or production database."""
from __future__ import annotations

import copy
import io
import json
import math
import time

import pytest

from backend import game_retrieval as retrieval


def source(ref, text, *, campaign="harbor", revision=1, audience="party", owner="", deleted=False):
    return {"campaign": campaign, "ref": ref, "revision": revision, "audience": audience,
            "owner": owner, "text": text, "provenance": "fixture", "exportable": False, "deleted": deleted}


LOCAL_MODEL = {"details": {"format": "gguf"}, "model_info": {"general.architecture": "bert"}, "capabilities": ["embedding"], "modelfile": "FROM /models/blobs/sha256-" + "a" * 64}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.delenv("OBUS_GAME_EMBEDDING_MODEL", raising=False)
    with retrieval._CACHE_LOCK:
        retrieval._CACHE.clear()

    def forbidden(*_args, **_kwargs):
        pytest.fail("A controlled retrieval fixture attempted a real network connection")

    monkeypatch.setattr(retrieval.http.client, "HTTPConnection", forbidden)
    yield
    with retrieval._CACHE_LOCK:
        retrieval._CACHE.clear()


def embedding_fixture(monkeypatch, vectors=None):
    calls = []
    vectors = vectors or {}
    monkeypatch.setenv("OBUS_GAME_EMBEDDING_MODEL", "fixture-embed:v1")

    def request(path, payload, deadline, limit):
        assert deadline > time.monotonic()
        calls.append((path, copy.deepcopy(payload)))
        if path == "/api/show":
            return copy.deepcopy(LOCAL_MODEL)
        assert path == "/api/embed"
        return {"embeddings": [vectors.get(text, [1.0, 0.0]) for text in payload["input"]]}

    monkeypatch.setattr(retrieval, "_request_json", request)
    return calls


def test_semantic_synonyms_rank_without_lexical_overlap_and_omit_unrelated(monkeypatch):
    calls = embedding_fixture(monkeypatch, {
        "Injured soldiers recuperate?": [1, 0],
        "The infirmary welcomes wounded veterans.": [1, 0.1],
        "The merchant sells lanterns.": [0, 1],
        "A distant desert dune.": [-1, 0],
    })
    relevant = source("hospital", "The infirmary welcomes wounded veterans.")
    records = [source("dune", "A distant desert dune."), source("market", "The merchant sells lanterns."), relevant]
    result = retrieval.rank_sources("harbor", "Injured soldiers recuperate?", records)
    assert len(result) == 1 and result[0] is relevant
    assert [path for path, _ in calls] == ["/api/show", "/api/embed"]


def test_lexical_fallback_is_deterministic_and_never_sends_text_when_disabled():
    first, second = source("a", "lantern signal"), source("b", "lantern signal")
    irrelevant = source("c", "unrelated ocean")
    assert retrieval.rank_sources("harbor", "lantern", [second, irrelevant, first]) == [first, second]
    assert retrieval.rank_sources("harbor", "", [first]) == []
    assert retrieval.rank_sources("harbor", "   ", [first]) == []


@pytest.mark.parametrize("failure", [
    TimeoutError("deadline"), OSError("unavailable"), {"embeddings": []},
    {"embeddings": [[1, 0], [1]]}, {"embeddings": [[1, 0], [True, 0]]},
    {"embeddings": [[1, 0], [math.inf, 0]]}, {"embeddings": [[1, 0], [math.nan, 0]]},
    {"embeddings": [[1, 0], [0, 0]]}, {"embeddings": [[1] * 2049, [1] * 2049]},
    {"embeddings": [[1, 0], "wrong"]},
])
def test_embedding_failures_return_lexical_matches_without_cache_writes(monkeypatch, failure):
    embedding_fixture(monkeypatch)

    def request(path, *_args):
        if path == "/api/show":
            return LOCAL_MODEL
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(retrieval, "_request_json", request)
    wanted = source("one", "lantern")
    assert retrieval.rank_sources("harbor", "lantern", [wanted]) == [wanted]
    assert not retrieval._CACHE


@pytest.mark.parametrize("metadata", [
    {}, {**LOCAL_MODEL, "remote_host": "https://provider.invalid"},
    {**LOCAL_MODEL, "remote_model": "paid-cloud-model"},
    {**LOCAL_MODEL, "details": {"format": "gguf", "remote_host": "https://provider.invalid"}},
    {**LOCAL_MODEL, "details": {"format": "cloud"}},
    {**LOCAL_MODEL, "model_info": {}}, {**LOCAL_MODEL, "capabilities": ["completion"]},
])
def test_model_must_prove_local_embedding_capability_before_any_text_is_sent(monkeypatch, metadata):
    embedding_fixture(monkeypatch)
    calls = []

    def request(path, payload, *_args):
        calls.append((path, payload))
        return metadata

    monkeypatch.setattr(retrieval, "_request_json", request)
    wanted = source("one", "private lantern evidence")
    assert retrieval.rank_sources("harbor", "lantern", [wanted]) == [wanted]
    assert len(calls) == 1 and calls[0][0] == "/api/show"
    assert "lantern" not in json.dumps(calls)


@pytest.mark.parametrize("model", ["some-model:cloud", "https://provider.invalid/model", "auto model", "x" * 161])
def test_cloud_or_ambiguous_model_names_never_dispatch(monkeypatch, model):
    calls = embedding_fixture(monkeypatch)
    monkeypatch.setenv("OBUS_GAME_EMBEDDING_MODEL", model)
    wanted = source("one", "lantern")
    assert retrieval.rank_sources("harbor", "lantern", [wanted]) == [wanted]
    assert calls == []


def test_cache_only_reranks_current_sources_and_invalidates_revision_text_and_access(monkeypatch):
    calls = embedding_fixture(monkeypatch)
    original = source("same", "a safe harbor")
    assert retrieval.rank_sources("harbor", "shelter", [original]) == [original]
    current = {**original}
    assert retrieval.rank_sources("harbor", "shelter", [current])[0] is current
    assert len(calls[-1][1]["input"]) == 1  # Query is fresh; document vector is reused.
    for updated in [
        {**current, "revision": 2},
        {**current, "revision": 2, "text": "a corrected sanctuary"},
        {**current, "revision": 2, "audience": "private", "owner": "alice"},
    ]:
        result = retrieval.rank_sources("harbor", "shelter", [updated])
        assert result[0] is updated and len(calls[-1][1]["input"]) == 2
        assert len(retrieval._CACHE) == 1
    other = source("same", "a safe harbor", campaign="island")
    assert retrieval.rank_sources("island", "shelter", [other])[0] is other
    assert len(calls[-1][1]["input"]) == 2
    monkeypatch.setenv("OBUS_GAME_EMBEDDING_MODEL", "fixture-embed:v2")
    assert retrieval.rank_sources("harbor", "shelter", [original])[0] is original
    assert len(calls[-1][1]["input"]) == 2
    assert {key[3] for key in retrieval._CACHE} == {"fixture-embed:v2"}


def test_replacing_weights_under_the_same_model_tag_invalidates_cached_vectors(monkeypatch):
    embedding_fixture(monkeypatch)
    identity = ["a"]
    calls = []

    def request(path, payload, *_args):
        if path == "/api/show":
            return {**LOCAL_MODEL, "modelfile": "FROM /models/blobs/sha256-" + identity[0] * 64}
        calls.append(payload["input"])
        return {"embeddings": [[1, 0]] + [[1, 0] if identity[0] == "a" else [0, 1] for _ in payload["input"][1:]]}

    monkeypatch.setattr(retrieval, "_request_json", request)
    current = source("place", "sanctuary")
    assert retrieval.rank_sources("harbor", "shelter", [current]) == [current]
    assert retrieval.rank_sources("harbor", "shelter", [current]) == [current]
    assert len(calls[-1]) == 1
    identity[0] = "b"
    assert retrieval.rank_sources("harbor", "shelter", [current]) == []
    assert len(calls[-1]) == 2
    assert len(retrieval._CACHE) == 1


def test_model_without_immutable_weight_identity_never_reuses_vectors(monkeypatch):
    embedding_fixture(monkeypatch)
    calls = []

    def request(path, payload, *_args):
        if path == "/api/show":
            return {**LOCAL_MODEL, "modelfile": "FROM /models/mutable.gguf"}
        calls.append(payload["input"])
        return {"embeddings": [[1, 0] for _ in payload["input"]]}

    monkeypatch.setattr(retrieval, "_request_json", request)
    current = source("place", "sanctuary")
    for _ in range(2):
        assert retrieval.rank_sources("harbor", "shelter", [current]) == [current]
    assert [len(batch) for batch in calls] == [2, 2]
    assert not retrieval._CACHE


def test_foreign_campaigns_deleted_and_absent_acl_sources_never_enter_embedding_batch(monkeypatch):
    calls = embedding_fixture(monkeypatch)
    visible = source("public", "lantern")
    hidden = source("secret", "invisible private secret", audience="private", owner="other")
    # The caller omits `hidden` at its SQL authorization boundary.
    records = [visible, source("foreign", "other campaign secret", campaign="island"), source("deleted", "deleted secret", deleted=True)]
    assert retrieval.rank_sources("harbor", "lantern", records) == [visible]
    captured = json.dumps(calls)
    for text in [hidden["text"], "other campaign secret", "deleted secret"]:
        assert text not in captured
    before = len(calls)
    assert retrieval.rank_sources("harbor", "lantern", [{**visible, "deleted": True}]) == []
    assert len(calls) == before


def test_request_candidate_text_and_cache_bounds_with_nomic_prefixes(monkeypatch):
    calls = embedding_fixture(monkeypatch)
    monkeypatch.setenv("OBUS_GAME_EMBEDDING_MODEL", "nomic-embed-text:latest")
    records = [source(f"{index:04}", "lantern " + "x" * 15000) for index in range(100)]
    result = retrieval.rank_sources("harbor", "lantern " + "q" * 10000, reversed(records))
    assert len(result) == retrieval.MAX_CANDIDATES
    batch = calls[-1][1]["input"]
    assert len(batch) == retrieval.MAX_CANDIDATES + 1
    assert batch[0].startswith("search_query: ")
    assert all(text.startswith("search_document: ") for text in batch[1:])
    assert sum(map(len, batch)) <= retrieval.MAX_TOTAL_TEXT_CHARS
    assert len(batch[0]) <= retrieval.MAX_QUERY_CHARS + len("search_query: ")
    assert all(len(text) <= retrieval.MAX_SOURCE_CHARS + len("search_document: ") for text in batch[1:])
    assert [item["ref"] for item in result] == [f"{index:04}" for index in range(32)]
    for campaign_index in range(5):
        campaign = f"campaign-{campaign_index}"
        retrieval.rank_sources(campaign, "lantern", [{**record, "campaign": campaign} for record in records])
    assert len(retrieval._CACHE) == retrieval.MAX_CACHE_ENTRIES


def test_scan_bound_and_busy_embedding_worker_use_lexical_results(monkeypatch):
    calls = embedding_fixture(monkeypatch)
    monkeypatch.setattr(retrieval, "MAX_SCANNED_SOURCES", 2)
    first = source("first", "lantern")
    beyond = source("beyond", "lantern lantern")
    retrieval._EMBED_LOCK.acquire()
    try:
        assert retrieval.rank_sources("harbor", "lantern", [first, source("none", "unrelated"), beyond]) == [first]
    finally:
        retrieval._EMBED_LOCK.release()
    assert calls == []


def test_one_deadline_covers_model_check_and_embedding(monkeypatch):
    embedding_fixture(monkeypatch)
    clock = [10.0]
    monkeypatch.setattr(retrieval.time, "monotonic", lambda: clock[0])
    calls = []

    def request(path, payload, deadline, limit):
        calls.append((path, deadline))
        if path == "/api/show":
            clock[0] += retrieval.RETRIEVAL_SECONDS + 0.1
            return LOCAL_MODEL
        retrieval._remaining(deadline)
        pytest.fail("Expired retrieval reached inference")

    monkeypatch.setattr(retrieval, "_request_json", request)
    wanted = source("one", "lantern")
    assert retrieval.rank_sources("harbor", "lantern", [wanted]) == [wanted]
    assert len({deadline for _, deadline in calls}) == 1
    assert not retrieval._CACHE


class FakeSocket:
    def settimeout(self, timeout):
        assert timeout > 0

    def shutdown(self, how):
        pass


class FakeConnection:
    status = 200
    content = b'{"embeddings":[[1,0]]}'
    declared_length = None
    instances = []

    def __init__(self, host, port, timeout):
        assert (host, port) == ("127.0.0.1", 11434)
        assert 0 < timeout <= retrieval.RETRIEVAL_SECONDS
        self.sock = FakeSocket()
        self.closed = False
        self.requests = []
        self.body = io.BytesIO(self.content)
        self.__class__.instances.append(self)

    def connect(self):
        pass

    def request(self, method, path, body, headers):
        self.requests.append((method, path, body, headers))

    def getresponse(self):
        return self

    def getheader(self, name):
        assert name == "Content-Length"
        return self.declared_length

    def read1(self, count):
        return self.body.read(count)

    def close(self):
        self.closed = True


def test_transport_is_direct_loopback_even_when_proxy_environment_is_set(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://provider.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://provider.invalid:8080")
    monkeypatch.setattr(retrieval.http.client, "HTTPConnection", FakeConnection)
    response = retrieval._request_json("/api/embed", {"model": "fixture", "input": ["sample"]}, time.monotonic() + retrieval.RETRIEVAL_SECONDS, 1024)
    assert response == {"embeddings": [[1, 0]]}
    connection = FakeConnection.instances[-1]
    assert connection.closed and len(connection.requests) == 1
    assert connection.requests[0][0:2] == ("POST", "/api/embed")


@pytest.mark.parametrize("status,content,declared", [
    (302, b"", None), (307, b"", None), (500, b"", None),
    (200, b"x" * 1025, None), (200, b"{}", "100000"),
    (200, b"{}", "-1"), (200, b"[]", None), (200, b"not json", None),
])
def test_transport_rejects_redirects_oversized_and_invalid_responses(monkeypatch, status, content, declared):
    monkeypatch.setattr(FakeConnection, "status", status)
    monkeypatch.setattr(FakeConnection, "content", content)
    monkeypatch.setattr(FakeConnection, "declared_length", declared)
    monkeypatch.setattr(retrieval.http.client, "HTTPConnection", FakeConnection)
    with pytest.raises(ValueError):
        retrieval._request_json("/api/embed", {"model": "fixture", "input": ["sample"]}, time.monotonic() + retrieval.RETRIEVAL_SECONDS, 1024)
    connection = FakeConnection.instances[-1]
    assert connection.closed and len(connection.requests) == 1


def test_deadline_interrupts_body_read_after_http_connection_detaches_socket(monkeypatch):
    import threading

    aborted = threading.Event()

    class DetachedSocket(FakeSocket):
        def shutdown(self, how):
            aborted.set()

    class DetachedConnection(FakeConnection):
        def connect(self):
            self.sock = DetachedSocket()

        def getresponse(self):
            self.sock = None  # Mirrors HTTPConnection with Connection: close.
            return self

        def read1(self, count):
            if not aborted.wait(1):
                pytest.fail("Retrieval deadline lost the detached response socket")
            raise OSError("response socket interrupted")

    monkeypatch.setattr(retrieval.http.client, "HTTPConnection", DetachedConnection)
    started = time.monotonic()
    with pytest.raises(OSError):
        retrieval._request_json("/api/embed", {"model": "fixture", "input": ["sample"]}, started + 0.05, 1024)
    assert aborted.is_set()
    assert time.monotonic() - started < 0.8
    assert DetachedConnection.instances[-1].closed


def test_actual_game_candidate_limit_excludes_tombstones_and_keeps_late_lexical_match(tmp_path, monkeypatch):
    from backend import game_agent as agent

    monkeypatch.setattr(agent, "ROOT", tmp_path / "private-game-fixture")
    monkeypatch.setattr(agent, "MAX_SCANNED_SOURCES", 2)
    for record in [source("a-deleted", "lantern", deleted=True),
                   source("b-deleted", "lantern", deleted=True),
                   source("c-irrelevant", "unrelated ocean"),
                   source("z-relevant", "lantern beacon")]:
        agent.ingest(agent.Source(**record))
    result = agent.retrieve(agent.Scope(campaign="harbor", role="player", owner="alice"), "lantern")
    assert [item["ref"] for item in result] == ["z-relevant"]


def test_actual_game_retrieval_authorizes_before_ranking_and_passes_current_corrections(tmp_path, monkeypatch):
    from backend import game_agent as agent

    monkeypatch.setattr(agent, "ROOT", tmp_path / "private-game-fixture")
    observations = []

    def rank(campaign, query, eligible):
        observations.append((campaign, query, copy.deepcopy(eligible)))
        return eligible

    monkeypatch.setattr(agent, "rank_sources", rank)
    records = [source("party", "public lantern"), source("gm", "GM secret", audience="host"),
               source("alice", "Alice private note", audience="private", owner="alice"),
               source("bob", "Bob private note", audience="private", owner="bob"),
               source("foreign", "other campaign", campaign="island")]
    for record in records:
        agent.ingest(agent.Source(**record))
    player = agent.Scope(campaign="harbor", role="player", owner="alice")
    host = agent.Scope(campaign="harbor", role="host", owner="alice")
    assert {item["ref"] for item in agent.retrieve(player, "query")} == {"party", "alice"}
    assert {item["ref"] for item in observations[-1][2]} == {"party", "alice"}
    assert {item["ref"] for item in agent.retrieve(host, "query")} == {"party", "gm", "alice"}
    assert {item["ref"] for item in observations[-1][2]} == {"party", "gm", "alice"}
    agent.ingest(agent.Source(**{**records[0], "revision": 2, "text": "corrected evidence"}))
    agent.ingest(agent.Source(**{**records[2], "revision": 2, "deleted": True, "text": ""}))
    agent.retrieve(player, "query")
    assert [(item["ref"], item["revision"], item["text"]) for item in observations[-1][2]] == [("party", 2, "corrected evidence")]
    agent.ingest(agent.Source(**{**records[0], "revision": 3, "audience": "host"}))
    assert agent.retrieve(player, "query") == []
    assert observations[-1][2] == []
