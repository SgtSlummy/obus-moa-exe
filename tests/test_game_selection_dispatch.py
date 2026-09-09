"""Real Obus ledger/runtime transitions; external provider responses are fixtures."""
import hashlib
import json
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend import game_agent as g, game_dispatch as ledger
from tests.test_game_evidence_selection_api import env, request, appended
from tests.test_game_evidence_uploads import transfer

FREE = {"id": "fixture-free", "provider": "openrouter", "model": "fixture:free",
        "connected": True, "verified": True,
        "game_free_pin": {"downstream_provider_name": "fixture-provider"}}
PROVENANCE = {"route_id": FREE["id"], "model": FREE["model"], "provider": "fixture-provider",
              "gateway": "openrouter", "destination": "external", "cost": "zero",
              "cost_basis": "free-variant+zero-price-ceiling+response-usage"}


def set_policy(env, *, enabled=True):
    master = env.authority.snapshot("camp", "campaign")
    env.authority.patch_policy({
        "contract": g.RUNTIME_CONTRACT, "campaign": "camp", "session": "campaign",
        "expectedBootEpoch": master.boot_epoch, "expectedGeneration": master.generation,
        "expectedSessionPolicyRevision": master.policy_revision, "opId": str(uuid.uuid4()),
        "policy": {"enabled": enabled, "mode": "local-free", "codex": False, "exportable": True},
    })
    runtime = env.client.get("/api/game/runtime?campaign=camp&session=session", headers=env.headers).json()
    env.fence = {key: runtime[key] for key in ("contract", "bootEpoch", "generation", "sessionPolicyRevision")}


@pytest.fixture
def external(env):
    set_policy(env)
    body = env.snapshot()
    g._save_evidence_snapshot(body)
    job = request(env, body, policy={"namespace": "camp", "mode": "local-free", "exportable": True})
    return env, body, job


def run_remote(job, effect=lambda: None):
    calls = []
    def remote(_key, prompt, _budget):
        calls.append(prompt)
        effect()
        return {**PROVENANCE, "endpoint": "https://openrouter.ai/api/v1/chat/completions",
                "text": "Two bell strokes were heard [S1]."}
    with patch.object(g, "approved_free", return_value=[FREE]), patch.object(g, "retrieve", side_effect=AssertionError("general RAG forbidden")):
        result = g.run_job(job, get_keys=lambda: [FREE], local=lambda *_: pytest.fail("unexpected local provider"), remote=remote)
    return result, calls


def rows():
    with g.database() as db:
        return [dict(row) for row in db.execute("SELECT * FROM dispatch_attempts ORDER BY created_at_ms")]


def queued(job, *, legacy=False):
    fingerprint = hashlib.sha256(job.model_dump_json().encode()).hexdigest()
    with g._dispatch_transaction(job) as (db, state):
        record = ledger.enqueue(db, campaign=job.scope.campaign, session=job.session, owner=job.scope.owner,
            request_id=job.requestId, fingerprint=fingerprint, task=job.task,
            boot_epoch=state.boot_epoch, generation=state.generation, policy_revision=state.policy_revision,
            evidence_revision=job.evidence["revision"], evidence_digest="a" * 64,
            route_id=FREE["id"], route_digest="b" * 64, provider="fixture-provider", model=FREE["model"], now_ms=1,
            evidence_selection=None if legacy else {"role": job.scope.role, "request": job.evidence})
    return record["attemptId"], fingerprint


def mark(job, attempt, fingerprint):
    with g._dispatch_transaction(job) as (db, _):
        return ledger.mark_dispatched(db, attempt, fingerprint=fingerprint, now_ms=2)


def finish(job, attempt, fingerprint):
    with g._receipt_transaction(job.scope.campaign, job.session, job.runtime) as db:
        return ledger.finish(db, attempt, fingerprint=fingerprint, now_ms=3, outcome="completed", provenance=PROVENANCE)


def test_external_append_finishes_once_and_replays_without_provider(external):
    env, body, job = external
    result, calls = run_remote(job, lambda: g._save_evidence_snapshot(appended(body)))
    assert len(calls) == 1
    assert "Unrelated" not in calls[0]
    replay, replay_calls = run_remote(job, lambda: pytest.fail("replay dispatched"))
    assert replay == result and replay_calls == []
    assert env.receipts() == 1
    assert [(row["status"], row["cancel_requested"]) for row in rows()] == [("completed", 0)]
    public = ledger.public_recent(g.ROOT / "game.sqlite", "camp", "session")
    encoded = json.dumps(public)
    for secret in ("selectionHash", "chronicle:session:E1", "harbor bell", "generation"):
        assert secret not in encoded


@pytest.mark.parametrize("change", ["consent", "correction", "private", "removed"])
def test_external_relevant_change_discards_result_without_reexport(external, change):
    env, body, job = external
    newer = appended(body)
    if change == "consent":
        newer["participants"][0].update(external=False, externalEpoch=2)
    elif change == "correction":
        newer["sources"][0].update(revision=2, text="The bell rang three times.")
    elif change == "private":
        newer["sources"][0].update(revision=2, audience="private", owner="other")
    else:
        newer["sources"].pop(0)
    with pytest.raises(HTTPException):
        run_remote(job, lambda: g._save_evidence_snapshot(newer))
    assert env.receipts() == 0
    row = rows()[0]
    assert (row["status"], row["cancel_requested"], row["cancel_reason"]) == ("discarded", 1, "evidence_changed")
    with pytest.raises(HTTPException):
        run_remote(job, lambda: pytest.fail("invalid selection reexported"))


