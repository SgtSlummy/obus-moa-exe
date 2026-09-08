"""Independent fixtures for complete snapshots, source lineage and consent boundaries."""
from __future__ import annotations

from copy import deepcopy
import json
import sqlite3

import pytest
from pydantic import ValidationError

from backend.game_evidence import (
    CONTRACT, EvidenceDenied, EvidenceReference, EvidenceSnapshot,
    initialize_schema, resolve_evidence, save_snapshot,
)


def participant(user="player-1", **updates):
    return {"user": user, "capture": True, "external": True, "captureEpoch": 1, "externalEpoch": 2, **updates}


def contributor(user="player-1", **updates):
    return {"user": user, "captureEpoch": 1, "externalEpoch": 2, "exportableAtCapture": True, **updates}


def source(ref="entry-1", **updates):
    return {"ref": ref, "revision": 1, "audience": "party", "owner": "", "text": "The lantern glows.",
            "provenance": "chronicle:entry-1", "deleted": False, "contributors": [contributor()], "derivesFrom": [], **updates}


def snapshot(**updates):
    return {"contract": CONTRACT, "campaign": "camp-1", "session": "session-1", "revision": 1,
            "runtime": {"contract": "raph-obus-game-runtime-v1", "bootEpoch": "boot-1",
                        "generation": "generation-1", "sessionPolicyRevision": 0},
            "participants": [participant()], "sources": [source()], **updates}


def save(db, body=None, **updates):
    return save_snapshot(db, EvidenceSnapshot.model_validate(body or snapshot(**updates)))


def resolve(db, *, campaign="camp-1", session="session-1", owner="player-1", role="player", revision=1, refs=None, external=False):
    return resolve_evidence(db, campaign, session, owner, role, revision,
                            [{"ref": "entry-1", "revision": 1}] if refs is None else refs, external=external)


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    connection.execute("BEGIN")
    try:
        yield connection
    finally:
        connection.close()


def test_save_receipt_is_bounded_and_contains_no_text_or_identity(db):
    receipt = save(db)
    assert receipt == {"contract": CONTRACT, "campaign": "camp-1", "session": "session-1", "revision": 1,
                       "status": "saved", "sourceCount": 1, "participantCount": 1}
    assert "player-1" not in json.dumps(receipt)
    assert "lantern" not in json.dumps(receipt)
    assert db.in_transaction


def test_exact_replay_and_runtime_restart_do_not_change_content_digest(db):
    save(db)
    changed_runtime = snapshot()
    changed_runtime["runtime"].update(bootEpoch="boot-2", generation="generation-2", sessionPolicyRevision=7)
    assert save(db, changed_runtime)["status"] == "unchanged"
    assert resolve(db)["sources"][0]["text"] == "The lantern glows."


def test_unordered_records_have_same_canonical_digest(db):
    first = snapshot(participants=[participant("player-1"), participant("player-2")], sources=[
        source("a", contributors=[contributor("player-1"), contributor("player-2")],
               derivesFrom=[{"ref": "b", "revision": 1}, {"ref": "c", "revision": 1}]), source("b"), source("c")])
    save(db, first)
    reordered = deepcopy(first)
    reordered["participants"].reverse()
    reordered["sources"][0]["contributors"].reverse()
    reordered["sources"][0]["derivesFrom"].reverse()
    reordered["sources"].reverse()
    assert save(db, reordered)["status"] == "unchanged"


@pytest.mark.parametrize("revision,code", [(0, "evidence_snapshot_stale"), (1, "evidence_snapshot_conflict")])
def test_snapshot_revision_conflicts_leave_current_state(db, revision, code):
    save(db)
    with pytest.raises(EvidenceDenied) as denied:
        save(db, snapshot(revision=revision, sources=[source(text="rewritten")]))
    assert denied.value.status == 409
    assert denied.value.code == code
    assert resolve(db)["sources"][0]["text"] == "The lantern glows."


