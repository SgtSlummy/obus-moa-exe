"""Independent wire-format and atomicity fixtures for bounded evidence uploads."""
import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from backend import game_evidence as evidence
from backend import game_evidence_uploads as uploads


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def source(number=1, revision=1, **changes):
    return dict(ref=f"E{number:05d}", revision=revision, audience="party", owner="",
                text=f"Source fact {number}.", provenance=f"chronicle:entry:{number}", deleted=False,
                contributors=[dict(user="player", captureEpoch=1, externalEpoch=1, exportableAtCapture=True)],
                derivesFrom=[], **changes)


def document(revision=1, count=4, **changes):
    value = dict(contract="raph-obus-game-evidence-v1", campaign="campaign", session="session", revision=revision,
                 runtime=dict(contract="raph-obus-game-runtime-v1", bootEpoch="boot", generation="generation", sessionPolicyRevision=1),
                 participants=[dict(user="player", capture=True, external=True, captureEpoch=1, externalEpoch=1)],
                 sources=[source(n) for n in range(1, count + 1)])
    value.update(changes)
    return value


def transfer(value, page_size=3):
    body = copy.deepcopy({k: v for k, v in value.items() if k != "runtime"})
    body["participants"].sort(key=lambda item: item["user"])
    body["sources"].sort(key=lambda item: item["ref"])
    for item in body["sources"]:
        item["contributors"].sort(key=lambda entry: entry["user"])
        item["derivesFrom"].sort(key=lambda entry: entry["ref"])
    groups = [body["sources"][n:n + page_size] for n in range(0, len(body["sources"]), page_size)] or [[]]
    manifest = dict(contract=uploads.CONTRACT, operation="begin", campaign=body["campaign"], session=body["session"],
                    revision=body["revision"], documentHash=hashlib.sha256(canonical(body)).hexdigest(),
                    documentBytes=len(canonical(body)), sourceCount=len(body["sources"]), participants=body["participants"],
                    pages=[dict(sha256=hashlib.sha256(canonical(group)).hexdigest(), bytes=len(canonical(group)), count=len(group)) for group in groups])
    identity = hashlib.sha256(canonical(manifest)).hexdigest()
    shared = dict(contract=uploads.CONTRACT, campaign=body["campaign"], session=body["session"], runtime=value["runtime"], uploadId=identity)
    begin = dict(manifest, runtime=value["runtime"], uploadId=identity)
    pages = [dict(shared, operation="page", index=n, sources=group) for n, group in enumerate(groups)]
    return begin, pages, dict(shared, operation="commit")


def reidentify(begin):
    begin["uploadId"] = hashlib.sha256(canonical({k: v for k, v in begin.items() if k not in {"runtime", "uploadId"}})).hexdigest()


class EvidenceUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="evidence-upload-")
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.clean_temp)
        self.path = self.root / "game.sqlite"
        uploads.prepare_store(self.path)
        self.db = sqlite3.connect(self.path)
        self.addCleanup(lambda: self.db.close())
        evidence.initialize_schema(self.db)
        self.db.commit()
        self.now = 10_000_000

    def clean_temp(self):
        assert self.root.parent == Path(tempfile.gettempdir()).resolve()
        assert self.root.name.startswith("evidence-upload-")
        self.temp.cleanup()

    def send(self, body):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return uploads.apply_command(self.db, copy.deepcopy(body), self.now)

    def save(self, value):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return evidence.save_snapshot(self.db, evidence.EvidenceSnapshot.model_validate(value))

    def resolve(self, revision=1, external=False, **changes):
        args = dict(campaign="campaign", session="session", revision=revision, owner="player", role="player",
                    references=[dict(ref="E00001", revision=1)], external=external)
        args.update(changes)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return evidence.resolve_evidence(self.db, **args)

    def upload(self, value, page_size=3):
        begin, pages, commit = transfer(value, page_size)
        result = self.send(begin)
        if result["status"] != "complete":
            for page in pages:
                self.send(page)
            result = self.send(commit)
        return result

    def denied(self, code, work):
        with self.assertRaises(evidence.EvidenceDenied) as caught:
            work()
        self.assertEqual(caught.exception.code, code)

    def test_legacy_limit_is_preserved(self):
        with self.assertRaises(ValidationError):
            evidence.EvidenceSnapshot.model_validate(document(count=2049))
        evidence.EvidenceDocument.model_validate(document(count=2049))

    def test_large_document_atomic_out_of_order_and_restart(self):
        self.save(document(count=1))
        begin, pages, commit = transfer(document(revision=2, count=2050), 128)
        self.assertEqual(self.send(begin)["status"], "pending")
        self.denied("evidence_upload_pending", lambda: self.resolve())
        self.send(pages[-1])
        self.denied("evidence_upload_incomplete", lambda: self.send(commit))
        self.assertEqual(self.db.execute("SELECT count(*) FROM game_evidence_sources").fetchone()[0], 1)
        self.db.close()
        self.db = sqlite3.connect(self.path)
        self.assertEqual(self.send(begin)["received"], [len(pages) - 1])
        for page in pages[:-1]:
            self.send(page)
        result = self.send(commit)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["receipt"]["sourceCount"], 2050)
        self.assertEqual(self.send(commit)["receipt"]["status"], "unchanged")
        self.assertEqual(self.db.execute("SELECT count(*) FROM game_evidence_upload_pages").fetchone()[0], 0)
        manifest = self.db.execute("SELECT manifest FROM game_evidence_uploads").fetchone()[0]
        self.assertNotIn("Source fact", manifest)
        self.assertNotIn("player", manifest)
        self.resolve(revision=2, external=True)

    def test_page_retries_and_changed_replay_before_and_after_commit(self):
        begin, pages, commit = transfer(document(count=1))
        self.send(begin)
        self.assertEqual(self.send(pages[0]), self.send(pages[0]))
        changed = copy.deepcopy(pages[0])
        changed["sources"][0]["text"] = "tampered"
        self.denied("evidence_upload_page_conflict", lambda: self.send(changed))
        self.send(commit)
        self.assertEqual(self.send(pages[0])["status"], "complete")
        self.denied("evidence_upload_page_conflict", lambda: self.send(changed))

    def test_duplicate_source_across_pages_never_promotes(self):
        value = document(count=2)
        value["sources"][1] = copy.deepcopy(value["sources"][0])
        begin, pages, commit = transfer(value, 1)
        self.send(begin)
        for page in pages:
            self.send(page)
        self.denied("evidence_upload_document_invalid", lambda: self.send(commit))
        self.denied("evidence_upload_pending", lambda: self.resolve())

    def test_wrong_document_digest_or_size_keeps_old_snapshot_blocked(self):
        self.save(document(count=1))
        for field, invalid in (("documentHash", "0" * 64), ("documentBytes", 9999)):
            begin, pages, commit = transfer(document(revision=2 if field == "documentHash" else 3, count=1))
            begin[field] = invalid
            reidentify(begin)
            for command in pages + [commit]:
                command["uploadId"] = begin["uploadId"]
            self.send(begin)
            for page in pages:
                self.send(page)
            self.denied("evidence_upload_document_invalid", lambda: self.send(commit))
            self.denied("evidence_upload_pending", lambda: self.resolve())

    def test_consent_high_water_survives_paging(self):
        self.save(document(count=1))
        value = document(revision=2, count=1)
        value["participants"][0]["external"] = False
        self.denied("evidence_consent_conflict", lambda: self.upload(value))
        self.denied("evidence_upload_pending", lambda: self.resolve())
        value["revision"] = 3
        value["participants"][0]["externalEpoch"] = 2
        self.upload(value)
        self.resolve(revision=3)
        self.denied("evidence_external_consent_required", lambda: self.resolve(revision=3, external=True))

    def test_source_high_water_survives_paging(self):
        self.save(document(count=1))
        value = document(revision=2, count=1)
        value["sources"][0]["text"] = "correction without a new revision"
        self.denied("evidence_source_conflict", lambda: self.upload(value))
        self.denied("evidence_upload_pending", lambda: self.resolve())

    def test_expiry_scrubs_text_but_preserves_privacy_barrier(self):
        self.save(document(count=1))
        begin, pages, commit = transfer(document(revision=2, count=2), 1)
        self.send(begin)
        self.send(pages[0])
        self.now += uploads.UPLOAD_TTL_MS + 1
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            uploads.expire_uploads(self.db, self.now)
        self.assertEqual(self.db.execute("SELECT count(*) FROM game_evidence_upload_pages").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT state,manifest,expected_bytes FROM game_evidence_uploads").fetchone(), ("expired", None, 0))
        self.denied("evidence_upload_pending", lambda: self.resolve())
        self.denied("evidence_upload_expired", lambda: self.send(commit))
        self.assertEqual(self.send(begin)["received"], [])
        for page in pages:
            self.send(page)
        self.send(commit)

    def test_runtime_rebind_discards_old_pages(self):
        begin, pages, commit = transfer(document(count=2), 1)
        self.send(begin)
        self.send(pages[0])
        current = copy.deepcopy(begin)
        current["runtime"]["generation"] = "new-generation"
        self.assertEqual(self.send(current)["received"], [])
        self.denied("evidence_upload_runtime_changed", lambda: self.send(pages[0]))
        for page in pages + [commit]:
            page["runtime"] = current["runtime"]
            self.send(page)

    def test_newer_small_snapshot_can_supersede_pending_upload(self):
        self.save(document(count=1))
        begin, _, commit = transfer(document(revision=2, count=2))
        self.send(begin)
        self.denied("evidence_upload_pending", lambda: self.save(document(revision=2, count=1)))
        self.save(document(revision=3, count=1))
        self.assertEqual(self.db.execute("SELECT count(*) FROM game_evidence_uploads").fetchone()[0], 0)
        self.denied("evidence_upload_unknown", lambda: self.send(commit))
        self.resolve(revision=3)

    def test_capacity_failure_still_fences_old_private_evidence(self):
        self.save(document(count=1))
        begin, pages, _ = transfer(document(revision=2, count=1))
        with patch.object(uploads, "MAX_STAGED_BYTES", 1):
            self.assertEqual(self.send(begin)["status"], "deferred")
        self.denied("evidence_upload_pending", lambda: self.resolve())
        self.denied("evidence_upload_expired", lambda: self.send(pages[0]))
        self.assertEqual(self.send(begin)["status"], "pending")
        other, _, _ = transfer(document(campaign="other", count=1))
        with patch.object(uploads, "MAX_ACTIVE_UPLOADS", 1):
            self.assertEqual(self.send(other)["status"], "deferred")
        self.assertEqual(self.db.execute("SELECT count(*) FROM game_evidence_uploads WHERE state='pending'").fetchone()[0], 1)

    def test_cross_scope_and_conflicting_revision_are_denied(self):
        begin, pages, commit = transfer(document(revision=2, count=1))
        self.send(begin)
        for command in [pages[0], commit]:
            changed = copy.deepcopy(command)
            changed["session"] = "other"
            self.denied("evidence_upload_unknown", lambda: self.send(changed))
        old, _, _ = transfer(document(revision=1, count=1))
        self.denied("evidence_upload_conflict", lambda: self.send(old))
        conflict, _, _ = transfer(document(revision=2, count=2))
        self.denied("evidence_upload_conflict", lambda: self.send(conflict))

    def test_repaging_same_document_restarts_staging(self):
        first, pages, _ = transfer(document(count=4), 1)
        second, new_pages, commit = transfer(document(count=4), 3)
        self.assertEqual(first["documentHash"], second["documentHash"])
        self.assertNotEqual(first["uploadId"], second["uploadId"])
        self.send(first)
        self.send(pages[0])
        self.assertEqual(self.send(second)["received"], [])
        for page in new_pages:
            self.send(page)
        self.send(commit)

    def test_existing_snapshot_receipt_does_not_stage_duplicate_text(self):
        self.save(document(count=1))
        begin, pages, commit = transfer(document(count=1))
        self.assertEqual(self.send(begin)["status"], "complete")
        self.assertEqual(self.send(commit)["receipt"]["status"], "unchanged")
        self.assertEqual(self.send(pages[0])["status"], "complete")
        self.assertEqual(self.db.execute("SELECT count(*) FROM game_evidence_upload_pages").fetchone()[0], 0)

    def test_malformed_commands_rejected_before_writes(self):
        begin, pages, _ = transfer(document(count=1))
        cases = [None, [], {}, dict(begin, uploadId="0" * 64), dict(begin, extra=True), dict(pages[0], index=True),
                 dict(pages[0], sources=[source(n) for n in range(257)])]
        for case in cases:
            with self.subTest(case=type(case).__name__):
                self.denied("evidence_upload_invalid", lambda: self.send(case))
        self.assertEqual(self.db.execute("SELECT count(*) FROM game_evidence_uploads").fetchone()[0], 0)

    def test_utf8_byte_sizes_and_empty_documents_are_exact(self):
        value = document(count=1)
        value["sources"][0]["text"] = "Harbor " + "".join(chr(code) for code in (0, 1, 9, 10, 13, 27, 127, 0x1F30A, 0x6D77))
        begin, _, _ = transfer(value)
        self.assertGreater(begin["documentBytes"], len(canonical({k: v for k, v in value.items() if k != "runtime"}).decode("utf-8")))
        self.assertEqual(self.upload(value)["status"], "complete")
        self.assertEqual(self.upload(document(revision=2, count=0, participants=[]))["receipt"]["sourceCount"], 0)

    def test_corrupt_staged_body_never_promotes(self):
        begin, pages, commit = transfer(document(count=1))
        self.send(begin)
        self.send(pages[0])
        with self.db:
            self.db.execute("UPDATE game_evidence_upload_pages SET body='[]'")
        self.denied("evidence_upload_document_invalid", lambda: self.send(commit))

    def test_transaction_and_clock_are_required(self):
        begin, _, _ = transfer(document(count=1))
        with self.assertRaises(Exception):
            uploads.apply_command(self.db, begin, self.now)
        for invalid in (True, -1, 1.5):
            self.now = invalid
            self.denied("evidence_upload_time_invalid", lambda: self.send(begin))

    def test_existing_wal_store_is_backed_up_once(self):
        path = self.root / "space and # percent%.sqlite"
        original = sqlite3.connect(path)
        self.addCleanup(original.close)
        original.execute("PRAGMA journal_mode=WAL")
        original.execute("CREATE TABLE sentinel(value TEXT)")
        original.execute("INSERT INTO sentinel VALUES ('committed')")
        original.commit()
        uploads.prepare_store(path)
        backups = list((self.root / "backups").glob("game-before-evidence-upload-v1-*.sqlite"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as backup:
            self.assertEqual(backup.execute("SELECT value FROM sentinel").fetchone()[0], "committed")
            self.assertEqual(backup.execute("SELECT count(*) FROM sqlite_master WHERE name='game_evidence_uploads'").fetchone()[0], 0)
        uploads.prepare_store(path)
        self.assertEqual(len(list((self.root / "backups").glob("game-before-evidence-upload-v1-*.sqlite"))), 1)
        self.assertTrue(uploads.schema_ready(original))

    def test_row_factory_and_partial_schema_validation(self):
        self.db.row_factory = sqlite3.Row
        self.assertTrue(uploads.schema_ready(self.db))
        uploads.prepare_store(self.path)
        self.upload(document(count=1))
        path = self.root / "partial.sqlite"
        with closing(sqlite3.connect(path)) as broken:
            broken.execute("CREATE TABLE game_evidence_upload_schema(version INTEGER PRIMARY KEY CHECK(version=1))")
            broken.commit()
        self.denied("evidence_upload_schema_invalid", lambda: uploads.prepare_store(path))


if __name__ == "__main__":
    unittest.main()