def test_external_policy_withdrawal_is_not_relaxed_by_later_append(external):
    env, body, job = external
    def effect():
        set_policy(env, enabled=False)
        newer = appended(body)
        newer["runtime"] = env.fence
        g._save_evidence_snapshot(newer)
    with pytest.raises(HTTPException):
        run_remote(job, effect)
    row = rows()[0]
    assert (row["status"], row["cancel_requested"], row["cancel_reason"]) == ("discarded", 1, "policy_changed")
    assert env.receipts() == 0


def test_unknown_external_outcome_never_reexports_after_append(external):
    env, body, job = external
    with pytest.raises(HTTPException, match="uncertain"):
        run_remote(job, lambda: (_ for _ in ()).throw(TimeoutError("unknown delivery")))
    assert rows()[0]["status"] == "uncertain"
    g._save_evidence_snapshot(appended(body))
    with pytest.raises(HTTPException):
        run_remote(job, lambda: pytest.fail("unknown outcome reexported"))
    assert rows()[0]["status"] == "uncertain"
    assert env.receipts() == 0


@pytest.mark.parametrize("complete", [False, True])
def test_external_upload_barrier_prevents_completion_until_atomic_promotion(external, complete):
    env, body, job = external
    begin, pages, commit = transfer(appended(body))
    def effect():
        g._upload_evidence(begin)
        assert rows()[0]["status"] == "dispatched"
        assert rows()[0]["cancel_requested"] == 0
        if complete:
            for page in pages:
                g._upload_evidence(page)
            g._upload_evidence(commit)
    if complete:
        assert run_remote(job, effect)[0]["evidenceRevision"] == 1
        assert rows()[0]["status"] == "completed"
    else:
        with pytest.raises(HTTPException, match="evidence_upload_pending"):
            run_remote(job, effect)
        assert rows()[0]["status"] == "discarded"
        for page in pages:
            g._upload_evidence(page)
        g._upload_evidence(commit)
        with pytest.raises(HTTPException):
            run_remote(job, lambda: pytest.fail("discarded attempt resurrected"))
        assert env.receipts() == 0


def test_queued_selection_cannot_dispatch_during_pending_upload(external):
    env, body, job = external
    attempt, fingerprint = queued(job)
    begin, pages, commit = transfer(appended(body))
    g._upload_evidence(begin)
    with pytest.raises(HTTPException, match="evidence_upload_pending"):
        mark(job, attempt, fingerprint)
    assert rows()[0]["status"] == "queued"
    for page in pages:
        g._upload_evidence(page)
    g._upload_evidence(commit)
    assert mark(job, attempt, fingerprint)["status"] == "dispatched"
    assert finish(job, attempt, fingerprint)["status"] == "completed"
    with pytest.raises(HTTPException):
        mark(job, attempt, fingerprint)


def test_queued_selection_is_cancelled_when_staged_consent_change_commits(external):
    env, body, job = external
    attempt, fingerprint = queued(job)
    newer = appended(body)
    newer["participants"][0].update(external=False, externalEpoch=2)
    begin, pages, commit = transfer(newer)
    g._upload_evidence(begin)
    for page in pages:
        g._upload_evidence(page)
    g._upload_evidence(commit)
    assert rows()[0]["status"] == "cancelled"
    with pytest.raises(HTTPException):
        mark(job, attempt, fingerprint)


def test_legacy_attempt_still_cancels_on_unrelated_append(external):
    env, body, job = external
    queued(job, legacy=True)
    g._save_evidence_snapshot(appended(body))
    assert (rows()[0]["status"], rows()[0]["cancel_reason"]) == ("cancelled", "evidence_changed")


def test_policy_cancelled_queue_is_not_resurrected_after_upload(external):
    env, body, job = external
    queued(job)
    set_policy(env, enabled=False)
    newer = appended(body)
    newer["runtime"] = env.fence
    begin, pages, commit = transfer(newer)
    g._upload_evidence(begin)
    for page in pages:
        g._upload_evidence(page)
    g._upload_evidence(commit)
    assert (rows()[0]["status"], rows()[0]["cancel_reason"]) == ("cancelled", "policy_changed")


def test_ledger_direct_completion_and_replay_recheck_selection(external):
    env, body, job = external
    attempt, fingerprint = queued(job)
    mark(job, attempt, fingerprint)
    finish(job, attempt, fingerprint)
    newer = appended(body)
    newer["participants"][0].update(external=False, externalEpoch=2)
    g._save_evidence_snapshot(newer)
    with pytest.raises(ledger.DispatchDenied, match="evidence_external_consent_required"):
        finish(job, attempt, fingerprint)
    assert rows()[0]["status"] == "completed"
