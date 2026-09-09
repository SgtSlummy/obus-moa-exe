"""Independent selection fixtures: append continuity must not weaken disclosure checks."""
from copy import deepcopy
import hashlib
import json
import sqlite3

import pytest
from backend.game_evidence import EvidenceDenied
from backend.game_evidence_selection import SelectionRequest, resolve_selection
from tests.test_game_evidence import db, contributor, participant, resolve, save, snapshot, source


def selection(body, refs=None):
    """Wire oracle from the authoritative document; no backend hash helpers."""
    refs = refs or [{"ref": "entry-1", "revision": 1}]
    by_ref = {row["ref"]: row for row in body["sources"]}
    chosen = {}

    def visit(ref):
        if ref["ref"] in chosen:
            return
        row = deepcopy(by_ref[ref["ref"]])
        chosen[row["ref"]] = row
        row["contributors"].sort(key=lambda item: item["user"])
        row["derivesFrom"].sort(key=lambda item: item["ref"])
        for ancestor in row["derivesFrom"]:
            visit(ancestor)

    for ref in refs:
        visit(ref)
    users = sorted({item["user"] for row in chosen.values() for item in row["contributors"]})
    participants = {row["user"]: row for row in body["participants"]}
    document = {"contract": "raph-obus-game-selection-v1", "campaign": body["campaign"],
                "session": body["session"], "sources": sorted(chosen.values(), key=lambda row: row["ref"]),
                "participants": [{"user": user, "state": participants.get(user)} for user in users]}
    digest = hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"contract": "raph-obus-game-evidence-refs-v2", "revision": body["revision"],
            "selectionHash": digest, "references": deepcopy(refs)}


def selected(db, request, **updates):
    return resolve_selection(db, "camp-1", "session-1", "player-1", "player", request, **updates)


@pytest.mark.parametrize("external", [False, True])
def test_append_and_unrelated_participant_changes_keep_exact_selected_payload(db, external):
    body = snapshot(participants=[participant(), participant("other")], sources=[source(), source("other", contributors=[contributor("other")])])
    save(db, body)
    request = selection(body)
    before = selected(db, request, external=external)
    newer = deepcopy(body)
    newer["revision"] = 2
    newer["sources"][1].update(revision=2, text="An unrelated correction.")
    newer["sources"].append(source("new-chat", text="A later message."))
    newer["participants"][1].update(external=False, externalEpoch=3)
    save(db, newer)
    assert selected(db, request, external=external) == before
    assert before["revision"] == 1
    assert before["references"] == [{"ref": "entry-1", "revision": 1}]
    with pytest.raises(EvidenceDenied, match="evidence_snapshot_stale"):
        resolve(db)  # Legacy exact-snapshot requests keep their existing behavior.


@pytest.mark.parametrize("change", ["text", "audience", "owner", "provenance", "contributors", "derivesFrom", "deleted", "removed"])
def test_referenced_source_changes_never_reuse_old_selection(db, change):
    body = snapshot(sources=[source(), source("ancestor")])
    save(db, body)
    request = selection(body)
    newer = deepcopy(body)
    newer["revision"] = 2
    row = newer["sources"][0]
    row["revision"] = 2
    updates = {"text": "Corrected", "audience": "host", "owner": "different",
               "provenance": "corrected-provenance", "contributors": [],
               "derivesFrom": [{"ref": "ancestor", "revision": 1}], "deleted": True}
    if change == "removed":
        newer["sources"].pop(0)
    else:
        row[change] = updates[change]
    save(db, newer)
    with pytest.raises(EvidenceDenied):
        selected(db, request)


@pytest.mark.parametrize("updates", [
    {"external": False, "externalEpoch": 3}, {"capture": False, "captureEpoch": 2},
    {"externalEpoch": 3}, {"captureEpoch": 2},
])
def test_relevant_consent_changes_invalidate_even_local_results(db, updates):
    body = snapshot()
    save(db, body)
    request = selection(body)
    save(db, snapshot(revision=2, participants=[participant(**updates)]))
    with pytest.raises(EvidenceDenied, match="evidence_selection_changed"):
        selected(db, request)
    with pytest.raises(EvidenceDenied, match="evidence_external_consent_required"):
        selected(db, request, external=True)


def test_missing_participant_is_bound_and_cannot_be_silently_reintroduced(db):
    body = snapshot(participants=[])
    save(db, body)
    request = selection(body)
    assert selected(db, request)["sources"]
    with pytest.raises(EvidenceDenied, match="evidence_external_consent_required"):
        selected(db, request, external=True)
    save(db, snapshot(revision=2))
    with pytest.raises(EvidenceDenied, match="evidence_selection_changed"):
        selected(db, request)


