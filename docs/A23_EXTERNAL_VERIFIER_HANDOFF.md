# A23 external-verifier handoff

## Purpose and authority boundary

This is an operator handoff for an **authorized external evaluator** running the Obus Autonomous AGI Claim Contract v2.0.0 campaign. It is planning and evidence-collection guidance only. It cannot validate a run, supply missing evidence, authorize a promotion, or change Obus's reported maturity level.

Obus may prepare, sandbox, evaluate, reject, monitor, and roll back candidate improvements. It may not alter the evaluator or held-out suite, inspect held-out answers, increase its authority, or certify its own A23 claim. Promotion remains a human and independent-evaluator decision.

## Current truthful starting point

- Current reported level: **A2 — bounded autonomous agent platform**.
- Target: **A23 — externally verified 23-gate Autonomous AGI**.
- Qualification: **not earned**; no qualification receipt is persisted.
- Required evidence: **three consecutive sealed primary runs** and **at least one independent organizational replication**.
- The local Qwen warm-runtime result and public cross-model development baseline are operational/development evidence. They cannot qualify or promote A23.
- The current public baseline found no measured local deficit. Its correct behavior is to decline an automatic improvement candidate, not create a decorative loop.

## Independence and custody

The evaluator owns the held-out task material and scoring process. Obus operators must not see held-out answers, alter evaluator-owned thresholds during a campaign, select post-hoc subsets, or replace an unfavorable record.

The independent replication must be operated by an organization different from the primary operator. A second account, cloud model, or person under the same organization is not an independent organizational replication.

Keep enough methodological information to permit independent scrutiny without releasing held-out content. Preserve all failures, incompletes, incidents, and configuration changes as first-class campaign evidence.

## Campaign protocol

### 1. Freeze the campaign identity

Before task execution, create a campaign envelope recording:

- claim ID, contract version, and evaluation-manifest digest;
- full source revision and artifact digests for the runner and evaluator;
- model/provider identity, runtime configuration, tool policy, permissions, hardware/operating-system facts, and resource budget;
- evaluator and operator organizations, suite-custody statement, and the planned three-run sequence;
- a commitment to the required independent replication.

If an identity, policy, evaluator, held-out suite, or material environment changes, stop the campaign and create a newly frozen envelope. Never merge evidence across frozen configurations.

### 2. Run the three primary sealed evaluations

Retain one immutable, uniquely identified record for each primary sequence number `1`, `2`, and `3`. Each must include timestamps, frozen identity values, resource measurements, task-level evidence, gate outcomes, recovery/rollback evidence where applicable, and the evaluator's decision.

Completion alone is not eligibility. Missing provenance, fallback routing, identity drift, held-out leakage, incomplete gate evidence, a critical incident, or unverifiable records must remain incomplete or failed.

### 3. Obtain the independent organizational replication

Give the external organization the frozen envelope and this handoff—not held-out answers and not an operator-authored favorable receipt. The organization must run and attest to its own replication, identify itself, mark it independent, and preserve comparable provenance, gate, budget, and incident evidence.

### 4. Submit only an evidence-bound receipt

Use the claim contract's official receipt format and evaluator. At minimum the receipt must bind:

- `schema_version`, `claim_id`, `claim_version`, and `manifest_digest`;
- `operator_organization` and a `campaign` object;
- `primary_runs` with three or more consecutive, unique primary records;
- `independent_replications` with at least one record marked independent and attributed to a different organization;
- frozen identity, provenance, gate results, and reproducible evidence references for every submitted run.

The official evaluator is fail-closed. Absent, stale, tampered, incomparable, leaked, fallback-routed, or self-authenticated evidence cannot pass a gate. A syntactically complete JSON document is not a qualification receipt unless that evaluator accepts it.

## Stop and reject conditions

Stop the campaign and retain its negative evidence when:

- the evaluator, policy, held-out suite, or a material configuration changes;
- an operator can access held-out answers or evaluator-owned scoring data;
- a required record, digest, signature, resource measurement, or incident trail is missing;
- the model/provider/runtime identity drifts;
- a critical safety, governance, or recovery failure occurs; or
- the replication is not independently operated.

Do not repair a failed run by deleting it, changing the threshold, or submitting only favorable sub-runs. Start a new frozen campaign instead.

## Deliverables for the external organization

1. Frozen campaign envelope and suite-custody statement.
2. The exact claim contract and evaluation manifest listed below.
3. Three immutable primary-run records with consecutive sequence numbers.
4. One independently operated replication record.
5. A machine-readable qualification receipt evaluated by the official evaluator.
6. A variance and incident report covering failed, incomplete, and rejected evidence.

## Evaluator selection and research channels

This is a **non-endorsement research shortlist**, not a statement that any organization is available, willing to evaluate Obus, or able to qualify A23. Do not share an envelope, endpoint, logs, or task material, and do not contact an organization, without explicit operator authorization.

Select an evaluator only if it can demonstrate all of the following:

- independent control of held-out tasks, scoring, and unfavorable records;
- a method that evaluates autonomous, long-horizon task execution rather than only static benchmark scores;
- reproducible configuration, provenance, incident, and resource reporting;
- a conflict-of-interest disclosure and a separate organizational identity for the replication; and
- an explicit willingness to retain failed or incomplete records and issue a machine-readable result.

Research channels worth independently checking before any authorized outreach:

- [METR's autonomous-capability evaluation resources](https://metr.org/measuring-autonomous-ai-capabilities/) describe held-out autonomy tasks and an evaluation platform. Treat this as a research contact path, not an available service or an endorsement.
- [CRUX open-world evaluations](https://cruxevals.com/) study long-horizon, real-world agent tasks with detailed log analysis. Treat this as a possible research-collaboration path, not a certification service or an A23 qualification mechanism.

If no suitable independent evaluator accepts the scope, retain that outcome as an unresolved evidence gap; do not substitute a friendly account, a cloud provider, or a self-run public benchmark for the required replication.

## Canonical references

- `AUTONOMOUS_AGI_CLAIM.md` — target definition, eligibility rule, and authority boundary.
- `data/autonomous-agi-evaluation-manifest.json` — versioned A23 evaluation manifest.
- `backend/agi_evaluation.py` — official fail-closed evaluation logic.
- `backend/agi_api.py` — A23 status and screening boundary.
- `data/autonomous-improvement-policy.json` — guarded self-improvement policy.
- [AEF-1 minimum conditions for independent third-party AI evaluations](https://aievaluatorforum.org/AEF_1_Minimum_Operating_Conditions_for_Independent_Third_Party_AI_Evaluations.pdf) — evaluator independence, access, transparency, held-out integrity, and responsible disclosure.
- [NIST AI 800-2 announcement](https://www.nist.gov/news-events/news/2026/01/towards-best-practices-automated-benchmark-evaluations) — benchmark objectives, execution, analysis, and reporting practices.

## Acceptance condition

Only the official evaluator may report an A23-eligible receipt, and only after every declared gate passes across three sealed primary runs and an independently operated organizational replication. Until then, report Obus as A2 and retain negative or incomplete results as evidence.
