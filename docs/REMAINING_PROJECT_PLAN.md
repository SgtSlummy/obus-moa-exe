# Remaining project plan — Obus

Status date: **2026-09-03**

## Where the project is now

The review and repair pass is complete. The Python suite, browser-module tests, focused runtime checks, and local backend restart have all been validated.

The current verified capability position is **A2 — bounded autonomous agent platform**. The longer-term project target is **A23-verified Autonomous AGI**.

## Remaining work

### 1. Prepare the A23 evaluation campaign

Create the campaign package for the next qualification effort: the evaluation plan, run ledger, artifact map, system snapshot, and preflight materials.

**Deliverables:** campaign package, frozen evaluation inputs, and preflight report.

### 2. Run the primary evaluation campaigns

Execute and collect the three primary evaluation runs. Consolidate the resulting transcripts, metrics, incident records, resource reports, and evaluation receipts.

**Deliverables:** primary-run evidence set and scored evaluation report.

### 3. Complete independent replication

Arrange an independent organizational replication of the evaluation and gather its verifier report and final decision.

**Deliverables:** independent-replication evidence and external verifier decision.

### 4. Finish engineering release readiness

Complete the remaining product-quality work: reproducible coverage reporting, critical-path test mapping, packaged desktop/backend acceptance checks, and release evidence.

**Deliverables:** coverage report, critical-path test inventory, packaged-product acceptance report, and updated release materials.

### 5. Consolidate evidence and prepare the next release decision

Bring the evaluation and engineering evidence together into one release/claim packet. Update public status materials only to reflect the evidence that exists at that point.

**Deliverables:** consolidated evidence packet, status summary, release decision record, and rollback/recovery notes.

## Suggested sequence

| Workstream | Starts after | Can proceed alongside |
| --- | --- | --- |
| Campaign preparation | Now | Engineering release readiness |
| Primary evaluation runs | Campaign preparation | Engineering release readiness |
| Independent replication | Primary evaluation runs | Engineering release readiness |
| Engineering release readiness | Now | All evaluation workstreams |
| Evidence consolidation and release decision | Evaluation and release work are complete | — |

## Immediate next focus

Begin the evaluation-campaign preparation and engineering release-readiness tracks. The primary runs and replication follow as their input materials become available.

## Reference material

- `AUTONOMOUS_AGI_CLAIM.md`
- `data/autonomous-agi-evaluation-manifest.json`
- `backend/agi_evaluation.py`
- `INDEPENDENT_EVALUATION_REQUEST.md`
- `docs/release.md`
- `.github/workflows/release.yml`
