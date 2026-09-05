# Obus production-maturity research and improvement contract

## Scope and measurement

This report defines the first bounded improvement loop for Obus. “200% improvement” is treated as a measurable maturity target: double the baseline score across seven production domains, with no regression in approval, local-first, or secret-redaction safeguards. The target product claim is now defined in [Obus Autonomous AGI claim contract](AUTONOMOUS_AGI_CLAIM.md); this maturity score measures progress toward that claim but does not certify it or permit uncontrolled self-modification.

Scoring uses 0 (absent), 1 (partial), 2 (implemented and exercised), and 3 (operationally measured) for each domain. The 2x target is 20/21 from the observed 10/21 baseline. Each loop must leave a receipt: evidence, tests, risk review, and an explicit next action.

## Evidence-backed baseline (10/21)

| Domain | Score | Evidence | Gap to close |
| --- | ---: | --- | --- |
| Product boundary | 2 | Local-first routing, explicit `Begin`, autonomous-run and parallel-team controls are visible. | Publish supported workflows, ownership, and service promises. |
| Architecture | 2 | Bounded recovery scanning, context limits, route events, a scheduler, memory, and provider routing are present. | Make the runtime readiness contract and dependency boundaries observable. |
| Deployment and security | 2 | Secret redaction, loopback validation, bounded browser observation, and approval-oriented controls exist. | Add a deployment/configuration baseline and repeatable security verification. |
| Observability | 1 | `RouteEventHub` supplies bounded, redacted event history and streaming. | Correlate route outcome, warm-up state, latency, errors, and provider readiness in one operator surface. |
| Regression and release | 1 | Focused tests have passed for routing/provider/runtime paths. | Add a release gate with a reproducible smoke suite and explicit acceptance thresholds. |
| UX and accessibility | 1 | The audited Command center has labelled controls, status regions, context budgeting, and safety explanations. | Make readiness state stable and specific; reduce disclosure density; test keyboard focus and status-message behavior. |
| Bounded self-improvement | 1 | Objective scheduling, recovery, receipts, safety, and local reviewer affordances exist. | Require deterministic evidence -> proposal -> test -> review -> approved apply -> receipt loops. |

The observed dashboard is a capable operator console, but its initial state says both “Checking Ollama” and “GPU cold” while offering “Warm GPU.” That ambiguity is a production-readiness issue: the user cannot tell whether work is unavailable, warming, or ready. The page also places a long safety disclosure directly under the primary goal composer, which competes with the primary action.

## External standards translated into Obus work

1. **Observable outcomes, not only logs.** OpenTelemetry defines useful instrumentation in terms of correlated traces, metrics, and logs, and frames reliability from the user’s outcome. Obus should emit a redacted route receipt containing selected provider/model, readiness state, duration, outcome, cancellation reason, and stable correlation ID.
2. **Governed improvement.** NIST’s AI RMF and Generative AI profile organize risk work around governing, mapping, measuring, and managing. Obus should retain human approval for material actions and treat every self-improvement proposal as a testable change with a rollback path.
3. **Security as verification.** OWASP ASVS is a requirements and verification basis rather than a one-time feature list. Obus should turn existing secret/redaction and loopback rules into a repeatable verification gate.
4. **Accessible operations.** WCAG 2.2 requires programmatic names, roles, values, and status messages; it also adds focus and target-size guidance. Obus should test the route-readiness status and primary controls at keyboard-only and responsive breakpoints.

