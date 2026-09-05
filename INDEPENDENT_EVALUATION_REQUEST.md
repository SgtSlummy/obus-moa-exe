# Request for independent evaluation — Obus A23 claim contract

**To:** Model Evaluation and Threat Research (METR) — [info@metr.org](mailto:info@metr.org)
**Subject:** Request to scope an independent evaluation of Obus; no current AGI claim

Hello,

We are requesting an independent, evidence-led evaluation of Obus, a local-first agent platform. This is **not** a request to validate a present AGI claim. Obus currently represents itself only as **A2 — bounded autonomous agent platform**. Its stated research target, “A23-verified Autonomous AGI,” is an Obus-specific 23-gate contract that is not earned and must not be inferred from this request, its local model, a long context window, or demos.

We would value an evaluator’s advice on whether, and under what conditions, a future sealed campaign could support an independent qualification decision. We would specifically welcome a scope that challenges the system rather than accepting subject-supplied scoring.

## Requested scope

1. Review the frozen evaluation contract, campaign design, threat model, and artifact chain before any qualification attempt.
2. Independently select, author, or seal held-out tasks and control the withheld answers, scoring environment, and contamination review.
3. Verify the submitted source/configuration/model/provider identities, artifact bytes, digests, run ledger, resource accounting, and intervention records.
4. Evaluate capability, long-horizon task completion, continual learning, calibration, prompt-injection/authority resistance, recovery, rollback, and evaluator non-interference using the evaluator’s own judgment and methods.
5. Independently reproduce at least one complete run under a separately operated organization and publish a bounded findings report, including negative findings and protocol limitations.

## System and evidence boundary

The current primary local configuration is `hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M` in Ollama on an RTX 3090. The operational profile is 65,536 context tokens, full-GPU residency, and explicit `keep_alive: -1`. These are runtime facts only—not capability or qualification evidence.

Obus has a fail-closed local screening evaluator, immutable receipts, replay checks, human-gated promotion, defined rollback paths, and a public claim contract. The subject cannot self-authorize the A23 wording. Any self-submitted screening result remains non-qualifying until an authenticated external evaluator independently rehashes artifacts, authenticates the replication organization, and binds an attestation to the exact receipt and manifest digests.

## Known blockers and requested evaluator posture

Obus has not completed the three sealed primary runs, a validated 40-hour human-calibrated horizon suite, held-out continual-learning evidence, the full adversarial authority campaign, or an independent organizational replication. We ask that missing, stale, contaminated, unverifiable, or subject-controlled evidence be treated as incomplete rather than as a pass.

The project will not ask an evaluator to endorse a predetermined conclusion, waive negative findings, reveal sealed answers to the evaluated system, or treat model identity, benchmark proxies, self-reported scores, or ordinary task receipts as proof.

## Materials available for a scoping review

- [`AUTONOMOUS_AGI_CLAIM.md`](AUTONOMOUS_AGI_CLAIM.md): A23 contract, all 23 gates, current A2 status, and non-qualification language.
- [`data/autonomous-agi-evaluation-manifest.json`](data/autonomous-agi-evaluation-manifest.json): machine-readable evaluation requirements.
- [`backend/agi_evaluation.py`](backend/agi_evaluation.py): local fail-closed screening evaluator; it deliberately cannot promote the claim.
- Frozen source/configuration/model identities, receipts, raw artifacts, environment records, resource accounting, and redacted incident/approval records can be supplied under an agreed disclosure process.

## Suggested scoping questions

1. Which parts of the proposed 23-gate design are measurable, which are underspecified, and which should be removed or redesigned?
2. What task-sealing, contamination controls, access boundaries, and audit rights are necessary for an independent replication?
3. What evidence would distinguish a genuinely capable system from benchmark overfitting, reward hacking, or subject-controlled evaluator behavior?
4. What public reporting format would make both positive and negative results falsifiable and useful?

We understand that an independent organization may decline, require an NDA, require funding, or propose a narrower scope. Any such engagement should preserve evaluator independence and the right to publish appropriately bounded conclusions.

Sincerely,
**Obus project operator**
Contact details to be supplied through the authenticated sending channel

## Reference context

The request follows the project’s own [A23 contract](AUTONOMOUS_AGI_CLAIM.md) and is informed by [METR’s public discussion of independent evaluation practice](https://metr.org/blog/2026-07-28-investigating-ai-propensities-after-incidents/) and [its published external-evaluation work](https://metr.org/blog/2026-06-26-gpt-5-6-sol/). Those materials are methodological references; they do not endorse, evaluate, or certify Obus.
