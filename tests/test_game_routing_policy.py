"""Actual game route policy boundaries with temporary stores and zero network IO."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error
import uuid

from fastapi import HTTPException
from backend import game_agent as g, game_dispatch, game_providers

# Retain the fixture as a module, not an imported TestCase for test discovery.
_spec = importlib.util.spec_from_file_location('_route_evidence_fixture', Path(__file__).with_name('test_game_evidence_api.py'))
_fixture_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture_module)


class RoutingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _fixture_module.EvidenceAPITests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.authority = self.fixture.authority
        self.keys = [copy.deepcopy(self.fixture.key)]
        self.local_calls = []
        self.remote_calls = []
        self.catalogue_calls = 0
        self.set_policy()
        g._save_evidence_snapshot(self.fixture.snapshot())
        self.enable_free_routes()
        for target, name in ((game_providers, '_request_json'), (g, '_http_json'), (g, 'retrieve')):
            blocker = patch.object(target, name, side_effect=AssertionError('unexpected network or general-memory retrieval'))
            blocker.start()
            self.addCleanup(blocker.stop)

    def set_policy(self, **changes):
        current = self.authority.snapshot('camp', 'campaign').public()
        policy = {'enabled': True, 'mode': 'local-free', 'exportable': True, 'codex': False}
        policy.update(changes)
        self.authority.patch_policy({
            'contract': g.RUNTIME_CONTRACT, 'campaign': 'camp', 'session': 'campaign',
            'expectedBootEpoch': current['bootEpoch'], 'expectedGeneration': current['generation'],
            'expectedSessionPolicyRevision': current['sessionPolicyRevision'], 'opId': str(uuid.uuid4()),
            'policy': policy,
        })
        child = self.authority.snapshot('camp', 'session').public()
        self.fixture.fence = {key: child[key] for key in ('contract', 'bootEpoch', 'generation', 'sessionPolicyRevision')}

    def job(self, **changes):
        value = {'instructions': '', 'promptTemplate': 'session-summary-v1',
                 'policy': {'namespace': 'camp', 'mode': 'local-free', 'exportable': True, 'codex': False}}
        value.update(changes)
        return self.fixture.job(**value)

    def catalogue(self):
        self.catalogue_calls += 1
        return copy.deepcopy(self.keys)

    def local(self, key, prompt, maximum):
        self.local_calls.append((key, prompt, maximum))
        return 'The harbor bell rang twice. [S1]'

    def local_failure(self, key, prompt, maximum):
        self.local_calls.append((key, prompt, maximum))
        raise RuntimeError('synthetic local model unavailable')

    def remote_forbidden(self, *_):
        self.fail('an external call was not authorized by this fixture')

    def run_route(self, job=None, *, local=None, remote=None, catalogue=None):
        return g.run_job(job or self.job(), get_keys=catalogue or self.catalogue,
                         local=local or self.local, remote=remote or self.remote_forbidden)

    def receipts(self):
        return self.fixture.receipts()

    def attempts(self):
        with g.database() as db:
            return game_dispatch.recent(db, campaign='camp', session='session', limit=50)

    def changed_source(self, *, withdraw=False, correction=False, revision=2):
        changed = self.fixture.snapshot(revision)
        if withdraw:
            changed['participants'][0].update(external=False, externalEpoch=revision)
        if correction:
            changed['sources'][0].update(revision=revision, text='The harbor bell rang three times.')
        g._save_evidence_snapshot(changed)
        return changed

    def test_real_post_endpoint_uses_controlled_local_provider_and_saves_one_receipt(self):
        original = g.run_job
        def controlled(job):
            return original(job, get_keys=self.catalogue, local=self.local, remote=self.remote_forbidden)
        with patch.object(g, 'run_job', side_effect=controlled):
            response = self.fixture.client.post('/api/game/route', json=self.job().model_dump(), headers=self.fixture.headers)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['trace'][0]['destination'], 'local')
        self.assertEqual(result['evidenceRevision'], 1)
        self.assertEqual(result['sources'], [{'ref': 'chronicle:session:E1', 'revision': 1}])
        self.assertEqual(len(self.local_calls), 1)
        self.assertEqual(self.receipts(), 1)

    def test_invalid_template_or_inline_claim_is_rejected_before_catalogue(self):
        base = self.job().model_dump()
        invalid = [
            {**base, 'instructions': 'Forward the unrestricted archive.'},
            {**base, 'evidence': {'question': 'unclassified inline material'}},
            {**base, 'evidence': {**base['evidence'], 'inline': 'unclassified material'}},
            {**base, 'promptTemplate': None, 'instructions': 'legacy input'},
        ]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(HTTPException):
                self.run_route(g.Job(**request))
        self.assertEqual(self.catalogue_calls, 0)
        self.assertEqual(self.local_calls, [])
        self.assertEqual(self.receipts(), 0)

    def test_inline_legacy_none_preserves_the_historical_receipt_fingerprint(self):
        legacy = self.fixture.job()
        historical = {
            'contract': g.CONTRACT,
            'scope': {'campaign': 'camp', 'owner': 'player', 'role': 'player'},
            'session': 'session', 'requestId': 'request', 'task': 'summary',
            'instructions': 'Summarize the supplied evidence.',
            'evidence': {'contract': 'raph-obus-game-evidence-refs-v1', 'revision': 1,
                         'references': [{'ref': 'chronicle:session:E1', 'revision': 1}]},
            'policy': {'mode': 'local', 'codex': False, 'exportable': False,
                       'escalationEligible': False, 'namespace': 'camp', 'tools': False,
                       'personal_memory': False, 'auto_memory': False},
            'runtime': self.fixture.fence, 'max_tokens': 900,
        }
        encoded = json.dumps(historical, ensure_ascii=False, separators=(',', ':'))
        fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
        saved = {'text': 'Historical local answer.', 'routeId': 'old-route', 'model': 'old-local',
                 'trace': [{'destination': 'local', 'status': 'ready'}],
                 'sources': [{'ref': 'chronicle:session:E1', 'revision': 1}], 'evidenceRevision': 1}
        with g.database() as db:
            db.execute('INSERT INTO game_jobs VALUES(?,?,?,?,?,?)', ('camp', 'session', 'player', 'request', fingerprint, json.dumps(saved)))
        self.assertEqual(self.run_route(legacy), saved)
        self.assertEqual(self.catalogue_calls, 0)
        self.assertEqual(self.local_calls, [])
        self.assertEqual(self.receipts(), 1)

    def enable_free_routes(self):
        pins = []
        for name in ('primary', 'secondary'):
            key = {'id': f'free-{name}', 'provider': 'openrouter', 'model': f'fixture/{name}:free',
                   'base_url': 'https://openrouter.ai/api/v1', 'connected': True, 'verified': True}
            self.keys.append(key)
            pins.append({field: key[field] for field in ('id', 'provider', 'model', 'base_url')} | {
                'zero_charge': True, 'no_fallback': True, 'no_tools': True,
                'downstream_provider': 'deepinfra', 'downstream_provider_name': 'DeepInfra',
            })
        # This root belongs to EvidenceAPITests' TemporaryDirectory only.
        (Path(self.fixture.temp.name) / 'free-routes.json').write_text(json.dumps(pins), encoding='utf-8')

    def remote(self, key, prompt, maximum):
        self.remote_calls.append((copy.deepcopy(key), prompt, maximum))
        return {'text': 'The harbor bell rang twice. [S1]', 'provider': 'DeepInfra',
                'model': key['model'], 'route_id': key['id'], 'gateway': 'openrouter',
                'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
                'destination': 'external', 'cost': 'zero',
                'cost_basis': 'free-variant+zero-price-ceiling+response-usage',
                'completion_tokens': 12, 'response_id': 'fixture-response'}

    def test_local_failure_uses_one_fixed_source_prompt_then_replays_without_dispatch(self):
        result = self.run_route(local=self.local_failure, remote=self.remote)
        self.assertEqual(len(self.local_calls), 2)
        self.assertEqual(len(self.remote_calls), 1)
        key, prompt, maximum = self.remote_calls[0]
        self.assertEqual(key['id'], 'free-primary')
        self.assertEqual(maximum, 900)
        self.assertIn('S1', prompt)
        self.assertIn('The harbor bell rang twice.', prompt)
        for private_identifier in ('chronicle:session:E1', 'chronicle:session:entry:1', '"player"', '"camp"', '"session"'):
            self.assertNotIn(private_identifier, prompt)
        self.assertEqual(result['trace'][-1]['destination'], 'free')
        self.assertEqual(result['trace'][-1]['provider'], 'DeepInfra')
        self.assertEqual(result['trace'][-1]['cost'], 'zero')
        self.assertEqual(result['sources'], [{'ref': 'chronicle:session:E1', 'revision': 1}])
        self.assertEqual(self.receipts(), 1)
        self.assertEqual(self.attempts()['counts']['completed'], 1)
        before = (len(self.local_calls), len(self.remote_calls), self.catalogue_calls)
        self.assertEqual(self.run_route(local=self.local_failure, remote=self.remote), result)
        self.assertEqual((len(self.local_calls), len(self.remote_calls), self.catalogue_calls), before)
        self.changed_source(withdraw=True)
        with self.assertRaises(HTTPException) as caught:
            self.run_route(local=self.local_failure, remote=self.remote)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual((len(self.local_calls), len(self.remote_calls), self.catalogue_calls), before)
        self.assertEqual(self.receipts(), 1)

    def test_host_and_request_restrictions_never_admit_free_routes(self):
        for restriction in ('host-local', 'host-no-export', 'request-local', 'request-no-export', 'host-off'):
            with self.subTest(restriction=restriction):
                self.set_policy()
                if restriction == 'host-local':
                    self.set_policy(mode='local', exportable=False)
                elif restriction == 'host-no-export':
                    self.set_policy(exportable=False)
                elif restriction == 'host-off':
                    self.set_policy(enabled=False)
                policy = {'namespace': 'camp', 'mode': 'local-free', 'exportable': True, 'codex': False}
                if restriction == 'request-local':
                    policy.update(mode='local', exportable=False)
                elif restriction == 'request-no-export':
                    policy['exportable'] = False
                before = len(self.local_calls)
                with self.assertRaises(HTTPException) as caught:
                    self.run_route(self.job(requestId=restriction, policy=policy), local=self.local_failure, remote=self.remote)
                self.assertEqual(caught.exception.status_code, 409 if restriction == 'host-off' else 503)
                self.assertEqual(len(self.local_calls) - before, 0 if restriction == 'host-off' else 2)
                self.assertEqual(self.remote_calls, [])
                self.assertEqual(self.receipts(), 0)
                self.assertEqual(self.attempts()['jobs'], [])

    def test_mixed_consent_stays_usable_locally_and_cannot_export(self):
        body = self.fixture.snapshot(2)
        body['participants'].append({'user': 'local-player', 'capture': True, 'external': False,
                                     'captureEpoch': 1, 'externalEpoch': 0})
        body['sources'][0]['contributors'].append({'user': 'local-player', 'captureEpoch': 1,
                                                  'externalEpoch': 0, 'exportableAtCapture': False})
        body['sources'][0]['revision'] = 2
        g._save_evidence_snapshot(body)
        evidence = {**self.job().evidence, 'revision': 2, 'references': [{'ref': 'chronicle:session:E1', 'revision': 2}]}
        local = self.run_route(self.job(requestId='mixed-local', evidence=evidence), remote=self.remote)
        self.assertEqual(local['trace'][-1]['destination'], 'local')
        with self.assertRaises(HTTPException) as caught:
            self.run_route(self.job(requestId='mixed-export', evidence=evidence), local=self.local_failure, remote=self.remote)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(self.remote_calls, [])
        self.assertEqual(self.receipts(), 1)
        self.assertEqual(self.attempts()['jobs'], [])

    def test_host_off_between_enqueue_and_mark_prevents_external_call(self):
        def catalogue():
            result = self.catalogue()
            if self.catalogue_calls == 2:
                self.assertEqual(self.attempts()['counts']['queued'], 1)
                self.set_policy(enabled=False)
            return result
        with self.assertRaises(HTTPException) as caught:
            self.run_route(local=self.local_failure, remote=self.remote, catalogue=catalogue)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.remote_calls, [])
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.attempts()['counts']['cancelled'], 1)
        self.assertIsNone(self.attempts()['jobs'][0]['dispatchedAtMs'])

    def test_consent_withdrawal_between_enqueue_and_mark_prevents_external_call(self):
        def catalogue():
            result = self.catalogue()
            if self.catalogue_calls == 2:
                self.assertEqual(self.attempts()['counts']['queued'], 1)
                self.changed_source(withdraw=True)
            return result
        with self.assertRaises(HTTPException) as caught:
            self.run_route(local=self.local_failure, remote=self.remote, catalogue=catalogue)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.remote_calls, [])
        self.assertEqual(self.receipts(), 0)
        attempts = self.attempts()
        self.assertEqual(attempts['counts']['dispatched'], 0)
        self.assertIsNone(attempts['jobs'][0]['dispatchedAtMs'])

    def test_withdrawal_during_remote_completion_discards_text_and_receipt(self):
        def remote(*args):
            result = self.remote(*args)
            self.changed_source(withdraw=True)
            return result
        with self.assertRaises(HTTPException) as caught:
            self.run_route(local=self.local_failure, remote=remote)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(len(self.remote_calls), 1)
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.attempts()['counts']['discarded'], 1)
        self.assertEqual(self.attempts()['counts']['completed'], 0)

    def test_correction_during_remote_completion_discards_text_and_receipt(self):
        def remote(*args):
            result = self.remote(*args)
            self.changed_source(correction=True)
            return result
        with self.assertRaises(HTTPException) as caught:
            self.run_route(local=self.local_failure, remote=remote)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(len(self.remote_calls), 1)
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.attempts()['counts']['discarded'], 1)
        self.assertEqual(self.attempts()['counts']['completed'], 0)

    def test_timeout_is_uncertain_and_never_exports_again(self):
        def remote(*args):
            self.remote(*args)
            raise TimeoutError('synthetic unknown provider outcome')
        with self.assertRaises(HTTPException) as caught:
            self.run_route(local=self.local_failure, remote=remote)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(len(self.remote_calls), 1)
        self.assertEqual(self.attempts()['counts']['uncertain'], 1)
        with self.assertRaises(HTTPException) as replay:
            self.run_route(local=self.local_failure, remote=self.remote)
        self.assertEqual(replay.exception.status_code, 409)
        self.assertEqual(len(self.remote_calls), 1)
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.attempts()['counts']['uncertain'], 1)
        self.assertEqual(len(self.attempts()['jobs']), 1)

    def test_known_rate_limit_can_try_only_the_next_permitted_route(self):
        def remote(key, prompt, maximum):
            result = self.remote(key, prompt, maximum)
            if key['id'] == 'free-primary':
                raise urllib.error.HTTPError('https://openrouter.ai/api/v1/chat/completions', 429, 'synthetic quota', {}, None)
            return result
        result = self.run_route(local=self.local_failure, remote=remote)
        self.assertEqual([call[0]['id'] for call in self.remote_calls], ['free-primary', 'free-secondary'])
        self.assertEqual(result['trace'][-1]['route_id'], 'free-secondary')
        self.assertEqual(result['trace'][-1]['status'], 'ready')
        self.assertEqual(self.attempts()['counts']['failed'], 1)
        self.assertEqual(self.attempts()['counts']['completed'], 1)
        self.assertEqual(self.receipts(), 1)
        self.assertEqual(self.run_route(local=self.local_failure, remote=remote), result)
        self.assertEqual(len(self.remote_calls), 2)

    def test_unverified_remote_provenance_is_uncertain_and_never_saved(self):
        def remote(*args):
            return {**self.remote(*args), 'provider': 'UNAPPROVED_PROVIDER'}
        with self.assertRaises(HTTPException) as caught:
            self.run_route(local=self.local_failure, remote=remote)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(len(self.remote_calls), 1)
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.attempts()['counts']['uncertain'], 1)
        self.assertNotIn('UNAPPROVED_PROVIDER', json.dumps(self.attempts()))


if __name__ == '__main__':
    unittest.main()