def test_participant_removal_invalidates_local_selection(db):
    body = snapshot()
    save(db, body)
    request = selection(body)
    save(db, snapshot(revision=2, participants=[]))
    with pytest.raises(EvidenceDenied, match="evidence_selection_changed"):
        selected(db, request)


def test_derived_source_binds_ancestor_consent_and_version(db):
    body = snapshot(participants=[participant(), participant("corrector")], sources=[source(),
        source("summary", contributors=[contributor("corrector")], derivesFrom=[{"ref": "entry-1", "revision": 1}])])
    save(db, body)
    request = selection(body, [{"ref": "summary", "revision": 1}])
    assert len(selected(db, request, external=True)["sources"]) == 2
    newer = deepcopy(body)
    newer["revision"] = 2
    newer["participants"][0].update(external=False, externalEpoch=3)
    save(db, newer)
    with pytest.raises(EvidenceDenied, match="evidence_selection_changed"):
        selected(db, request)


def test_selection_hash_is_not_permission_and_acl_precedes_text_reads(db):
    body = snapshot(sources=[source(audience="host")])
    save(db, body)
    request = selection(body)
    assert resolve_selection(db, "camp-1", "session-1", "gm", "host", request)["sources"]
    db.set_authorizer(lambda action, table, column, *_: sqlite3.SQLITE_DENY
                      if action == sqlite3.SQLITE_READ and table == "game_evidence_sources" and column == "body"
                      else sqlite3.SQLITE_OK)
    try:
        with pytest.raises(EvidenceDenied, match="evidence_source_forbidden"):
            selected(db, request)
    finally:
        db.set_authorizer(None)


def test_hash_binds_scope_even_for_identical_source_content(db):
    body = snapshot()
    save(db, body)
    request = selection(body)
    save(db, snapshot(campaign="other"))
    save(db, snapshot(session="other"))
    for campaign, session in [("other", "session-1"), ("camp-1", "other")]:
        with pytest.raises(EvidenceDenied, match="evidence_selection_changed"):
            resolve_selection(db, campaign, session, "player-1", "player", request)


def test_newer_minimum_revision_and_missing_snapshot_are_denied(db):
    body = snapshot()
    request = selection(body)
    with pytest.raises(EvidenceDenied, match="evidence_snapshot_stale"):
        selected(db, request)
    save(db, body)
    request["revision"] = 2
    with pytest.raises(EvidenceDenied, match="evidence_snapshot_stale"):
        selected(db, request)


def test_transaction_required(db):
    body = snapshot()
    save(db, body)
    db.commit()
    with pytest.raises(EvidenceDenied, match="evidence_transaction_required"):
        selected(db, selection(body))


def test_canonical_unicode_order_and_shared_ancestors(db):
    users = ["\U0001f30a", "\ue000"]
    body = snapshot(participants=[participant(user) for user in users], sources=[
        source("entry-1", text="\U0001f30a\n\t\"", contributors=[contributor(user) for user in users],
               derivesFrom=[{"ref": ref, "revision": 1} for ref in users]),
        *[source(user, contributors=[contributor(user)]) for user in users]])
    save(db, body)
    request = selection(body)
    assert len(selected(db, request, external=True)["sources"]) == 3
    reordered = deepcopy(body)
    reordered["sources"].reverse()
    reordered["participants"].reverse()
    for row in reordered["sources"]:
        row["contributors"].reverse()
        row["derivesFrom"].reverse()
    assert selection(reordered) == request


@pytest.mark.parametrize("updates", [
    {"contract": "raph-obus-game-evidence-refs-v1"}, {"revision": True}, {"revision": -1},
    {"revision": 9_007_199_254_740_992}, {"selectionHash": "F" * 64}, {"selectionHash": "0" * 63},
    {"selectionHash": 0}, {"references": []}, {"references": [{"ref": "entry-1", "revision": True}]},
    {"references": [{"ref": "entry-1", "revision": 1}] * 2}, {"unrestricted_memory": True},
])
def test_wire_contract_strict_and_bounded(db, updates):
    body = snapshot()
    save(db, body)
    request = {**selection(body), **updates}
    with pytest.raises(EvidenceDenied, match="evidence_selection_invalid"):
        selected(db, request)


def test_hash_tampering_and_mutated_model_fail_closed(db):
    body = snapshot()
    save(db, body)
    request = selection(body)
    with pytest.raises(EvidenceDenied, match="evidence_selection_changed"):
        selected(db, {**request, "selectionHash": "0" * 64})
    parsed = SelectionRequest.model_validate(request)
    parsed.references.append(parsed.references[0])
    with pytest.raises(EvidenceDenied, match="evidence_selection_invalid"):
        selected(db, parsed)
