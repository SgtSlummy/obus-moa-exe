"""Session-scoped, revisioned evidence; callers own authentication and transactions.

These tables never consult general memory. The caller must open a transaction
before saving or resolving and retain it through any dependent receipt commit.
Inference must occur outside the receipt transaction, followed by re-resolution.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Annotated, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

CONTRACT = "raph-obus-game-evidence-v1"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_SNAPSHOT_BYTES = 512 * 1024
MAX_SOURCES = 2048
MAX_PARTICIPANTS = 256
MAX_REFERENCES = 32
MAX_TEXT = 16_000

SafeInt = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]
Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=100)]
Reference = Annotated[str, Field(strict=True, min_length=1, max_length=160)]


class EvidenceDenied(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceRuntimeFence(Strict):
    contract: Literal["raph-obus-game-runtime-v1"]
    bootEpoch: Identifier
    generation: Identifier
    sessionPolicyRevision: SafeInt


class EvidenceParticipant(Strict):
    user: Identifier
    capture: bool
    external: bool
    captureEpoch: SafeInt
    externalEpoch: SafeInt


class EvidenceContributor(Strict):
    user: Identifier
    captureEpoch: SafeInt | None
    externalEpoch: SafeInt | None
    exportableAtCapture: bool

    @model_validator(mode="after")
    def known_export_epochs(self):
        if self.exportableAtCapture and (self.captureEpoch is None or self.externalEpoch is None):
            raise ValueError("exportable contributors require known epochs")
        return self


class EvidenceReference(Strict):
    ref: Reference
    revision: SafeInt


class EvidenceSource(Strict):
    ref: Reference
    revision: SafeInt
    audience: Literal["party", "host", "private"]
    owner: Annotated[str, Field(strict=True, max_length=100)]
    text: Annotated[str, Field(strict=True, max_length=MAX_TEXT)]
    provenance: Reference
    deleted: bool
    contributors: Annotated[list[EvidenceContributor], Field(max_length=MAX_PARTICIPANTS)]
    derivesFrom: Annotated[list[EvidenceReference], Field(max_length=MAX_REFERENCES)]

    @model_validator(mode="after")
    def unique_lineage(self):
        _unique(self.contributors, "user", "duplicate contributor")
        _unique(self.derivesFrom, "ref", "duplicate derivation")
        if self.audience == "private" and not self.owner:
            raise ValueError("private evidence requires an owner")
        return self


def _unique(records, field, message):
    values = [getattr(record, field) for record in records]
    if len(set(values)) != len(values):
        raise ValueError(message)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _source_body(source: EvidenceSource) -> dict:
    body = source.model_dump()
    body["contributors"].sort(key=lambda item: item["user"])
    body["derivesFrom"].sort(key=lambda item: item["ref"])
    return body


class EvidenceSnapshot(Strict):
    contract: Literal["raph-obus-game-evidence-v1"]
    campaign: Identifier
    session: Identifier
    revision: SafeInt
    runtime: EvidenceRuntimeFence
    participants: Annotated[list[EvidenceParticipant], Field(max_length=MAX_PARTICIPANTS)]
    sources: Annotated[list[EvidenceSource], Field(max_length=MAX_SOURCES)]

    @model_validator(mode="after")
    def unique_bounded_snapshot(self):
        _unique(self.participants, "user", "duplicate participant")
        _unique(self.sources, "ref", "duplicate source")
        try:
            size = len(_json(self.model_dump()).encode("utf-8"))
        except UnicodeError as exc:
            raise ValueError("snapshot must be UTF-8") from exc
        if size > MAX_SNAPSHOT_BYTES:
            raise ValueError("snapshot exceeds byte limit")
        return self


def initialize_schema(db: sqlite3.Connection) -> None:
    """Initialize separately from receipt work; never commit a caller transaction."""
    statements = (
        "CREATE TABLE IF NOT EXISTS game_evidence_snapshots(campaign TEXT NOT NULL, session TEXT NOT NULL, revision INTEGER NOT NULL, body_hash TEXT NOT NULL, PRIMARY KEY(campaign,session))",
        "CREATE TABLE IF NOT EXISTS game_evidence_participants(campaign TEXT NOT NULL, session TEXT NOT NULL, user TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(campaign,session,user))",
        "CREATE TABLE IF NOT EXISTS game_evidence_sources(campaign TEXT NOT NULL, session TEXT NOT NULL, ref TEXT NOT NULL, revision INTEGER NOT NULL, audience TEXT NOT NULL, owner TEXT NOT NULL, deleted INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(campaign,session,ref))",
        "CREATE TABLE IF NOT EXISTS game_evidence_source_heads(campaign TEXT NOT NULL, session TEXT NOT NULL, ref TEXT NOT NULL, revision INTEGER NOT NULL, body_hash TEXT NOT NULL, PRIMARY KEY(campaign,session,ref))",
    )
    for statement in statements:
        db.execute(statement)


def _transaction_required(db):
    if not db.in_transaction:
        raise EvidenceDenied(500, "evidence_transaction_required")


def _digest(body: dict) -> str:
    return hashlib.sha256(_json(body).encode("utf-8")).hexdigest()


def save_snapshot(db: sqlite3.Connection, snapshot: EvidenceSnapshot) -> dict:
    """Replace one complete snapshot; raise before writes on revision conflicts.

    Source high-water hashes survive removal without retaining removed text, so
    an old source revision cannot be reintroduced with different evidence.
    """
    _transaction_required(db)
    try:
        snapshot = EvidenceSnapshot.model_validate(snapshot.model_dump())
    except (AttributeError, ValidationError) as exc:
        raise EvidenceDenied(400, "evidence_snapshot_invalid") from exc
    body = snapshot.model_dump(exclude={"runtime"})
    body["participants"].sort(key=lambda item: item["user"])
    body["sources"] = sorted((_source_body(source) for source in snapshot.sources), key=lambda item: item["ref"])
    body_hash = _digest(body)
    identity = (snapshot.campaign, snapshot.session)
    old = db.execute("SELECT revision,body_hash FROM game_evidence_snapshots WHERE campaign=? AND session=?", identity).fetchone()
    status = "saved"
    if old:
        if old[0] > snapshot.revision:
            raise EvidenceDenied(409, "evidence_snapshot_stale")
        if old[0] == snapshot.revision:
            if old[1] != body_hash:
                raise EvidenceDenied(409, "evidence_snapshot_conflict")
            status = "unchanged"
    receipt = {"contract": CONTRACT, "campaign": snapshot.campaign, "session": snapshot.session,
               "revision": snapshot.revision, "status": status, "sourceCount": len(snapshot.sources),
               "participantCount": len(snapshot.participants)}
    if status == "unchanged":
        return receipt
    source_rows = []
    source_heads = []
    for source in body["sources"]:
        source_hash = _digest(source)
        head = db.execute("SELECT revision,body_hash FROM game_evidence_source_heads WHERE campaign=? AND session=? AND ref=?",
                          (*identity, source["ref"])).fetchone()
        if head and (source["revision"] < head[0] or (source["revision"] == head[0] and source_hash != head[1])):
            raise EvidenceDenied(409, "evidence_source_conflict")
        source_rows.append((*identity, source["ref"], source["revision"], source["audience"], source["owner"], int(source["deleted"]), _json(source)))
        source_heads.append((*identity, source["ref"], source["revision"], source_hash))
    db.execute("DELETE FROM game_evidence_sources WHERE campaign=? AND session=?", identity)
    db.execute("DELETE FROM game_evidence_participants WHERE campaign=? AND session=?", identity)
    db.executemany("INSERT INTO game_evidence_sources VALUES(?,?,?,?,?,?,?,?)", source_rows)
    db.executemany("INSERT INTO game_evidence_participants VALUES(?,?,?,?)",
                   [(*identity, item["user"], _json(item)) for item in body["participants"]])
    db.executemany("INSERT INTO game_evidence_source_heads VALUES(?,?,?,?,?) ON CONFLICT(campaign,session,ref) DO UPDATE SET revision=excluded.revision,body_hash=excluded.body_hash", source_heads)
    db.execute("INSERT INTO game_evidence_snapshots VALUES(?,?,?,?) ON CONFLICT(campaign,session) DO UPDATE SET revision=excluded.revision,body_hash=excluded.body_hash",
               (*identity, snapshot.revision, body_hash))
    return receipt


def _request_identity(campaign, session, owner, role, revision, external):
    if any(not isinstance(value, str) or not 1 <= len(value) <= 100 for value in (campaign, session, owner)):
        raise EvidenceDenied(400, "evidence_scope_invalid")
    if role not in {"host", "player"} or type(external) is not bool:
        raise EvidenceDenied(400, "evidence_scope_invalid")
    if type(revision) is not int or not 0 <= revision <= MAX_SAFE_INTEGER:
        raise EvidenceDenied(400, "evidence_revision_invalid")


def resolve_evidence(
    db: sqlite3.Connection, campaign: str, session: str, owner: str, role: str,
    revision: int, references: Sequence[EvidenceReference | Mapping], external: bool = False,
) -> dict:
    """Resolve a bounded exact-revision closure, checking every source before return.

    ACL columns are read and checked before source text is loaded. Derived
    evidence inherits all dependency access/consent restrictions. The returned
    references include the complete closure, sorted by ref, for citations.
    """
    _transaction_required(db)
    _request_identity(campaign, session, owner, role, revision, external)
    if not isinstance(references, (list, tuple)) or len(references) > MAX_REFERENCES:
        raise EvidenceDenied(400, "evidence_references_invalid")
    try:
        requested = [EvidenceReference.model_validate(item.model_dump() if isinstance(item, EvidenceReference) else item) for item in references]
        _unique(requested, "ref", "duplicate reference")
    except (ValidationError, ValueError) as exc:
        raise EvidenceDenied(400, "evidence_references_invalid") from exc
    identity = (campaign, session)
    snapshot = db.execute("SELECT revision FROM game_evidence_snapshots WHERE campaign=? AND session=?", identity).fetchone()
    if snapshot is None or snapshot[0] != revision:
        raise EvidenceDenied(409, "evidence_snapshot_stale")
    records = {}
    visiting = set()
    consent = {}
    total_text = 0

    def check_consent(source):
        if not source.contributors:
            raise EvidenceDenied(403, "evidence_external_consent_required")
        for contributor in source.contributors:
            if contributor.user not in consent:
                row = db.execute("SELECT body FROM game_evidence_participants WHERE campaign=? AND session=? AND user=?",
                                 (*identity, contributor.user)).fetchone()
                try:
                    consent[contributor.user] = EvidenceParticipant.model_validate_json(row[0]) if row else None
                except ValidationError as exc:
                    raise EvidenceDenied(500, "evidence_store_invalid") from exc
            participant = consent[contributor.user]
            if (participant is None or not participant.capture or not participant.external
                    or not contributor.exportableAtCapture
                    or contributor.captureEpoch is None or contributor.externalEpoch is None
                    or contributor.captureEpoch != participant.captureEpoch
                    or contributor.externalEpoch != participant.externalEpoch):
                raise EvidenceDenied(403, "evidence_external_consent_required")

    def visit(reference):
        nonlocal total_text
        if reference.ref in visiting:
            raise EvidenceDenied(409, "evidence_derivation_cycle")
        if reference.ref in records:
            if records[reference.ref].revision != reference.revision:
                raise EvidenceDenied(409, "evidence_source_stale")
            return
        if len(records) >= MAX_REFERENCES:
            raise EvidenceDenied(400, "evidence_closure_excessive")
        meta = db.execute("SELECT revision,audience,owner,deleted FROM game_evidence_sources WHERE campaign=? AND session=? AND ref=?",
                          (*identity, reference.ref)).fetchone()
        if meta is None or meta[3]:
            raise EvidenceDenied(409, "evidence_source_unavailable")
        if meta[0] != reference.revision:
            raise EvidenceDenied(409, "evidence_source_stale")
        if not (meta[1] == "party" or (meta[1] == "host" and role == "host") or (meta[1] == "private" and meta[2] == owner)):
            raise EvidenceDenied(403, "evidence_source_forbidden")
        row = db.execute("SELECT body FROM game_evidence_sources WHERE campaign=? AND session=? AND ref=?", (*identity, reference.ref)).fetchone()
        try:
            source = EvidenceSource.model_validate_json(row[0])
        except (TypeError, ValidationError) as exc:
            raise EvidenceDenied(500, "evidence_store_invalid") from exc
        if (source.ref, source.revision, source.audience, source.owner, int(source.deleted)) != (reference.ref, *meta):
            raise EvidenceDenied(500, "evidence_store_invalid")
        if external:
            check_consent(source)
        total_text += len(source.text)
        if total_text > MAX_TEXT:
            raise EvidenceDenied(400, "evidence_text_excessive")
        records[reference.ref] = source
        visiting.add(reference.ref)
        for dependency in source.derivesFrom:
            visit(dependency)
        visiting.remove(reference.ref)

    for reference in requested:
        visit(reference)
    ordered = sorted(records.values(), key=lambda source: source.ref)
    return {"revision": revision,
            "sources": [{key: value for key, value in _source_body(source).items() if key != "deleted"} for source in ordered],
            "references": [{"ref": source.ref, "revision": source.revision} for source in ordered]}
