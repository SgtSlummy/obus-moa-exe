# A23 external-verifier handoff

## Purpose and authority boundary

This brief is the operational handoff for an **authorized external evaluator** to run the evaluation required by the Obus Autonomous AGI Claim Contract v2.0.0. It is a planning and evidence-collection artifact only. It cannot validate a run, supply missing evidence, authorize a promotion, or change Obus's reported maturity level.

Obus may prepare, sandbox, evaluate, reject, monitor, and roll back candidate improvements. It may not alter the evaluator or held-out suite, inspect held-out answers, increase its authority, or certify its own A23 claim. Promotion remains a human and independent-evaluator decision.

## Current truthful starting point

- Current reported level: **A2 — bounded autonomous agent platform**.
- Target: **A23 — externally verified 23-gate Autonomous AGI**.
- Current qualification: **not earned**; no qualification receipt is persisted.
- Required evidence: **three consecutive sealed primary runs** and **at least one independent organizational replication**.
- The local Qwen warm-runtime result and the public cross-model development baseline are operational/development evidence. They are not sealed capability evidence and cannot qualify or promote A23.
- The current public baseline identified no measured local deficit. Its correct result is to decline an automatic improvement candidate, not create a decorative loop.

## What the evaluator must keep independent

The evaluator must own the held-out task material and scoring process. Obus operators must not see held-out answers, alter the evaluator or score thresholds during a campaign, choose post-hoc subsets, or replace failed records with a more favorable run.

The independent replication must be run by an organization different from the primary operator. A different cloud model, a second account, or a different person under the same organization is not an independent organizational replication.

## Campaign protocol

### 1. Freeze the identity before the first run

Create a campaign envelope before task execution and record all of the following:

- claim ID, claim-contract version, and evaluation-manifest digest;
- full source revision and artifact digests for the exact runner and evaluator;
- model/provider identity, runtime configuration, tool policy, permissions, hardware/operating-system facts, and resource budget;
- sealed-suite custody statement, evaluator organization, and operator organization;
- the planned three-run sequence and the independent replication requirement.

If an identity, policy, evaluator, held-out suite, or environment material to a gate changes, stop the campaign and create a new envelope. Do not merge records across frozen configurations.

### 2. Run three primary sealed evaluations

For each primary run, retain a complete immutable record with a unique run ID and consecutive sequence number `1`, `2`, then `3`. Capture timestamps, frozen-identity values, budget/resource measurements, task-level evidence, gate outcomes, recovery/rollback evidence where applicable, and the evaluator's final decision.

A run is not eligible merely because it completes. Missing provenance, a fallback route, identity drift, leaked held-out material, incomplete gate evidence, a critical incident, or unverifiable records must remain incomplete or failed.

### 3. Obtain the independent organizational replication

Give the external organization the frozen campaign envelope and this brief, but not held-out answers or an operator-authored favorable receipt. The external organization must run and attest to its own replication, identify itself, mark the replication as independent, and preserve equivalent provenance, gate, budget, and incident evidence.

### 4. Produce the qualification receipt

Use the claim contract's official receipt format and evaluator. At a minimum, the receipt must bind:

- `schema_version`, `claim_id`, `claim_version`, and `manifest_digest`;
- `operator_organization` and a `campaign` object;
- `primary_runs` with three or more consecutive, unique primary run records;
- `independent_replications` with at least one record marked independent and attributed to a different organization;
- frozen identity, provenance, gate results, and reproducible evidence references for every submitted run.

The official evaluator is intentionally fail-closed: absent, stale, tampered, incomparable, leaked, fallback-routed, or self-authenticated evidence cannot pass a gate. A completed JSON document is not a qualification receipt unless that evaluator accepts it.

## Stop and reject conditions

Stop the campaign and preserve the negative result when any of these occur:

- an evaluator, policy, or held-out suite changes during the campaign;
- an operator can access held-out answers or edit evaluator-owned scoring data;
- a required record, digest, signature, resource measurement, or incident trail is missing;
- a run changes model/provider/configuration identity without starting a new campaign;
- an evaluator finds a critical safety, governance, or recovery failure;
- the proposed replication is not independently operated.

Do not repair a failed run by deleting it, changing the threshold, or submitting only favorable sub-runs. Start a newly frozen campaign instead.

## Deliverables for the external organization

1. Frozen campaign envelope and custody statement.
2. The exact claim contract and evaluation manifest listed below.
3. Three immutable primary-run records with consecutive sequence numbers.
4. One independently operated replication record.
5. A machine-readable qualification receipt evaluated by the official fail-closed evaluator.
6. A short variance/incident report, including all failed, incomplete, and rejected evidence.

## Canonical local references

- `AUTONOMOUS_AGI_CLAIM.md` — target definition, eligibility rule, and authority boundary.
- `data/autonomous-agi-evaluation-manifest.json` — versioned A23 evaluation manifest.
- `backend/agi_evaluation.py` — official fail-closed evaluation logic.
- `backend/agi_api.py` — read-only A23 status surface and screening boundary.
- `data/autonomous-improvement-policy.json` — guarded self-improvement policy.
- `backend/improvement_governor.py` — append-only improvement lineage; this is not a promotion path.

## Acceptance condition

Only the official evaluator may report an A23-eligible receipt, and only after every declared gate passes across the three sealed primary runs and an independently operated organizational replication. Until then, report Obus as A2 and retain every negative or incomplete result as evidence.
