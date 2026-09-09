"""Bounded, atomic campaign-evidence uploads. No network or provider access.

The API authenticates every command and owns the runtime-fenced transaction.
Staged or expired uploads block retrieval until a complete document is promoted.
An expired upload loses its duplicate source text, never its privacy barrier.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Annotated, Literal
import uuid

from pydantic import Field, ValidationError, model_validator
from backend.game_evidence import (
    CONTRACT as EVIDENCE_CONTRACT, MAX_DOCUMENT_BYTES, MAX_DOCUMENT_SOURCES,
    MAX_PARTICIPANTS, MAX_SAFE_INTEGER, EvidenceDenied, EvidenceDocument,
    EvidenceParticipant, EvidenceRuntimeFence, EvidenceSource, Identifier, SafeInt,
    Strict, _digest, _json, _replace_snapshot, _source_body, _transaction_required,
    _unique, document_body,
)

CONTRACT = "raph-obus-game-evidence-upload-v1"
MAX_HTTP_BYTES = 256 * 1024
MAX_PAGE_BYTES = 240 * 1024
MAX_PAGE_SOURCES = 256
MAX_PAGES = 512
MAX_ACTIVE_UPLOADS = 8
MAX_STAGED_BYTES = 128 * 1024 * 1024
UPLOAD_TTL_MS = 60 * 60 * 1000
Hash = Annotated[str, Field(strict=True, min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")]
_MIGRATION_LOCK = threading.RLock()
_TABLES = {"game_evidence_upload_schema", "game_evidence_uploads", "game_evidence_upload_pages"}
_COLUMNS = ("upload_id", "revision", "document_hash", "manifest_hash", "state", "fence", "manifest",
            "page_count", "source_count", "participant_count", "document_bytes", "expected_bytes", "created_ms", "updated_ms")


class PageDescriptor(Strict):
    sha256: Hash
    bytes: Annotated[int, Field(strict=True, ge=2, le=MAX_PAGE_BYTES)]
    count: Annotated[int, Field(strict=True, ge=0, le=MAX_PAGE_SOURCES)]


class Command(Strict):
    contract: Literal["raph-obus-game-evidence-upload-v1"]
    campaign: Identifier
    session: Identifier
    runtime: EvidenceRuntimeFence
    uploadId: Hash


class Begin(Command):
    operation: Literal["begin"]
    revision: SafeInt
    documentHash: Hash
    documentBytes: Annotated[int, Field(strict=True, ge=2, le=MAX_DOCUMENT_BYTES)]
    sourceCount: Annotated[int, Field(strict=True, ge=0, le=MAX_DOCUMENT_SOURCES)]
    participants: Annotated[list[EvidenceParticipant], Field(max_length=MAX_PARTICIPANTS)]
    pages: Annotated[list[PageDescriptor], Field(min_length=1, max_length=MAX_PAGES)]

    @model_validator(mode="after")
    def bounded_manifest(self):
        _unique(self.participants, "user", "duplicate participant")
        if sum(page.count for page in self.pages) != self.sourceCount:
            raise ValueError("page counts disagree")
        if self.sourceCount == 0:
            if len(self.pages) != 1 or self.pages[0].count != 0 or self.pages[0].bytes != 2 or self.pages[0].sha256 != hashlib.sha256(b"[]").hexdigest():
                raise ValueError("invalid empty document page")
        elif any(page.count == 0 for page in self.pages):
            raise ValueError("empty intermediate page")
        size = sum(page.bytes for page in self.pages)
        if size > MAX_DOCUMENT_BYTES + MAX_PAGES or size > self.documentBytes + len(self.pages):
            raise ValueError("page bytes disagree")
        if _digest(self.model_dump(exclude={"runtime", "uploadId"})) != self.uploadId:
            raise ValueError("invalid manifest identity")
        return self


class Page(Command):
    operation: Literal["page"]
    index: Annotated[int, Field(strict=True, ge=0, lt=MAX_PAGES)]
    sources: Annotated[list[EvidenceSource], Field(max_length=MAX_PAGE_SOURCES)]

    @model_validator(mode="after")
    def unique_sources(self):
        _unique(self.sources, "ref", "duplicate page source")
        return self


class Commit(Command):
    operation: Literal["commit"]


def parse_command(body: dict) -> Begin | Page | Commit:
    try:
        if not isinstance(body, dict):
            raise ValueError("invalid command")
        model = {"begin": Begin, "page": Page, "commit": Commit}.get(body.get("operation"))
        if model is None:
            raise ValueError("unknown operation")
        parsed = model.model_validate(body)
        if len(_json(parsed.model_dump()).encode("utf-8")) > MAX_HTTP_BYTES:
            raise ValueError("oversized command")
        return parsed
    except (ValidationError, ValueError, TypeError, UnicodeError) as exc:
        raise EvidenceDenied(400, "evidence_upload_invalid") from exc


def schema_ready(db: sqlite3.Connection) -> bool:
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    found = names.intersection(_TABLES)
    if not found:
        return False
    if found != _TABLES:
        raise EvidenceDenied(500, "evidence_upload_schema_invalid")
    versions = [row[0] for row in db.execute("SELECT version FROM game_evidence_upload_schema")]
    if versions != [1]:
        raise EvidenceDenied(500, "evidence_upload_schema_invalid")
    for table, expected in (
        ("game_evidence_uploads", {"campaign", "session", *_COLUMNS}),
        ("game_evidence_upload_pages", {"campaign", "session", "upload_id", "page_index", "sha256", "byte_count", "source_count", "body"}),
    ):
        # Receipt connections deliberately reject every PRAGMA. Read-only
        # projection metadata verifies the same columns without weakening that guard.
        if {column[0] for column in db.execute(f"SELECT * FROM {table} WHERE 0").description} != expected:
            raise EvidenceDenied(500, "evidence_upload_schema_invalid")
    return True


def _initialize_schema(db: sqlite3.Connection) -> None:
    statements = (
        "CREATE TABLE game_evidence_upload_schema(version INTEGER PRIMARY KEY CHECK(version=1))",
        "INSERT INTO game_evidence_upload_schema VALUES(1)",
        "CREATE TABLE game_evidence_uploads(campaign TEXT NOT NULL,session TEXT NOT NULL,upload_id TEXT NOT NULL,revision INTEGER NOT NULL,document_hash TEXT NOT NULL,manifest_hash TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('pending','expired','complete')),fence TEXT NOT NULL,manifest TEXT,page_count INTEGER NOT NULL,source_count INTEGER NOT NULL,participant_count INTEGER NOT NULL,document_bytes INTEGER NOT NULL,expected_bytes INTEGER NOT NULL,created_ms INTEGER NOT NULL,updated_ms INTEGER NOT NULL,PRIMARY KEY(campaign,session))",
        "CREATE TABLE game_evidence_upload_pages(campaign TEXT NOT NULL,session TEXT NOT NULL,upload_id TEXT NOT NULL,page_index INTEGER NOT NULL,sha256 TEXT NOT NULL,byte_count INTEGER NOT NULL,source_count INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(campaign,session,page_index))",
    )
    for statement in statements:
        db.execute(statement)


def prepare_store(game_path: Path) -> None:
    """Back up an existing nonempty store before adding staging tables.

    Run before runtime/receipt locks. A game-only writer reservation excludes
    concurrent migration and data writers while a separate read-only connection
    makes a consistent SQLite online backup (including committed WAL data).
    """
    game_path = Path(game_path).resolve()
    with _MIGRATION_LOCK:
        if game_path.is_file():
            probe = sqlite3.connect(game_path.as_uri() + "?mode=ro", uri=True, timeout=10)
            try:
                if schema_ready(probe):
                    return
            finally:
                probe.close()
        game_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(game_path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            if schema_ready(db):
                db.commit()
                return
            existing = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1").fetchone()
            if existing:
                backup_dir = game_path.parent / "backups"
                backup_dir.mkdir(exist_ok=True)
                backup = backup_dir / ("game-before-evidence-upload-v1-" + str(uuid.uuid4()) + ".sqlite")
                source = sqlite3.connect(game_path.as_uri() + "?mode=ro", uri=True, timeout=10)
                target = sqlite3.connect(backup, timeout=10)
                try:
                    source.backup(target)
                finally:
                    target.close()
                    source.close()
            _initialize_schema(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def _record(db: sqlite3.Connection, campaign: str, session: str) -> dict | None:
    row = db.execute("SELECT " + ",".join(_COLUMNS) + " FROM game_evidence_uploads WHERE campaign=? AND session=?", (campaign, session)).fetchone()
    return dict(zip(_COLUMNS, row)) if row else None


def _fence(command: Command) -> str:
    return _json(command.runtime.model_dump())


def _time(now_ms: int) -> int:
    if type(now_ms) is not int or not 0 <= now_ms <= MAX_SAFE_INTEGER:
        raise EvidenceDenied(400, "evidence_upload_time_invalid")
    return now_ms


def expire_uploads(db: sqlite3.Connection, now_ms: int) -> int:
    _transaction_required(db)
    _time(now_ms)
    expired = db.execute("SELECT campaign,session FROM game_evidence_uploads WHERE state='pending' AND updated_ms<=?", (now_ms - UPLOAD_TTL_MS,)).fetchall()
    for campaign, session in expired:
        db.execute("DELETE FROM game_evidence_upload_pages WHERE campaign=? AND session=?", (campaign, session))
        db.execute("UPDATE game_evidence_uploads SET state='expired',manifest=NULL,expected_bytes=0 WHERE campaign=? AND session=?", (campaign, session))
    return len(expired)


def _completed_receipt(db: sqlite3.Connection, command: Command, stored: dict) -> dict:
    identity = (command.campaign, command.session)
    head = db.execute("SELECT revision,body_hash FROM game_evidence_snapshots WHERE campaign=? AND session=?", identity).fetchone()
    if not head or (head[0], head[1]) != (stored["revision"], stored["document_hash"]):
        raise EvidenceDenied(409, "evidence_upload_stale")
    counts = [db.execute(f"SELECT COUNT(*) FROM {table} WHERE campaign=? AND session=?", identity).fetchone()[0]
              for table in ("game_evidence_sources", "game_evidence_participants")]
    if counts != [stored["source_count"], stored["participant_count"]]:
        raise EvidenceDenied(500, "evidence_upload_store_invalid")
    return {"contract": EVIDENCE_CONTRACT, "campaign": command.campaign, "session": command.session,
            "revision": stored["revision"], "status": "unchanged", "sourceCount": counts[0], "participantCount": counts[1]}


def _status(db: sqlite3.Connection, command: Command, stored: dict, receipt: dict | None = None) -> dict:
    complete = stored["state"] == "complete"
    received = [] if complete else [row[0] for row in db.execute("SELECT page_index FROM game_evidence_upload_pages WHERE campaign=? AND session=? AND upload_id=? ORDER BY page_index", (command.campaign, command.session, command.uploadId))]
    result = {"contract": CONTRACT, "campaign": command.campaign, "session": command.session, "uploadId": command.uploadId,
              "revision": stored["revision"], "status": "complete" if complete else "deferred" if stored["state"] == "expired" else "pending", "pageCount": stored["page_count"],
              "sourceCount": stored["source_count"], "participantCount": stored["participant_count"], "received": received}
    if complete:
        result["receipt"] = receipt if receipt is not None else _completed_receipt(db, command, stored)
    return result


def _require(db: sqlite3.Connection, command: Command, now_ms: int) -> dict:
    stored = _record(db, command.campaign, command.session)
    if not stored or stored["upload_id"] != command.uploadId:
        raise EvidenceDenied(409, "evidence_upload_unknown")
    if stored["fence"] != _fence(command):
        raise EvidenceDenied(409, "evidence_upload_runtime_changed")
    if stored["state"] != "complete" and (stored["state"] != "pending" or stored["updated_ms"] <= now_ms - UPLOAD_TTL_MS):
        raise EvidenceDenied(409, "evidence_upload_expired")
    return stored


def begin_upload(db: sqlite3.Connection, command: Begin, now_ms: int) -> dict:
    _transaction_required(db)
    _time(now_ms)
    expire_uploads(db, now_ms)
    identity = (command.campaign, command.session)
    stored = _record(db, *identity)
    if stored and (stored["revision"] > command.revision or stored["revision"] == command.revision and stored["document_hash"] != command.documentHash):
        raise EvidenceDenied(409, "evidence_upload_conflict")
    head = db.execute("SELECT revision,body_hash FROM game_evidence_snapshots WHERE campaign=? AND session=?", identity).fetchone()
    if head and (head[0] > command.revision or head[0] == command.revision and head[1] != command.documentHash):
        raise EvidenceDenied(409, "evidence_snapshot_conflict")
    manifest_hash = _digest(command.model_dump(exclude={"runtime"}))
    complete = bool(head and (head[0], head[1]) == (command.revision, command.documentHash))
    if stored and stored["upload_id"] == command.uploadId and stored["manifest_hash"] == manifest_hash and stored["fence"] == _fence(command) and stored["state"] in {"pending", "complete"}:
        return _status(db, command, stored)
    expected_bytes = sum(page.bytes for page in command.pages)
    deferred = False
    if not complete:
        active, reserved = db.execute("SELECT COUNT(*),COALESCE(SUM(expected_bytes),0) FROM game_evidence_uploads WHERE state='pending' AND NOT(campaign=? AND session=?)", identity).fetchone()
        deferred = active >= MAX_ACTIVE_UPLOADS or reserved + expected_bytes > MAX_STAGED_BYTES
    # A valid newer privacy intent must still block old evidence when staging
    # capacity is full. Persist metadata only and let a later begin reserve space.
    new = {"upload_id": command.uploadId, "revision": command.revision, "document_hash": command.documentHash,
           "manifest_hash": manifest_hash, "state": "complete" if complete else "expired" if deferred else "pending", "fence": _fence(command),
           "manifest": _json([page.model_dump() for page in command.pages]) if complete else None if deferred else _json(command.model_dump()), "page_count": len(command.pages),
           "source_count": command.sourceCount, "participant_count": len(command.participants), "document_bytes": command.documentBytes,
           "expected_bytes": 0 if complete or deferred else expected_bytes, "created_ms": now_ms, "updated_ms": now_ms}
    # Rebinding to a new live runtime or equivalent new page layout starts with
    # no old pages; the same document identity is still required at this revision.
    db.execute("DELETE FROM game_evidence_upload_pages WHERE campaign=? AND session=?", identity)
    db.execute("DELETE FROM game_evidence_uploads WHERE campaign=? AND session=?", identity)
    db.execute("INSERT INTO game_evidence_uploads(campaign,session," + ",".join(_COLUMNS) + ") VALUES(" + ",".join("?" for _ in range(len(_COLUMNS) + 2)) + ")", (*identity, *(new[key] for key in _COLUMNS)))
    return _status(db, command, new)


def save_page(db: sqlite3.Connection, command: Page, now_ms: int) -> dict:
    _transaction_required(db)
    _time(now_ms)
    stored = _require(db, command, now_ms)
    complete = stored["state"] == "complete"
    try:
        if complete:
            descriptors = [PageDescriptor.model_validate(value) for value in json.loads(stored["manifest"])]
            if len(descriptors) != stored["page_count"]:
                raise ValueError("invalid page metadata")
        else:
            descriptors = Begin.model_validate_json(stored["manifest"]).pages
    except (TypeError, ValueError, ValidationError) as exc:
        raise EvidenceDenied(500, "evidence_upload_store_invalid") from exc
    if command.index >= len(descriptors):
        raise EvidenceDenied(400, "evidence_upload_page_invalid")
    body = _json([_source_body(source) for source in command.sources])
    try:
        encoded = body.encode("utf-8")
    except UnicodeError as exc:
        raise EvidenceDenied(400, "evidence_upload_page_invalid") from exc
    descriptor = descriptors[command.index]
    digest = hashlib.sha256(encoded).hexdigest()
    if (len(command.sources), len(encoded), digest) != (descriptor.count, descriptor.bytes, descriptor.sha256):
        raise EvidenceDenied(409, "evidence_upload_page_conflict")
    if complete:
        return _status(db, command, stored)
    previous = db.execute("SELECT upload_id,sha256,body FROM game_evidence_upload_pages WHERE campaign=? AND session=? AND page_index=?", (command.campaign, command.session, command.index)).fetchone()
    if previous and tuple(previous) != (command.uploadId, digest, body):
        raise EvidenceDenied(409, "evidence_upload_page_conflict")
    if not previous:
        db.execute("INSERT INTO game_evidence_upload_pages VALUES(?,?,?,?,?,?,?,?)", (command.campaign, command.session, command.uploadId, command.index, digest, len(encoded), len(command.sources), body))
    db.execute("UPDATE game_evidence_uploads SET updated_ms=? WHERE campaign=? AND session=?", (now_ms, command.campaign, command.session))
    return _status(db, command, stored)


def commit_upload(db: sqlite3.Connection, command: Commit, now_ms: int) -> dict:
    _transaction_required(db)
    _time(now_ms)
    stored = _require(db, command, now_ms)
    if stored["state"] == "complete":
        return _status(db, command, stored)
    try:
        manifest = Begin.model_validate_json(stored["manifest"])
    except (TypeError, ValidationError) as exc:
        raise EvidenceDenied(500, "evidence_upload_store_invalid") from exc
    rows = db.execute("SELECT page_index,sha256,byte_count,source_count,body FROM game_evidence_upload_pages WHERE campaign=? AND session=? AND upload_id=? ORDER BY page_index", (command.campaign, command.session, command.uploadId)).fetchall()
    if len(rows) != len(manifest.pages):
        raise EvidenceDenied(409, "evidence_upload_incomplete")
    sources = []
    try:
        for index, row in enumerate(rows):
            descriptor = manifest.pages[index]
            encoded = row[4].encode("utf-8")
            if (row[0], row[1], row[2], row[3]) != (index, descriptor.sha256, descriptor.bytes, descriptor.count) or len(encoded) != descriptor.bytes or hashlib.sha256(encoded).hexdigest() != descriptor.sha256:
                raise ValueError("invalid stored page")
            page_sources = json.loads(row[4])
            if not isinstance(page_sources, list) or len(page_sources) != descriptor.count:
                raise ValueError("invalid stored page count")
            sources.extend(page_sources)
        document = EvidenceDocument.model_validate({"contract": EVIDENCE_CONTRACT, "campaign": command.campaign,
            "session": command.session, "revision": manifest.revision, "runtime": command.runtime.model_dump(),
            "participants": [item.model_dump() for item in manifest.participants], "sources": sources})
        encoded_document = _json(document_body(document)).encode("utf-8")
        if len(sources) != manifest.sourceCount or len(encoded_document) != manifest.documentBytes or hashlib.sha256(encoded_document).hexdigest() != manifest.documentHash:
            raise ValueError("invalid complete document")
    except (TypeError, ValueError, UnicodeError, ValidationError) as exc:
        raise EvidenceDenied(409, "evidence_upload_document_invalid") from exc
    receipt = _replace_snapshot(db, document)
    db.execute("DELETE FROM game_evidence_upload_pages WHERE campaign=? AND session=?", (command.campaign, command.session))
    page_metadata = _json([page.model_dump() for page in manifest.pages])
    db.execute("UPDATE game_evidence_uploads SET state='complete',manifest=?,expected_bytes=0,updated_ms=? WHERE campaign=? AND session=?", (page_metadata, now_ms, command.campaign, command.session))
    stored.update(state="complete", manifest=page_metadata, expected_bytes=0, updated_ms=now_ms)
    return _status(db, command, stored, receipt)


def apply_command(db: sqlite3.Connection, body: dict, now_ms: int) -> dict:
    """Caller must hold a current runtime/evidence transaction for this scope."""
    _transaction_required(db)
    command = parse_command(body)
    if not schema_ready(db):
        raise EvidenceDenied(500, "evidence_upload_schema_uninitialized")
    if isinstance(command, Begin):
        return begin_upload(db, command, now_ms)
    if isinstance(command, Page):
        return save_page(db, command, now_ms)
    return commit_upload(db, command, now_ms)
