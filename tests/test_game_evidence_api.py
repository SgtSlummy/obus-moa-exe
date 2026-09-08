"""Signed evidence boundary and reference-job races, using temporary stores only."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import game_agent as g
from backend.game_runtime import RuntimeDenied


class EvidenceAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = patch.object(g, 'ROOT', Path(self.temp.name))
        self.root.start()
        self.addCleanup(self.root.stop)
        self.old_runtime = g.RUNTIME
        g.RUNTIME = None
        self.addCleanup(setattr, g, 'RUNTIME', self.old_runtime)
        self.authority = g.runtime_authority()
        master = self.authority.register({
            'contract': g.RUNTIME_CONTRACT, 'campaign': 'camp', 'session': 'campaign',
            'generation': str(uuid.uuid4()), 'expectedBootEpoch': self.authority.boot_epoch,
            'expectedGeneration': None, 'opId': str(uuid.uuid4()), 'leaseSeconds': 30,
        })['runtime']
        runtime = self.authority.register({
            'contract': g.RUNTIME_CONTRACT, 'campaign': 'camp', 'session': 'session',
            'generation': master['generation'], 'expectedBootEpoch': self.authority.boot_epoch,
            'expectedGeneration': None, 'opId': str(uuid.uuid4()), 'leaseSeconds': 30,
        })['runtime']
        self.fence = {key: runtime[key] for key in ('contract', 'bootEpoch', 'generation', 'sessionPolicyRevision')}
        self.key = {'id': 'key-local-ollama', 'provider': 'ollama', 'model': 'controlled-local', 'connected': True, 'verified': True}
        self.client = TestClient(g.app)
        self.addCleanup(self.client.close)
        self.headers = {'X-Obus-Game-Token': g.token()}

    def snapshot(self, revision=1):
        return {
            'contract': 'raph-obus-game-evidence-v1', 'campaign': 'camp', 'session': 'session',
            'revision': revision, 'runtime': self.fence,
            'participants': [{'user': 'player', 'capture': True, 'external': True, 'captureEpoch': 1, 'externalEpoch': 1}],
            'sources': [{
                'ref': 'chronicle:session:E1', 'revision': 1, 'audience': 'party', 'owner': '',
                'text': 'The harbor bell rang twice.', 'provenance': 'chronicle:session:entry:1',
                'deleted': False,
                'contributors': [{'user': 'player', 'captureEpoch': 1, 'externalEpoch': 1, 'exportableAtCapture': True}],
                'derivesFrom': [],
            }],
        }

    def job(self, **changes):
        value = {
            'contract': g.CONTRACT, 'scope': {'campaign': 'camp', 'owner': 'player', 'role': 'player'},
            'session': 'session', 'requestId': 'request', 'task': 'summary',
            'instructions': 'Summarize the supplied evidence.',
            'evidence': {'contract': 'raph-obus-game-evidence-refs-v1', 'revision': 1,
                         'references': [{'ref': 'chronicle:session:E1', 'revision': 1}]},
            'policy': {'namespace': 'camp', 'mode': 'local'}, 'runtime': self.fence,
        }
        value.update(changes)
        return g.Job(**value)

    def run_job(self, job=None, local=None):
        with patch.object(g, 'retrieve', side_effect=AssertionError('reference jobs cannot use legacy retrieval')):
            return g.run_job(job or self.job(), get_keys=lambda: [self.key],
                             local=local or (lambda *_: 'Two bell strokes were heard.'),
                             remote=lambda *_: self.fail('external dispatch is still disabled'))

    def receipts(self):
        with g.database() as db:
            return db.execute('SELECT COUNT(*) FROM game_jobs').fetchone()[0]

    def test_service_token_alone_cannot_sync(self):
        response = self.client.post('/api/game/evidence/snapshot', json=self.snapshot(), headers=self.headers)
        self.assertIn(response.status_code, (401, 403))
        with self.assertRaises(HTTPException):
            self.run_job()

    def test_endpoint_checks_exact_method_path_body_then_saves(self):
        body = self.snapshot()
        with patch.object(self.authority, 'verify_host') as verify:
            response = self.client.post('/api/game/evidence/snapshot', json=body, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        method, path, parsed, headers = verify.call_args.args
        self.assertEqual((method, path, parsed), ('POST', '/api/game/evidence/snapshot', body))
        self.assertEqual(headers['X-Obus-Game-Token'], self.headers['X-Obus-Game-Token'])
        receipt = response.json()
        self.assertEqual((receipt['revision'], receipt['sourceCount'], receipt['participantCount']), (1, 1, 1))
        self.assertNotIn('bell', response.text)
        self.assertNotIn('player', response.text)

    def test_verifier_failure_cannot_write(self):
        with patch.object(self.authority, 'verify_host', side_effect=RuntimeDenied(403, 'test_signature_denied')):
            response = self.client.post('/api/game/evidence/snapshot', json=self.snapshot(), headers=self.headers)
        self.assertEqual(response.status_code, 403)
        with self.assertRaises(HTTPException):
            self.run_job()

    def test_stream_size_is_rejected_before_host_verification(self):
        with patch.object(self.authority, 'verify_host') as verify:
            response = self.client.post('/api/game/evidence/snapshot', content=b' ' * (512 * 1024 + 1), headers=self.headers)
        self.assertEqual(response.status_code, 413)
        verify.assert_not_called()

    def test_malformed_and_nonobject_json_are_rejected(self):
        for data in (b'{', b'[]', b'null', b'\xff'):
            with self.subTest(data=data), patch.object(self.authority, 'verify_host') as verify:
                response = self.client.post('/api/game/evidence/snapshot', content=data, headers=self.headers)
                self.assertEqual(response.status_code, 400)
                verify.assert_not_called()

    def test_snapshot_extra_fields_and_coerced_revisions_are_rejected(self):
        for field, value in [('unrestrictedMemory', True), ('revision', '1'), ('revision', True)]:
            body = self.snapshot()
            body[field] = value
            with self.subTest(field=field, value=value), patch.object(self.authority, 'verify_host'):
                response = self.client.post('/api/game/evidence/snapshot', json=body, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)

    def test_sync_runtime_fence_is_checked_before_any_save(self):
        body = self.snapshot()
        body['runtime'] = {**self.fence, 'sessionPolicyRevision': self.fence['sessionPolicyRevision'] + 1}
        with self.assertRaises(HTTPException) as caught:
            g._save_evidence_snapshot(body)
        self.assertEqual(caught.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            self.run_job()

    def test_reference_job_resolves_only_requested_sources_and_replays(self):
        body = self.snapshot()
        secret = copy.deepcopy(body['sources'][0])
        secret.update(ref='host-secret', audience='host', text='UNRELATED SECRET')
        body['sources'].append(secret)
        g._save_evidence_snapshot(body)
        prompts = []
        result = self.run_job(local=lambda key, prompt, maximum: prompts.append(json.loads(prompt)) or 'Two bell strokes were heard.')
        replay = self.run_job(local=lambda *_: self.fail('replay called inference'))
        self.assertEqual(result, replay)
        self.assertEqual(result['evidenceRevision'], 1)
        self.assertEqual(result['sources'], [{'ref': 'chronicle:session:E1', 'revision': 1}])
        self.assertEqual(len(prompts), 1)
        self.assertNotIn('UNRELATED SECRET', json.dumps(prompts))
        self.assertIn('harbor bell', json.dumps(prompts))
        self.assertEqual(self.receipts(), 1)

    def test_unknown_reference_contract_or_inline_extras_never_fall_back(self):
        g._save_evidence_snapshot(self.snapshot())
        for evidence in [
            {'contract': 'raph-obus-game-evidence-refs-v2', 'revision': 1, 'references': []},
            {**self.job().evidence, 'inline': 'secret'},
            {**self.job().evidence, 'revision': True},
            {**self.job().evidence, 'references': []},
        ]:
            with self.subTest(evidence=evidence), self.assertRaises(HTTPException) as caught:
                self.run_job(self.job(evidence=evidence), local=lambda *_: self.fail('invalid evidence dispatched'))
            self.assertEqual(caught.exception.status_code, 422)

    def test_stale_acl_and_duplicate_references_do_not_dispatch(self):
        body = self.snapshot()
        body['sources'][0]['audience'] = 'host'
        g._save_evidence_snapshot(body)
        for evidence in [self.job().evidence,
                         {**self.job().evidence, 'revision': 0},
                         {**self.job().evidence, 'references': self.job().evidence['references'] * 2}]:
            with self.subTest(evidence=evidence), self.assertRaises(HTTPException):
                self.run_job(self.job(evidence=evidence), local=lambda *_: self.fail('unauthorized evidence dispatched'))
        self.assertEqual(self.receipts(), 0)

    def test_consent_change_invalidates_saved_response_replay(self):
        g._save_evidence_snapshot(self.snapshot())
        self.run_job()
        changed = self.snapshot(2)
        changed['participants'][0].update(external=False, externalEpoch=2)
        g._save_evidence_snapshot(changed)
        with self.assertRaises(HTTPException) as caught:
            self.run_job(local=lambda *_: self.fail('stale replay dispatched'))
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.receipts(), 1)

    def test_correction_during_inference_prevents_receipt(self):
        g._save_evidence_snapshot(self.snapshot())
        def local(*_):
            changed = self.snapshot(2)
            changed['sources'][0].update(revision=2, text='The bell rang three times.')
            g._save_evidence_snapshot(changed)
            return 'Outdated two-stroke response.'
        with self.assertRaises(HTTPException) as caught:
            self.run_job(local=local)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.receipts(), 0)

    def test_sync_between_final_runtime_check_and_commit_is_revalidated(self):
        g._save_evidence_snapshot(self.snapshot())
        original = g._receipt_transaction
        @contextmanager
        def interleaved(campaign, session, fence):
            changed = self.snapshot(2)
            changed['sources'] = []
            with patch.object(g, '_receipt_transaction', original):
                g._save_evidence_snapshot(changed)
            with original(campaign, session, fence) as db:
                yield db
        with patch.object(g, '_receipt_transaction', interleaved), self.assertRaises(HTTPException):
            self.run_job()
        self.assertEqual(self.receipts(), 0)

    def test_new_reference_request_after_correction_receives_only_current_text(self):
        g._save_evidence_snapshot(self.snapshot())
        changed = self.snapshot(2)
        changed['sources'][0].update(revision=2, text='The bell rang three times.')
        g._save_evidence_snapshot(changed)
        evidence = {'contract': 'raph-obus-game-evidence-refs-v1', 'revision': 2,
                    'references': [{'ref': 'chronicle:session:E1', 'revision': 2}]}
        prompts = []
        result = self.run_job(self.job(evidence=evidence), local=lambda _, prompt, __: prompts.append(prompt) or 'Three strokes.')
        self.assertEqual(result['sources'][0]['revision'], 2)
        self.assertNotIn('rang twice', prompts[0])
        self.assertIn('three times', prompts[0])

    def test_signed_consent_sync_works_with_ai_off_but_generation_stays_denied(self):
        g._save_evidence_snapshot(self.snapshot())
        master = self.authority.snapshot('camp', 'campaign')
        self.authority.patch_policy({
            'contract': g.RUNTIME_CONTRACT, 'campaign': 'camp', 'session': 'campaign',
            'expectedBootEpoch': master.boot_epoch, 'expectedGeneration': master.generation,
            'expectedSessionPolicyRevision': master.policy_revision, 'opId': str(uuid.uuid4()),
            'policy': {'enabled': False, 'mode': 'local', 'codex': False, 'exportable': False},
        })
        runtime = self.client.get('/api/game/runtime?campaign=camp&session=session', headers=self.headers).json()
        self.fence = {key: runtime[key] for key in ('contract', 'bootEpoch', 'generation', 'sessionPolicyRevision')}
        changed = self.snapshot(2)
        changed['participants'][0].update(external=False, externalEpoch=2)
        with patch.object(self.authority, 'verify_host'):
            response = self.client.post('/api/game/evidence/snapshot', json=changed, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['revision'], 2)
        evidence = {**self.job().evidence, 'revision': 2}
        with self.assertRaises(HTTPException) as caught:
            self.run_job(self.job(evidence=evidence), local=lambda *_: self.fail('disabled AI dispatched'))
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.receipts(), 0)

    def test_local_only_people_remain_usable_for_local_requests(self):
        body = self.snapshot()
        body['participants'][0].update(external=False, externalEpoch=0)
        body['sources'][0]['contributors'][0].update(exportableAtCapture=False, externalEpoch=0)
        g._save_evidence_snapshot(body)
        self.assertEqual(self.run_job()['trace'][0]['destination'], 'local')


if __name__ == '__main__':
    unittest.main()