@pytest.mark.parametrize("source_revision", [0, 1])
def test_source_revision_cannot_regress_or_change_meaning(db, source_revision):
    save(db)
    with pytest.raises(EvidenceDenied, match="evidence_source_conflict"):
        save(db, snapshot(revision=2, sources=[source(revision=source_revision, text="rewritten")]))
    assert resolve(db)["revision"] == 1


def test_removed_sources_are_unavailable_and_keep_only_revision_hash(db):
    save(db)
    save(db, snapshot(revision=2, sources=[]))
    assert db.execute("SELECT COUNT(*) FROM game_evidence_sources").fetchone()[0] == 0
    head = db.execute("SELECT revision,body_hash FROM game_evidence_source_heads").fetchone()
    assert head[0] == 1 and len(head[1]) == 64
    with pytest.raises(EvidenceDenied, match="evidence_source_unavailable"):
        resolve(db, revision=2)
    with pytest.raises(EvidenceDenied, match="evidence_source_conflict"):
        save(db, snapshot(revision=3, sources=[source(text="reintroduced differently")]))
    save(db, snapshot(revision=3, sources=[source(revision=2, text="revised source")]))
    assert resolve(db, revision=3, refs=[{"ref": "entry-1", "revision": 2}])["sources"][0]["text"] == "revised source"


def test_save_and_resolve_require_caller_owned_transaction(db):
    db.commit()
    for operation in (lambda: save(db), lambda: resolve(db)):
        with pytest.raises(EvidenceDenied, match="evidence_transaction_required"):
            operation()
    assert not db.in_transaction
    assert db.execute("SELECT COUNT(*) FROM game_evidence_snapshots").fetchone()[0] == 0


def test_schema_initialization_does_not_commit_transaction():
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.execute("BEGIN")
        initialize_schema(connection)
        assert connection.in_transaction
        connection.rollback()
        assert connection.execute("SELECT name FROM sqlite_master WHERE name LIKE 'game_evidence_%'").fetchall() == []
    finally:
        connection.close()


