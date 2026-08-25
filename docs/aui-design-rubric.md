# OBus Hermetic Atelier AUI Design Rubric

## Purpose

This rubric is the release contract for the Hermetic Atelier AUI. It exists to prevent a subjective or self-awarded “9.9” claim. A candidate passes only when deterministic geometry evidence, automated tests, source/package smoke checks, and independent reviewers all agree.

The score is reported to two decimals with **no rounding up**. A measured `9.89` remains `9.89`, not `9.90`.

## Baseline and preservation boundary

Baseline HEAD at rubric creation: `2cce885`.

The worktree is shared and OBus Cron may commit or push concurrently. Before every edit, re-read the target and compare `git status --short`. Do not reset, stash, or overwrite unrelated work. Baseline exclusions include existing placeholder assets, build/dist directories, the local `skills/` tree, and `status-rtk-aft-push.md` unless a later task explicitly owns one of them.

No design score may hide a test failure, secret-safety regression, stale-process response, or unverified packaged artifact.

## Hard gates

A candidate is ineligible for a 9.90 release score when any gate fails:

1. **Zero unintended overlap** across every surface, viewport, density, and audited state.
2. **Zero clipped non-scrollable text** and zero unreadable text/image/line intersections.
3. All multiline text entry, output, transcript, code, context, and primary split panes are visibly defined, readable, adjustable, clamped, resettable, and keyboard accessible.
4. Every interactive control has a visible focus state, a semantic name, and a minimum 40×40 CSS-pixel pointer target unless it is an inline text link.
5. Reduced-motion mode disables deal, orbit, breathing, and layout animation while retaining textual/status communication.
6. Existing route, provider, runtime, Room, Forum, receipt, workspace, studio, memory, Forge, and safety operations remain functional.
7. Public AUI assets and payloads remain free of credential values, bearer tokens, private keys, and hidden chain-of-thought.
8. Source and packaged checks target the exact intended process on a fresh port.

## Weighted score

| Category | Weight | 10/10 evidence |
|---|---:|---|
| Geometry: overlap, clipping, containment | 20% | No hard-gate findings in the complete audit matrix |
| Typography and readability | 12% | Contrast, hierarchy, line length, labels, wrapping, and warm text texture pass |
| Golden-ratio composition | 10% | Default major splits use φ intentionally and remain user-adjustable |
| Spacing and alignment | 10% | Tokenized spacing, aligned baselines, and consistent vertical rhythm |
| Responsive behavior | 12% | Every surface remains usable at all required widths and densities |
| Accessibility and input ergonomics | 12% | Keyboard, focus, landmarks, live regions, motion, targets, and separators pass |
| Adjustability and workflow power | 10% | Persistent splitters, resize/reset/presets, block actions, and context inspection work |
| Original visual identity | 8% | Recognizably OBus/Hermetic Atelier; neither a Warp clone nor a generic AI dashboard |
| Interaction polish | 3% | Complete hover/pressed/loading/error states, bounded motion, and no layout shift |
| Stability and performance | 3% | Full tests, syntax, startup/render, observers, and listeners remain clean |

Weights total 100%.

For category score `s_i` and integer weight `w_i`, compute:

`weighted_mean = sum(s_i * w_i) / 100`

Release threshold:

- weighted mean `>= 9.90`;
- every hard gate passes;
- no subjective category is below `9.7`;
- at least two fresh visual-design scores are present;
- reviewer variance is reported rather than discarded.

## Operational surface matrix

Audit every surface below in the default state, a populated state, a long-content state, and its relevant empty/error state:

1. Run
2. Cards & Keys
3. Agents
4. Runtime
5. Rooms
6. Receipts
7. Visual Studio
8. Routing
9. Memory
10. Setup

Where available, also inspect Plan, Forums, Arcana Forge, Tentacle Worm safety, workspace context, command palette, dialogs, tooltips, and agent-context inspection.

## Viewport and density matrix

Widths:

- 390px phone
- 720px narrow/tablet boundary
- 1024px compact desktop
- 1440px standard desktop
- 1920px wide desktop

Densities:

- compact
- comfortable
- spacious

Motion modes:

- normal
- `prefers-reduced-motion: reduce`

Default wide-screen composition should target φ (`1.61803398875`) for major primary/secondary splits. Use φ as a compositional guide, not a reason to violate minimum widths, text measure, touch targets, or user-adjusted layouts.

## Geometry rules

Report unintended overlap when unrelated visible siblings intersect by more than one CSS pixel. Do not report:

- normal parent/child containment;
- closed dialogs or hidden pages;
- a visible popover, modal backdrop, tooltip, or menu intentionally layered above content;
- text inside its own button, label, badge, card, or field;
- content inside a declared scroll container.

Intentional overlays must be named in the audit allowlist with a reason. A selector may not be exempted only to improve the score.

Flag:

- horizontal document overflow;
- text where `scrollWidth > clientWidth + 1` or `scrollHeight > clientHeight + 1` without an explicit scroll/resize contract;
- broken, zero-size, or distorted images;
- text intersecting an image/line outside its owning container;
- action rows escaping their cards;
- controls below the target size;
- splitters missing valid ARIA orientation/min/max/current values;
- default split ratios outside documented φ tolerance.

## Readability and text-surface rules

Every multiline surface must have:

- an accessible label or labelled region;
- visible boundary and focus treatment;
- `overflow:auto` and stable scrollbars;
- a sensible minimum and maximum block size;
- vertical or two-axis resizing where compatible with its parent splitter;
- a visible reset affordance for persistent sizes;
- line-height of at least 1.45 for reading text;
- safe wrapping for provider/model IDs, paths, URLs, and receipt hashes.

Single-line fields stay single-line but require clear labels, placeholders that are not the sole label, helper/error placement, focus visibility, and safe overflow.

## Review roles

Each scored candidate requires fresh contexts:

- **spec reviewer** — checks every explicit requirement and hard gate;
- **visual-design reviewer** — scores the ten categories from contact sheets and the stated design brief;
- **accessibility/geometry reviewer** — checks overlap, clipping, focus, motion, responsive behavior, and adjustable separators;
- **code/security reviewer** — reviews only the diff, static scan, and test evidence for regressions or secret exposure.

The implementer may summarize evidence but cannot be the only scorer.

## Evidence bundle

Store untracked audit evidence under `.hermes/audits/<run-id>/`:

- stable geometry JSON;
- screenshot contact sheets or ordered PNGs;
- page/viewport/density coverage manifest;
- focused and full test output;
- JavaScript syntax output;
- source process identity and endpoint checks;
- packaged process identity and endpoint checks;
- reviewer score JSON and aggregated score JSON;
- SHA-256 hashes for the executable, final CSS/JS, and scored audit JSON.

## Improvement-loop stop conditions

Continue a measured fix loop while:

- a hard gate fails;
- weighted mean is below 9.90;
- any category is below 9.7;
- reviewer evidence is incomplete;
- source/package verification is stale or points at the wrong process.

Stop successfully only when every threshold passes. If the turn budget or a real tool/environment blocker prevents success, report the measured score and blocker. Never fabricate screenshots, geometry results, reviewer agreement, or a 9.9 score.
