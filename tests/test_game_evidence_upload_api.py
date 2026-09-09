"""HTTP authentication, runtime fencing and atomic evidence staging integration."""
import copy
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from backend import game_agent as g
from backend import game_evidence_uploads as uploads
from backend.game_runtime import RuntimeDenied
import test_game_evidence_api as api_fixtures
from test_game_evidence_uploads import transfer


class EvidenceUploadAPITests(unittest.TestCase):
    setUp = api_fixtures.EvidenceAPITests.setUp
    snapshot = api_fixtures.EvidenceAPITests.snapshot

    def post(self, body):
        return self.client.post('/api/game/evidence/upload', json=body, headers=self.headers)

    def commands(self, revision=1):
        return transfer(self.snapshot(revision), 1)

    def test_token_alone_cannot_upload(self):
        begin, _, _ = self.commands()
        result = self.post(begin)
        self.assertIn(result.status_code, (401, 403))
        self.assertFalse((g.ROOT / 'game.sqlite').exists())

    def test_verifier_checks_exact_method_path_body_on_every_command(self):
        begin, pages, commit = self.commands()
        with patch.object(self.authority, 'verify_host') as verify:
            for command in [begin, *pages, commit]:
                response = self.post(command)
                self.assertEqual(response.status_code, 200, response.text)
                args = verify.call_args.args
                self.assertEqual(args[:3], ('POST', '/api/game/evidence/upload', command))
            self.assertEqual(verify.call_count, 3)
        self.assertEqual(response.json()['receipt']['sourceCount'], 1)

    def test_bad_signature_never_migrates_or_writes(self):
        with patch.object(self.authority, 'verify_host', side_effect=RuntimeDenied(403, 'signature_invalid')):
            self.assertEqual(self.post(self.commands()[0]).status_code, 403)
        self.assertFalse((g.ROOT / 'game.sqlite').exists())

    def test_size_cap_precedes_signature_check(self):
        with patch.object(self.authority, 'verify_host') as verify:
            response = self.client.post('/api/game/evidence/upload', content=b' ' * (uploads.MAX_HTTP_BYTES + 1), headers=self.headers)
            self.assertEqual(response.status_code, 413)
            verify.assert_not_called()

    def test_malformed_json_is_rejected(self):
        with patch.object(self.authority, 'verify_host') as verify:
            for raw in (b'[1]', b'null', b'{', b'\xff'):
                response = self.client.post('/api/game/evidence/upload', content=raw, headers=self.headers)
                self.assertEqual(response.status_code, 400)
            verify.assert_not_called()

    def test_stale_runtime_cannot_begin_page_or_commit(self):
        begin, pages, commit = self.commands()
        with patch.object(self.authority, 'verify_host'):
            self.assertEqual(self.post(begin).status_code, 200)
            self.assertEqual(self.post(pages[0]).status_code, 200)
            for command in [begin, pages[0], commit]:
                stale = copy.deepcopy(command)
                stale['runtime']['sessionPolicyRevision'] += 1
                self.assertEqual(self.post(stale).status_code, 409)
        with g.database() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM game_evidence_snapshots').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM game_evidence_upload_pages').fetchone()[0], 1)

    def test_begin_cancels_exports_and_blocks_old_evidence_before_commit(self):
        g._save_evidence_snapshot(self.snapshot())
        begin, pages, commit = self.commands(2)
        with patch.object(g.game_dispatch, 'schema_ready', return_value=True), patch.object(g.game_dispatch, 'cancel_queued') as cancel:
            self.assertEqual(g._upload_evidence(begin)['status'], 'pending')
            self.assertEqual(cancel.call_count, 1)
            self.assertEqual(cancel.call_args.kwargs['reason'], 'evidence_changed')
            g._upload_evidence(pages[0])
            self.assertEqual(cancel.call_count, 1)
            g._upload_evidence(commit)
            self.assertEqual(cancel.call_count, 2)

    def test_capacity_deferred_begin_still_cancels_exports(self):
        begin, _, _ = self.commands()
        with patch.object(uploads, 'MAX_STAGED_BYTES', 1), patch.object(g.game_dispatch, 'schema_ready', return_value=True), patch.object(g.game_dispatch, 'cancel_queued') as cancel:
            result = g._upload_evidence(begin)
            self.assertEqual(result['status'], 'deferred')
            cancel.assert_called_once()
        with g.database() as db:
            self.assertEqual(db.execute('SELECT state FROM game_evidence_uploads').fetchone()[0], 'expired')

    def test_cancel_failure_rolls_back_barrier_transaction(self):
        g._save_evidence_snapshot(self.snapshot())
        begin, _, _ = self.commands(2)
        with patch.object(g.game_dispatch, 'schema_ready', return_value=True), patch.object(g.game_dispatch, 'cancel_queued', side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):
                g._upload_evidence(begin)
        with g.database() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM game_evidence_uploads').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT revision FROM game_evidence_snapshots').fetchone()[0], 1)

    def test_migration_precedes_runtime_transaction(self):
        begin, _, _ = self.commands()
        with patch.object(g, '_evidence_transaction', side_effect=HTTPException(409, 'stopped')):
            with self.assertRaises(HTTPException):
                g._upload_evidence(begin)
        with g.database() as db:
            self.assertTrue(uploads.schema_ready(db))
            self.assertEqual(db.execute('SELECT count(*) FROM game_evidence_uploads').fetchone()[0], 0)

    def test_receipt_has_no_transcript_or_consent_content(self):
        begin, pages, commit = self.commands()
        for command in [begin, *pages, commit]:
            result = g._upload_evidence(command)
            public = json.dumps(result)
            self.assertNotIn('harbor', public)
            self.assertNotIn('player', public)
            self.assertNotIn('externalEpoch', public)
        self.assertEqual(result['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