def test_failed_complete_snapshot_rolls_back_all_tables(db):
    save(db)
    db.commit()
    db.execute("CREATE TRIGGER reject_fixture BEFORE INSERT ON game_evidence_participants WHEN NEW.user='rejected' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    db.execute("BEGIN")
    with pytest.raises(sqlite3.IntegrityError, match="fixture failure"):
        save(db, snapshot(revision=2, participants=[participant("rejected")], sources=[source("new-source")]))
    db.rollback()
    db.execute("BEGIN")
    assert resolve(db)["sources"][0]["ref"] == "entry-1"
    assert db.execute("SELECT ref FROM game_evidence_source_heads").fetchall()[0][0] == "entry-1"
    assert db.execute("SELECT COUNT(*) FROM game_evidence_source_heads").fetchone()[0] == 1


@pytest.mark.parametrize("path,value", [
    (("revision",), True), (("revision",), -1), (("revision",), 1.0), (("revision",), "1"),
    (("revision",), 9_007_199_254_740_992), (("runtime", "sessionPolicyRevision"), False),
    (("participants", 0, "capture"), 1), (("participants", 0, "external"), "false"),
    (("participants", 0, "captureEpoch"), None), (("participants", 0, "externalEpoch"), True),
    (("sources", 0, "revision"), False), (("sources", 0, "deleted"), 0),
    (("sources", 0, "contributors", 0, "exportableAtCapture"), "true"),
    (("sources", 0, "contributors", 0, "captureEpoch"), 1.2),
    (("sources", 0, "contributors", 0, "captureEpoch"), None),
    (("campaign",), ""), (("session",), "x" * 101), (("sources", 0, "ref"), "x" * 161),
    (("sources", 0, "provenance"), ""), (("sources", 0, "text"), "x" * 16001),
    (("sources", 0, "contributors", 0, "user"), ""),
])
def test_snapshot_rejects_coercion_invalid_epochs_and_unbounded_fields(path, value):
    body = snapshot()
    item = body
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = value
    with pytest.raises(ValidationError):
        EvidenceSnapshot.model_validate(body)


@pytest.mark.parametrize("where", ["snapshot", "runtime", "participant", "source", "contributor", "derivation"])
def test_snapshot_rejects_unknown_fields(where):
    body = snapshot()
    targets = {"snapshot": body, "runtime": body["runtime"], "participant": body["participants"][0],
               "source": body["sources"][0], "contributor": body["sources"][0]["contributors"][0]}
    body["sources"][0]["derivesFrom"] = [{"ref": "other", "revision": 1}]
    targets["derivation"] = body["sources"][0]["derivesFrom"][0]
    targets[where]["unrestricted_memory"] = True
    with pytest.raises(ValidationError):
        EvidenceSnapshot.model_validate(body)


@pytest.mark.parametrize("kind", ["participant", "source", "contributor", "derivation"])
def test_duplicate_identities_rejected(kind):
    body = snapshot()
    if kind == "participant":
        body["participants"].append(participant())
    elif kind == "source":
        body["sources"].append(source(revision=2))
    elif kind == "contributor":
        body["sources"][0]["contributors"].append(contributor(externalEpoch=3))
    else:
        body["sources"][0]["derivesFrom"] = [{"ref": "same", "revision": 1}, {"ref": "same", "revision": 2}]
    with pytest.raises(ValidationError):
        EvidenceSnapshot.model_validate(body)


def test_snapshot_utf8_bytes_and_record_counts_are_bounded():
    with pytest.raises(ValidationError, match="byte limit"):
        EvidenceSnapshot.model_validate(snapshot(sources=[source(str(index), text="\U0001f30a" * 16000) for index in range(12)]))
    with pytest.raises(ValidationError):
        EvidenceSnapshot.model_validate(snapshot(participants=[participant(str(index)) for index in range(257)]))
    with pytest.raises(ValidationError):
        EvidenceSnapshot.model_validate(snapshot(sources=[source(str(index), text="") for index in range(2049)]))


def test_validation_cannot_be_bypassed_by_mutating_an_existing_model(db):
    body = EvidenceSnapshot.model_validate(snapshot())
    body.sources[0].deleted = "false"
    with pytest.warns(UserWarning, match="Pydantic serializer warnings"):
        with pytest.raises(EvidenceDenied, match="evidence_snapshot_invalid"):
            save_snapshot(db, body)
    assert db.execute("SELECT COUNT(*) FROM game_evidence_snapshots").fetchone()[0] == 0


def test_cross_campaign_and_session_records_never_collide(db):
    save(db)
    save(db, snapshot(campaign="other-campaign", sources=[source(text="other campaign secret")]))
    save(db, snapshot(session="other-session", sources=[source(text="other session secret")]))
    assert resolve(db)["sources"][0]["text"] == "The lantern glows."
    assert resolve(db, campaign="other-campaign")["sources"][0]["text"] == "other campaign secret"
    assert resolve(db, session="other-session")["sources"][0]["text"] == "other session secret"
    with pytest.raises(EvidenceDenied, match="evidence_snapshot_stale"):
        resolve(db, session="missing")


@pytest.mark.parametrize("audience,record_owner,viewer,role,allowed", [
    ("party", "", "player-1", "player", True), ("host", "", "gm", "host", True),
    ("host", "", "player-1", "player", False), ("private", "player-1", "player-1", "player", True),
    ("private", "player-1", "other", "player", False), ("private", "player-1", "gm", "host", False),
])
def test_source_acl(audience, record_owner, viewer, role, allowed, db):
    save(db, snapshot(sources=[source(audience=audience, owner=record_owner)]))
    if allowed:
        assert resolve(db, owner=viewer, role=role)["sources"][0]["audience"] == audience
    else:
        with pytest.raises(EvidenceDenied, match="evidence_source_forbidden"):
            resolve(db, owner=viewer, role=role)


def test_acl_denial_happens_before_source_text_is_loaded(db):
    save(db, snapshot(sources=[source(audience="host", text="GM secret")]))

    def deny_text_reads(action, table, column, _database, _trigger):
        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "game_evidence_sources" and column == "body" else sqlite3.SQLITE_OK

    db.set_authorizer(deny_text_reads)
    try:
        with pytest.raises(EvidenceDenied, match="evidence_source_forbidden"):
            resolve(db)
        with pytest.raises(sqlite3.DatabaseError):
            resolve(db, role="host")
    finally:
        db.set_authorizer(None)


@pytest.mark.parametrize("reason", ["missing", "capture_off", "external_off", "capture_epoch", "external_epoch", "capture_export_off", "null", "empty"])
def test_external_consent_fails_closed_for_every_contributor_condition(db, reason):
    body = snapshot()
    if reason == "missing":
        body["participants"] = []
    elif reason == "capture_off":
        body["participants"][0]["capture"] = False
    elif reason == "external_off":
        body["participants"][0]["external"] = False
    elif reason == "capture_epoch":
        body["participants"][0]["captureEpoch"] = 3
    elif reason == "external_epoch":
        body["participants"][0]["externalEpoch"] = 3
    elif reason == "capture_export_off":
        body["sources"][0]["contributors"][0]["exportableAtCapture"] = False
    elif reason == "null":
        body["sources"][0]["contributors"] = [contributor("unknown", captureEpoch=None, externalEpoch=None, exportableAtCapture=False)]
    else:
        body["sources"][0]["contributors"] = []
    save(db, body)
    assert resolve(db)["sources"]  # Local play still supports historical evidence.
    with pytest.raises(EvidenceDenied, match="evidence_external_consent_required") as denied:
        resolve(db, external=True)
    assert denied.value.status == 403


def test_external_consent_success_then_withdrawal_invalidates_resolution(db):
    save(db)
    assert resolve(db, external=True)["sources"]
    save(db, snapshot(revision=2, participants=[participant(external=False, externalEpoch=3)]))
    with pytest.raises(EvidenceDenied, match="evidence_snapshot_stale"):
        resolve(db, external=True)
    with pytest.raises(EvidenceDenied, match="evidence_external_consent_required"):
        resolve(db, revision=2, external=True)
    assert resolve(db, revision=2)["sources"]


def test_known_correction_cannot_erase_unknown_original_author(db):
    lineage = [contributor("unknown", captureEpoch=None, externalEpoch=None, exportableAtCapture=False), contributor("corrector")]
    save(db, snapshot(participants=[participant("corrector")], sources=[source(contributors=lineage)]))
    assert len(resolve(db)["sources"][0]["contributors"]) == 2
    with pytest.raises(EvidenceDenied, match="evidence_external_consent_required"):
        resolve(db, external=True)


def test_normalized_derivation_closure_is_returned_without_unrequested_sources(db):
    save(db, snapshot(sources=[source("summary", derivesFrom=[{"ref": "entry-1", "revision": 1}]), source(), source("unrequested", text="irrelevant")]))
    resolved = resolve(db, refs=[EvidenceReference(ref="summary", revision=1)], external=True)
    assert resolved["references"] == [{"ref": "entry-1", "revision": 1}, {"ref": "summary", "revision": 1}]
    assert [item["ref"] for item in resolved["sources"]] == ["entry-1", "summary"]
    assert all(set(item) == {"ref", "revision", "text", "provenance", "audience", "owner", "contributors", "derivesFrom"} for item in resolved["sources"])


@pytest.mark.parametrize("problem,code", [
    ("missing", "evidence_source_unavailable"), ("deleted", "evidence_source_unavailable"),
    ("stale", "evidence_source_stale"), ("private", "evidence_source_forbidden"),
    ("consent", "evidence_external_consent_required"), ("cycle", "evidence_derivation_cycle"),
])
def test_derivations_cannot_hide_stale_secret_or_nonconsensual_evidence(db, problem, code):
    child = source()
    summary = source("summary", derivesFrom=[{"ref": "entry-1", "revision": 1}])
    if problem == "deleted":
        child["deleted"] = True
    elif problem == "stale":
        child["revision"] = 2
    elif problem == "private":
        child.update(audience="private", owner="other-player")
    elif problem == "consent":
        child["contributors"] = []
    elif problem == "cycle":
        child["derivesFrom"] = [{"ref": "summary", "revision": 1}]
    save(db, snapshot(sources=[summary] if problem == "missing" else [summary, child]))
    with pytest.raises(EvidenceDenied, match=code):
        resolve(db, refs=[{"ref": "summary", "revision": 1}], external=True)


def test_closure_bound_counts_dependencies_and_deduplicates_shared_ancestors(db):
    chain = [source(f"entry-{index}", text="", derivesFrom=[] if index == 32 else [{"ref": f"entry-{index+1}", "revision": 1}]) for index in range(33)]
    save(db, snapshot(sources=chain))
    with pytest.raises(EvidenceDenied, match="evidence_closure_excessive"):
        resolve(db, refs=[{"ref": "entry-0", "revision": 1}])
    shared = [source("leaf"), source("left", derivesFrom=[{"ref": "leaf", "revision": 1}]), source("right", derivesFrom=[{"ref": "leaf", "revision": 1}])]
    save(db, snapshot(revision=2, sources=shared))
    assert len(resolve(db, revision=2, refs=[{"ref": "left", "revision": 1}, {"ref": "right", "revision": 1}])["sources"]) == 3


def test_total_resolved_text_is_bounded(db):
    save(db, snapshot(sources=[source("a", text="x" * 8000), source("b", text="y" * 8000), source("c", text="z")]))
    refs = [{"ref": "a", "revision": 1}, {"ref": "b", "revision": 1}]
    assert len(resolve(db, refs=refs)["sources"]) == 2
    with pytest.raises(EvidenceDenied, match="evidence_text_excessive"):
        resolve(db, refs=refs + [{"ref": "c", "revision": 1}])


@pytest.mark.parametrize("refs", [
    "entry-1", [{"ref": "entry-1", "revision": True}], [{"ref": "entry-1", "revision": -1}],
    [{"ref": "entry-1", "revision": 1, "text": "injected"}],
    [{"ref": "entry-1", "revision": 1}, {"ref": "entry-1", "revision": 1}],
    [{"ref": str(index), "revision": 1} for index in range(33)],
])
def test_invalid_reference_requests_are_rejected(db, refs):
    save(db)
    with pytest.raises(EvidenceDenied, match="evidence_references_invalid"):
        resolve(db, refs=refs)


def test_empty_reference_request_still_requires_current_snapshot(db):
    save(db)
    assert resolve(db, refs=[]) == {"revision": 1, "sources": [], "references": []}
    with pytest.raises(EvidenceDenied, match="evidence_snapshot_stale"):
        resolve(db, refs=[], revision=2)


def test_corrected_source_invalidates_older_summary_dependency(db):
    summary = source("summary", derivesFrom=[{"ref": "entry-1", "revision": 1}])
    save(db, snapshot(sources=[source(), summary]))
    save(db, snapshot(revision=2, sources=[source(revision=2, text="Corrected lantern evidence."), summary]))
    with pytest.raises(EvidenceDenied, match="evidence_source_stale"):
        resolve(db, revision=2, refs=[{"ref": "summary", "revision": 1}])
    summary.update(revision=2, derivesFrom=[{"ref": "entry-1", "revision": 2}], text="Corrected summary.")
    save(db, snapshot(revision=3, sources=[source(revision=2, text="Corrected lantern evidence."), summary]))
    assert resolve(db, revision=3, refs=[{"ref": "summary", "revision": 2}])["references"] == [{"ref": "entry-1", "revision": 2}, {"ref": "summary", "revision": 2}]


@pytest.mark.parametrize("updates", [
    {"captureEpoch": 0}, {"externalEpoch": 1}, {"capture": False}, {"external": False},
    {"capture": False, "externalEpoch": 3}, {"external": False, "captureEpoch": 2},
])
def test_consent_epochs_cannot_regress_or_ignore_flag_changes(db, updates):
    save(db)
    with pytest.raises(EvidenceDenied, match="evidence_consent_conflict"):
        save(db, snapshot(revision=2, participants=[participant(**updates)]))
    assert resolve(db, external=True)["sources"]


def test_consent_reenable_requires_new_epochs_and_cannot_revive_old_evidence(db):
    save(db)
    save(db, snapshot(revision=2, participants=[participant(capture=False, external=False, captureEpoch=2, externalEpoch=3)]))
    with pytest.raises(EvidenceDenied, match="evidence_consent_conflict"):
        save(db, snapshot(revision=3, participants=[participant(captureEpoch=2, externalEpoch=3)]))
    save(db, snapshot(revision=3, participants=[participant(captureEpoch=3, externalEpoch=4)]))
    with pytest.raises(EvidenceDenied, match="evidence_external_consent_required"):
        resolve(db, revision=3, external=True)
    assert resolve(db, revision=3)["sources"]


@pytest.mark.parametrize("capture_epoch,external_epoch", [(1, 2), (2, 2), (1, 3)])
def test_disappearance_cannot_restore_true_consent_with_reused_epoch(db, capture_epoch, external_epoch):
    save(db)
    save(db, snapshot(revision=2, participants=[]))
    with pytest.raises(EvidenceDenied, match="evidence_consent_conflict"):
        save(db, snapshot(revision=3, participants=[participant(captureEpoch=capture_epoch, externalEpoch=external_epoch)]))
    assert db.execute("SELECT present FROM game_evidence_participant_heads").fetchone()[0] == 0
    with pytest.raises(EvidenceDenied, match="evidence_external_consent_required"):
        resolve(db, revision=2, external=True)


def test_reappearance_with_new_epochs_does_not_resurrect_old_lineage(db):
    save(db)
    save(db, snapshot(revision=2, participants=[]))
    save(db, snapshot(revision=3, participants=[participant(captureEpoch=2, externalEpoch=3)]))
    with pytest.raises(EvidenceDenied, match="evidence_external_consent_required"):
        resolve(db, revision=3, external=True)
    revised = source(revision=2, text="New recording after renewed consent.", contributors=[contributor(captureEpoch=2, externalEpoch=3)])
    save(db, snapshot(revision=4, participants=[participant(captureEpoch=2, externalEpoch=3)], sources=[revised]))
    assert resolve(db, revision=4, refs=[{"ref": "entry-1", "revision": 2}], external=True)["sources"]


def test_consent_high_water_is_campaign_and_session_scoped(db):
    save(db)
    for updates in ({"campaign": "camp-2"}, {"session": "session-2"}):
        save(db, snapshot(**updates, participants=[participant(capture=False, external=False, captureEpoch=0, externalEpoch=0)]))
    assert resolve(db, external=True)["sources"]


@pytest.mark.parametrize("updates,code", [
    ({"owner": ""}, "evidence_scope_invalid"), ({"campaign": 1}, "evidence_scope_invalid"),
    ({"session": "x" * 101}, "evidence_scope_invalid"), ({"role": []}, "evidence_scope_invalid"),
    ({"role": "admin"}, "evidence_scope_invalid"), ({"external": "true"}, "evidence_scope_invalid"),
    ({"revision": True}, "evidence_revision_invalid"), ({"revision": -1}, "evidence_revision_invalid"),
])
def test_resolver_scope_types_fail_closed(db, updates, code):
    save(db)
    with pytest.raises(EvidenceDenied, match=code):
        resolve(db, **updates)
