"""Versioned selection consistency for summaries during continuous capture.

A selection hash binds exact source content and relevant CURRENT consent. It is
not authorization: every resolution still checks scope, ACL, derivation, current
external consent and the incomplete-upload barrier through the legacy resolver.
Unrelated additions can advance the store without changing the selected context.
The caller owns the runtime-fenced transaction and must re-resolve before commit.
"""
from __future__ import annotations

import hmac
import sqlite3
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator
from backend.game_evidence import (
    EvidenceDenied, EvidenceParticipant, EvidenceReference, EvidenceSource,
    MAX_REFERENCES, MAX_SAFE_INTEGER, SafeInt, Strict, _digest, _request_identity,
    _source_body, _transaction_required, _unique, resolve_evidence,
)

CONTRACT = "raph-obus-game-evidence-refs-v2"
STAMP_CONTRACT = "raph-obus-game-selection-v1"


class SelectionRequest(Strict):
    contract: Literal["raph-obus-game-evidence-refs-v2"]
    revision: SafeInt
    selectionHash: Annotated[str, Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
    references: Annotated[list[EvidenceReference], Field(min_length=1, max_length=MAX_REFERENCES)]

    @model_validator(mode="after")
    def unique_references(self):
        _unique(self.references, "ref", "duplicate reference")
        return self


def _parse_request(value: SelectionRequest | dict) -> SelectionRequest:
    try:
        return SelectionRequest.model_validate(value.model_dump() if isinstance(value, SelectionRequest) else value)
    except (ValidationError, ValueError, TypeError) as exc:
        raise EvidenceDenied(400, "evidence_selection_invalid") from exc


def _selection_document(db: sqlite3.Connection, campaign: str, session: str, resolved: dict) -> dict:
    # All sources have passed the resolver's ACL and transitive closure checks.
    # Canonicalize independently of discovery order and include complete lineage.
    sources = sorted((_source_body(EvidenceSource.model_validate({**source, "deleted": False}))
                      for source in resolved["sources"]), key=lambda source: source["ref"])
    users = sorted({contributor["user"] for source in sources for contributor in source["contributors"]})
    participants = []
    for user in users:
        row = db.execute("SELECT body FROM game_evidence_participants WHERE campaign=? AND session=? AND user=?",
                         (campaign, session, user)).fetchone()
        try:
            participant = EvidenceParticipant.model_validate_json(row[0]) if row else None
        except (ValidationError, ValueError, TypeError) as exc:
            raise EvidenceDenied(500, "evidence_store_invalid") from exc
        if participant is not None and participant.user != user:
            raise EvidenceDenied(500, "evidence_store_invalid")
        participants.append({"user": user, "state": participant.model_dump() if participant else None})
    return {"contract": STAMP_CONTRACT, "campaign": campaign, "session": session,
            "sources": sources, "participants": participants}


def resolve_selection(
    db: sqlite3.Connection, campaign: str, session: str, owner: str, role: str,
    request: SelectionRequest | dict, external: bool = False,
) -> dict:
    """Resolve current authorized content iff the complete selection is unchanged.

    `revision` is a minimum synchronized snapshot version; individual references
    and selectionHash remain exact. Returning the request's baseline revision
    keeps the rendered summary and dispatch fingerprint stable across additions.
    Legacy resolve_evidence and refs-v1 continue requiring an exact snapshot.
    """
    _transaction_required(db)
    request = _parse_request(request)
    _request_identity(campaign, session, owner, role, request.revision, external)
    head = db.execute("SELECT revision FROM game_evidence_snapshots WHERE campaign=? AND session=?",
                      (campaign, session)).fetchone()
    if head is None:
        raise EvidenceDenied(409, "evidence_snapshot_stale")
    current_revision = head[0]
    if type(current_revision) is not int or not 0 <= current_revision <= MAX_SAFE_INTEGER:
        raise EvidenceDenied(500, "evidence_store_invalid")
    if current_revision < request.revision:
        raise EvidenceDenied(409, "evidence_snapshot_stale")
    resolved = resolve_evidence(db, campaign, session, owner, role, current_revision,
                                request.references, external=external)
    stamp = _digest(_selection_document(db, campaign, session, resolved))
    if not hmac.compare_digest(stamp, request.selectionHash):
        raise EvidenceDenied(409, "evidence_selection_changed")
    return {**resolved, "revision": request.revision}
