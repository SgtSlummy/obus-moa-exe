"""Memory integration checks use disposable stores, never campaign history."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from backend import game_mempalace as memory
from backend import game_retrieval as retrieval


def source(ref='public', **changes):
    return dict(campaign='alpha', ref=ref, revision=1, audience='party', owner='',
                text='The northern bridge is open and safe for crossing.',
                provenance='fixture', exportable=False, deleted=False, **{}) | changes


@pytest.fixture
def configured(monkeypatch, tmp_path):
    config = dict(enabled=True, python=sys.executable,
                  palace_path=str(tmp_path / 'palace'), model_path=str(tmp_path / 'model'))
    monkeypatch.setattr(memory, '_config', lambda: config)
    monkeypatch.setattr(memory, '_LAST_STATUS', 'not_queried')
    return config


def completion(payload, hits=None):
    value = json.loads(payload)
    return SimpleNamespace(stdout=json.dumps({'hits': hits if hits is not None else
        [{'id': item['id'], 'cosine': 0.8} for item in value['sources']]}))


def test_returns_current_objects_and_uses_bounded_private_worker(monkeypatch, configured):
    record = source()
    def run(argv, **kwargs):
        assert argv[1:4] == ['-I', '-X', 'utf8']
        assert kwargs['timeout'] == 15
        assert kwargs['env']['HF_HUB_OFFLINE'] == '1'
        assert 'shell' not in kwargs
        return completion(kwargs['input'])
    monkeypatch.setattr(memory.subprocess, 'run', run)
    result = memory.rank_current_sources('alpha', 'cross the bridge', [record])
    assert result[0][0] is record
    assert result[0][1] == 0.8
    assert memory.memory_status()['last_query_status'] == 'ready'


@pytest.mark.parametrize('changed', [dict(campaign='beta'), dict(deleted=True), dict(revision=-1)])
def test_foreign_deleted_or_invalid_sources_never_reach_worker(monkeypatch, configured, changed):
    monkeypatch.setattr(memory.subprocess, 'run', lambda *a, **k: pytest.fail('worker called'))
    assert memory.rank_current_sources('alpha', 'bridge', [source(**changed)]) is None


@pytest.mark.parametrize('hits', [
    [{'id': 'unrequested-secret', 'cosine': 0.99}],
    [{'id': 'x', 'cosine': float('nan')}],
    [{'id': 'x', 'cosine': 3}],
    [{'id': 'x', 'cosine': True}],
])
def test_invalid_or_unrequested_results_are_discarded(monkeypatch, configured, hits):
    monkeypatch.setattr(memory.subprocess, 'run', lambda *a, **k: completion(k['input'], hits))
    assert memory.rank_current_sources('alpha', 'bridge', [source()]) is None
    assert memory.memory_status()['last_query_status'] == 'fallback'


def test_timeout_keeps_lexical_fallback(monkeypatch, configured):
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired('private-worker', 15)
    monkeypatch.setattr(memory.subprocess, 'run', fail)
    monkeypatch.delenv('OBUS_GAME_EMBEDDING_MODEL', raising=False)
    record = source()
    assert retrieval.rank_sources('alpha', 'bridge', [record]) == [record]
    assert memory.memory_status()['last_query_status'] == 'fallback'


def test_semantic_relevance_without_literal_keyword(monkeypatch):
    record = source(text='The healer recovered the missing medicine.')
    monkeypatch.setattr(memory, 'rank_current_sources', lambda *args: [(record, 0.9)])
    assert retrieval.rank_sources('alpha', 'physician remedy', [record]) == [record]
    monkeypatch.setattr(memory, 'rank_current_sources', lambda *args: [(record, 0.1)])
    assert retrieval.rank_sources('alpha', 'unrelated', [record]) == []


def test_revisions_acl_text_and_embedding_prefix_change_identity(monkeypatch, configured):
    identities = []
    def run(*args, **kwargs):
        identities.append(json.loads(kwargs['input'])['sources'][0]['id'])
        return completion(kwargs['input'])
    monkeypatch.setattr(memory.subprocess, 'run', run)
    for record in [source(), source(revision=2), source(audience='host'), source(text='The bridge is closed.')]:
        memory.rank_current_sources('alpha', 'bridge', [record])
    assert len(set(identities)) == 4
    memory.rank_current_sources('alpha', 'bridge', [source()])
    assert identities[-1] == identities[0]


def test_database_filters_before_memory_and_rechecks_changes(monkeypatch, tmp_path):
    from backend import game_agent as game
    monkeypatch.setattr(game, 'ROOT', tmp_path)
    for record in [source(), source('gm', audience='host'), source('private', audience='private', owner='other'),
                   source('foreign', campaign='beta'), source('deleted', deleted=True)]:
        game.ingest(game.Source(**record))
    calls = []
    def rank(campaign, query, candidates):
        calls.append(candidates)
        assert [item['ref'] for item in candidates] == ['public']
        game.ingest(game.Source(**source(revision=2, audience='host')))
        return candidates
    monkeypatch.setattr(game, 'rank_sources', rank)
    assert game.retrieve(game.Scope(campaign='alpha', owner='alice', role='player'), 'bridge') == []
    assert len(calls) == 1


def test_missing_or_incomplete_model_configuration_is_disabled(monkeypatch, tmp_path):
    config = tmp_path / 'config.json'
    monkeypatch.setenv('OBUS_GAME_MEMORY_CONFIG', str(config))
    assert memory._config() is None
    config.write_text(json.dumps(dict(enabled=True, python=sys.executable,
        palace_path=str(tmp_path / 'palace'), model_path=str(tmp_path / 'absent'))))
    assert memory._config() is None


def test_real_mempalace_persistence_and_exact_candidate_isolation(monkeypatch, tmp_path):
    python = os.environ.get('OPERATOR_TEST_MEMORY_PYTHON')
    model = os.environ.get('OPERATOR_TEST_MEMORY_MODEL')
    if not python or not model:
        pytest.skip('Set the explicit local MemPalace Python and cached model to run the real backend check.')
    config = dict(enabled=True, python=python, palace_path=str(tmp_path / 'palace'), model_path=model)
    monkeypatch.setattr(memory, '_config', lambda: config)
    first = source('gm-secret', audience='host', text='The dragon guards a hidden entrance behind the waterfall.')
    assert memory.rank_current_sources('alpha', 'dragon entrance', [first])[0][0] is first
    public = source('public', text='A merchant sells rope beside the river.')
    result = memory.rank_current_sources('alpha', 'dragon entrance', [public])
    assert len(result) == 1 and result[0][0] is public
    changed = source('public', revision=2, text='The merchant has left town.')
    assert memory.rank_current_sources('alpha', 'merchant', [changed])[0][0] is changed
    assert list((tmp_path / 'palace').rglob('sqlite_exact.sqlite3'))
    assert memory.memory_status()['last_query_status'] == 'ready'