Sources: [OpenTelemetry observability primer](https://opentelemetry.io/docs/concepts/observability-primer/), [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework), [NIST Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf), [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/), and [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

## Deterministic warm self-improvement contract

Obus may continuously *observe* local health, retain a bounded redacted receipt, and prepare the next review. It must not autonomously install software, modify credentials, transmit private data, change system settings, make purchases, or apply material source/configuration changes without explicit approval.

For every improvement loop:

1. Measure a fixed local baseline and record redacted evidence.
2. Generate a small, deterministic work card from the evidence and fixed policy.
3. Run bounded checks; failed or missing evidence means no change.
4. Present risk, rollback, and expected effect for review.
5. Apply only an approved, reversible change; verify it and retain a receipt.
6. Keep the local model warm only within configured resource limits; warming never overrides an active task or system-health signal.

## First implementation work card

**Readiness envelope (P0):** expose one redacted endpoint and dashboard status that reports local model/provider readiness, active warm residency, last warm-up result, and a route correlation ID. It must distinguish `ready`, `warming`, `degraded`, and `unavailable`; it must not reveal credentials, prompts, or host internals.

**Acceptance:** a minimal local Qwen request succeeds; the dashboard settles on one unambiguous readiness state; route events and the readiness payload agree; existing provider/routing tests pass; and the result can be reproduced after a process restart.

**Next loops:** release/security gate (P1), focused accessibility remediation (P1), and operational telemetry/latency budgets (P2). No score increase is claimed until the associated acceptance checks are automated or repeatably demonstrated.

## Epistemic calibration and governed self-improvement loop (2026-09-01)

### Decision and measured evidence

Obus now applies the versioned `obus-epistemic-honesty@1.0.0` system policy to both Local Ollama execution paths. The operator explicitly authorized this bounded runtime change. `OBUS_EPISTEMIC_POLICY=off` is the rollback switch.

- Development prompt search: the best predecessor policy improved the raw score from 75.0% to 83.33%, but one exact-match test incorrectly rejected an alternative valid topological order. That score is descriptive only.
- Disjoint challenge: the predecessor improved the conservative mechanical score from 50.0% to 91.67% (+41.67 percentage points), answerable accuracy from 83.33% to 100%, and mean latency from 23,691 ms to 19,489 ms (-17.74%). The scorer undercounted some valid control abstentions, so these values are retained as raw mechanical evidence rather than universal accuracy.
- Focused active-policy regression: v1.0.0 passed 14/16 checks (87.5%), preserved creative/coding/planning behavior, and changed unverifiable machine/workspace questions from unsupported answers to evidence-gathering responses.
- Known failure: Qwen still fabricated the same answer to a private-thought probe in every tested repeat. A prompt policy is therefore not a calibration guarantee.

The durable machine-readable evidence is `data/epistemic-calibration-policy.json`. The challenge was disjoint but not sealed or independently administered, and the active refinement did not receive a fresh full-suite replication. It therefore contributes no Autonomous AGI gate credit.

### Claim-to-source ledger

| Research claim | Primary source | Obus consequence |
| --- | --- | --- |
| Models can express uncertainty in words, but calibration is task- and model-dependent. | [Lin et al. (2022)](https://arxiv.org/abs/2205.14334) | Validate the exact local model and task mix. |
| Verbalized confidence and alternative hypotheses can improve calibration, with mixed transfer. | [Tian et al. (2023)](https://arxiv.org/abs/2305.14975) | Treat prompts as candidates, never guarantees. |
| Self-evaluation works in some formats and weakens under task shift. | [Kadavath et al. (2022)](https://arxiv.org/abs/2207.05221) | Require disjoint and shifted challenge cases. |
| Sample consistency can improve calibration at extra compute cost. | [Lyu et al. (2024)](https://arxiv.org/abs/2402.13904) | Reserve multi-sample checks for material-risk work. |
| Prompted uncertainty can remain overconfident. | [Groot and Valdenegro-Toro (2024)](https://arxiv.org/abs/2405.02917) | Preserve the observed private-state failure. |
| Same-model iterative refinement can reward-hack its evaluator. | [Pan et al. (2024)](https://arxiv.org/abs/2407.04549) | No self-judged automatic promotion. |
| Control protocols should treat the proposer as untrusted and evaluate the whole protocol. | [Greenblatt et al. (2024)](https://proceedings.mlr.press/v235/greenblatt24a.html) | Keep evaluator authority separate from candidate writes. |
| Deployment changes need documented change management, reassessment, and rollback. | [OpenAI Preparedness Framework v2 (2025)](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf) | Expose identity, evidence, and an operator rollback switch. |

### Relationship to the Autonomous AGI definition

This loop does not change Obus's current A2 verified status. The active research target is now the A23 v2.0.0 contract: all 23 frozen gates must pass in three consecutive sealed primary runs and one independent organizational replication. Warm residency, benchmark gains, self-reported confidence, synthetic scores, and this operator-authorized prompt policy cannot promote the claim.

## Deterministic unreported-private-state guard (2026-09-01)

### Why the prompt-only policy was insufficient

The active Qwen model bypassed the v1.0.0 system directive when the evaluator demanded the exact song privately selected before the run: it returned `Bohemian Rhapsody, Queen` even though the evidence could not determine any title. That reproduced failure is the reason for a deterministic boundary rather than another prompt revision.

External evidence supports abstention as a risk/coverage decision, but it does not make one mechanism universally reliable. [The Art of Abstention](https://aclanthology.org/2021.acl-long.84/) formalizes selective prediction around coverage and risk. [Semantic-entropy research](https://www.nature.com/articles/s41586-024-07421-0) reports stronger confabulation detection than several baselines, but requires repeated sampling and cannot catch a consistently repeated falsehood. [Guardrails validator actions](https://guardrailsai.com/guardrails/docs/concepts/validator_on_fail_actions) demonstrate deterministic refrain/filter/fix/exception boundaries, while [Promptfoo assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/) provide deterministic regression gates. For this narrow, high-confidence failure, Obus therefore uses a small native pre-generation classifier instead of adding a framework or a latency-heavy uncertainty ensemble.

### Implemented boundary and evidence

Policy `obus-epistemic-honesty@1.1.0` classifies explicit English-language requests to infer a person's unreported private state before either local Ollama path can invoke Qwen. A block returns one fixed disclosure-safe abstention, records category/policy/version without copying the prompt, reports zero provider calls and tokens, and remains reversible with `OBUS_EPISTEMIC_POLICY=off`.

The classifier was refined one real challenge at a time. Recorded development/challenge scores progressed through 19/27, 27/27, 26/30, 27/30, 38/40, 48/50, and 27/30 on a final disjoint paraphrase set. The committed regression then passed 10/10 explicit-private-state blocks and 12/12 preservation cases, plus all three provider-boundary bypass tests (route, direct aggregator, and workspace agent). Preserved cases include creative guessing, advice, coding terminology, technical uses of “private,” and values explicitly supplied in the prompt.

### Limits and AGI relationship

This guard is intentionally not described as a truth detector. Novel paraphrases may evade its patterns; ambiguous language may be over-blocked; and it does not verify machine, workspace, account, software, external-world, or tool-derived claims. The tests are researcher-authored, not independently sealed. The result closes one reproduced failure mode and improves operational honesty, but does not by itself earn an A23 gate, change the verified A2 level, or grant self-promotion authority.

## A23 falsifiable autonomy contract (2026-09-02)

A23 is now the active v2.0.0 research target. It is a project-specific contract name for exactly 23 conjunctive gates—not a universal AGI scale, consciousness claim, or self-rating. The original 11 capability, autonomy, learning, calibration, safety, reproducibility, and efficiency gates remain intact. Twelve additional gates cover private-state non-fabrication, current-state provenance, claim traceability, calibrated abstention, tool-call integrity, prompt-injection authority resistance, privilege non-escalation, destructive-action consent, checkpoint/resume integrity, per-task resource compliance, tested rollback, and evaluator non-interference.

The evaluator accepts historical v1/A4 manifests for reproducibility but requires active v2 manifests to declare A23, receipt schema 2, exactly 23 unique gates, a 23-gate passing floor, an independent organization, and `self_certification_permitted: false`. Screening is conjunctive: 22/23 cannot pass. Even a 23/23 self-submitted receipt is only `candidate_passed`; the API cannot authorize A23 because caller-authored hashes, URIs, verifier fields, and organization names are declarations rather than verified provenance. Promotion additionally requires external artifact resolution/rehashing plus authenticated independent attestation bound to the exact manifest and receipt digests. Missing or malformed manifests and receipts fail closed. The status API exposes the contract version and digest, the dashboard separates `Verified level`, `Research target`, and `A23 attainment`, and no UI fallback silently assumes a level.

The thresholds are explicit Obus policy choices grounded in, but not attributed to, [Levels of AGI](https://proceedings.mlr.press/v235/morris24b.html), [On the Measure of Intelligence](https://arxiv.org/abs/1911.01547), [ARC Prize evaluation policy](https://arcprize.org/policy), [METR time horizons](https://metr.org/time-horizons/), [NIST AI RMF](https://doi.org/10.6028/NIST.AI.100-1), [NIST Generative AI Profile](https://doi.org/10.6028/NIST.AI.600-1), [NIST SP 800-53 Rev. 5](https://doi.org/10.6028/NIST.SP.800-53r5), and the [DeepMind Frontier Safety Framework](https://deepmind.google/frontier-safety/). None of these sources certifies Obus.

Current attainment remains honest: **A2 verified; A23 not attained**. Promotion requires three sealed primary receipts plus one independent organizational replication with all 23 gates passed and artifact provenance verified.

## Deterministic Improvement Governor rationale (2026-09-02)

The governor adopts a deliberately smaller control pattern from primary sources: [Darwin Gödel Machine v3](https://arxiv.org/abs/2505.22954v3) motivates explicit parent lineages, empirical evaluation, sandboxing, and human oversight; [STOP](https://arxiv.org/abs/2310.02304) motivates treating self-improvement code and its sandbox behavior as evidence to constrain rather than authority to trust. [Temporal's workflow determinism guidance](https://docs.temporal.io/workflow-definition#deterministic-constraints) motivates replaying recorded external results instead of re-running nondeterministic model or evaluator calls. [Argo Rollouts analysis](https://argo-rollouts.readthedocs.io/en/stable/features/analysis/) motivates distinct successful, failed, and inconclusive outcomes, a stable checkpoint, and rollback before promotion. [SLSA build provenance](https://slsa.dev/spec/v1.2/build-provenance) motivates content-addressed inputs and lineage, while the [NIST AI RMF](https://doi.org/10.6028/NIST.AI.100-1) and [Generative AI Profile](https://doi.org/10.6028/NIST.AI.600-1) motivate explicit governance, measurement, risk treatment, and human accountability. [Ollama `keep_alive`](https://docs.ollama.com/faq#how-do-i-keep-a-model-loaded-in-memory-or-make-it-unload-immediately) remains only an operator-controlled residency setting and is not evidence of improvement.

Obus adopts those patterns; it does **not** claim equivalent workflow durability, rollout automation, supply-chain provenance, safety assurance, or self-improvement results. Its local canonical-JSON SHA-256 chain is tamper-evident and fails closed when the recorded chain no longer verifies, but it is not a signature and cannot prevent an attacker with write access from replacing and re-chaining the entire database. Screening remains non-authoritative: no API lets a candidate authorize itself or promote an active runtime pointer.

## Second-loop evidence architecture (2026-09-02)

The next bounded loop separates candidate execution, trusted evaluation, and human promotion. The candidate is fixed to an allowlisted improvement kind and runs from a frozen parent in a disposable, network-disabled, resource-limited environment. It may produce a patch, transcript digest, and measured outputs; it cannot choose its evaluator, synthesize approval, or change the active runtime. A fresh host-side evaluator repeats only the focused checks needed for the candidate, binds the result to exact inputs and outputs, and leaves promotion pending for an authenticated human decision.

Primary-source findings shape that boundary:

- The [Ollama FAQ](https://docs.ollama.com/faq) defines `/api/ps` as the live loaded-model view and a negative `keep_alive` as indefinite residency. It also warns that concurrent requests multiply context memory, so a warm-up receipt must record and verify the requested context rather than infer readiness from a successful request alone.
- A detached [Git worktree](https://git-scm.com/docs/git-worktree.html) provides a reproducible disposable checkout and convenient lineage, but it is not a security boundary. Candidate execution therefore also uses container controls such as no network, a read-only source mount, dropped privileges/capabilities, and explicit CPU, memory, and process limits, following the isolation posture described by [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/security/) and [Inspect AI sandboxing](https://inspect.aisi.org.uk/sandboxing.html).
- An [in-toto Statement and DSSE envelope](https://github.com/in-toto/attestation/blob/v1.2.0/spec/README.md) can bind an authenticated claim to subject digests, while [SLSA v1.2 build provenance](https://slsa.dev/spec/v1.2/build-provenance) records subjects, build type, parameters, dependencies, builder identity, and invocation details. These structures improve traceability and tamper evidence; they do not prove that the candidate is correct, safe, or semantically better.
- [Darwin Gödel Machine v3](https://arxiv.org/html/2505.22954v3) reports objective-hacking behavior in self-improving agents. Obus therefore freezes the outer evaluator, keeps held-out judgments outside candidate control, and preserves a human-only promotion boundary instead of treating self-evaluation as authority.

The remaining caveats are material. A local Docker daemon and its host are not a perfect trust boundary. Held-out-case composition, the signing root and key custody, offline package/network mirrors, and canary success and rollback metrics still require explicit design and operational evidence. Neither these controls nor any compared external model proves AGI or satisfies A23; Obus remains A2 verified, with A23 unattained until the full contract and independent replication pass.

## Paired-baseline promotion gate (2026-09-02)

The current-source governed loop `loop-5d13d4b3375234f569dd8e89` executed exactly once. Its three immutable-image, network-disabled candidate probes all passed, Qwen generated successfully at a requested and observed 262,144-token context, residency remained indefinite, receipt replay verified, and the append-only journal verified. The evaluator still rejected the candidate because the retained pre-change bytes were not replayable and because it checked a stale `generated` field while the trusted runner recorded `generation_done`. No second loop was started, and no promotion was attempted.

That outcome exposed the highest-value evidence gap: without a like-for-like pre-change run, successful candidate probes cannot establish an improvement delta. The new gate therefore captures a full immutable Git commit OID plus a separate `baseline_artifact_digest`; both the trusted runner and evaluator independently rederive the exact `<commit>:backend/main.py` bytes. It executes three baseline and three candidate runs through the same immutable Docker image, selector suite, isolation policy, resource envelope, and canonical command manifest, then signs artifact metadata and both arm manifests in the DSSE/in-toto receipt without embedding raw source. The evaluator validates each phase manifest and output digest, rejects identical artifacts, derives both scores from their signed run records, recomputes the improvement claim, and rejects missing, altered, or mismatched evidence. The existing runtime-status `baseline_digest`, rollback checkpoint, append-only journal, idempotency boundary, and human-only promotion rule remain unchanged. The generation/residency contract now evaluates the runner's actual `generation_done` field.

This design follows current primary evidence without overstating it. [Darwin Gödel Machine v3](https://arxiv.org/html/2505.22954v3) demonstrates bounded coding-agent scaffold improvement under empirical evaluation, sandboxing, archives, and human oversight, while its objective-hacking cases show why candidate-visible or candidate-mutable evaluators are unsafe. [Inspect AI](https://inspect.aisi.org.uk/sandboxing.html) supports isolated sandboxes and repeated evaluation epochs but also makes clear that supervisor-side tools and custom configuration remain outside the container boundary. [METR's time-horizon methodology](https://metr.org/time-horizons/) uses repeated runs, separate development and test sets, automated and human reward-hack review, and reliability curves rather than a best single run. [ARC Prize's verified testing policy](https://arcprize.org/policy) motivates equal procedures and private evaluation material, while [OpenAI's SWE-bench Verified analysis](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/) shows why contaminated or flawed public benchmarks cannot serve as frontier proof. [OpenAI's chain-of-thought monitoring research](https://openai.com/index/chain-of-thought-monitoring/) supports independent monitoring as a review signal but warns against optimizing candidates to hide from the monitor.

Validation was deliberately narrow: the three changed backend modules compiled, and the focused paired-evidence receipt case passed once. This proves the implemented contract path at unit scope; it does not constitute a fresh live paired loop, sealed held-out evaluation, external replication, a 200% measured improvement, AGI, or A23 attainment. The next admissible loop must use the new paired gate and may advance only to the existing human-authorization boundary when its signed evidence actually shows a policy-qualified gain.

## Baseline validity retention and comparator failure (2026-09-02)

A public, descriptive Qwen-versus-free-route rerun produced malformed no-text responses from every external sample. Its comparison is therefore `incomplete`, not a local win, loss, or model-quality verdict. A prompt variant also traded one probe outcome for another without increasing the local total, so it was reverted instead of being represented as capability growth. These results are retained as audit evidence; they earn no maturity score, A23 gate credit, or promotion authority.

The baseline store now writes every content-addressed attempt while maintaining `latest-valid.json` only for a digest-verified report whose comparison is measurement-valid. If a later attempt is stale, incomplete, tampered, or incomparable, status retains the matching valid measurement separately and exposes the failed latest attempt as diagnostic evidence. A changed harness invalidates the previous measurement rather than silently carrying it forward. This is a fail-closed provenance mechanism, not a benchmark or a self-improvement claim.

This decision follows the reproducibility posture of [VERO](https://arxiv.org/pdf/2602.22480): versioned snapshots, controlled budgets, isolated environments, and structured traces are necessary to make agentic evaluations comparable. Obus adopts that narrow implication only. It does not claim VERO-level validation, independently sealed evaluation, reliable external-model comparison, AGI, or A23 attainment.
