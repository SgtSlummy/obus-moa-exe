# Guided Ritual design QA

## Comparison target

- Source visual truth: `C:\Users\Hermes\.codex\generated_images\01a03f3d-b7c3-77f1-8c38-125113bee3d9\exec-07011e10-7f02-4486-a7df-a7141cd54b66.png`
- Source pixels: 1487 × 1058.
- Implementation: `.hermes/audits/guided-ritual/home-idle-status-1440x1024.jpg`
- Implementation pixels and CSS viewport: 1440 × 1024 at density 1.
- Full-view comparison: `.hermes/audits/guided-ritual/comparison-status-restored-final.jpg`
- Normalization: the source was content-fit to 1440 × 1024 for the side-by-side comparison; the implementation was captured at that same viewport.
- State: Home, idle, empty prompt. The source depicts a populated prompt and running task; this is intentionally not reproduced because submitting a live task would change the local workspace.

## Findings

- No actionable P0, P1, or P2 findings.
- Intentional deviation: the source greeting and large main question are removed at the user’s request. The prompt is now the first interactive element.
- Intentional idle-state deviation: the running transcript is replaced by a compact “No task running” state until Begin is selected. This prevents controls and agent detail from overwhelming a first-time user.
- P3 follow-up: when an actual route is running, capture that live state and compare its task stages against the running-state portion of the source direction.

## Fidelity review

- Fonts and typography: passed. Editorial display text remains reserved for the brand, section headings, and empty-state title; controls use the compact interface face with readable weights.
- Spacing and layout rhythm: passed. The composer remains the primary element; the activity card, status rail, and advanced disclosure use deliberate vertical separation and consistent radii.
- Colors and visual tokens: passed. The dark ink surface, parchment text, brass primary action, and verdigris readiness accents follow the selected direction.
- Image quality and assets: passed. The existing OBus emblem is retained; no source visual asset was replaced by a code-drawn approximation.
- Copy and content: passed. Visible language is plain and task-oriented; occult terminology stays in the identity and advanced capabilities rather than blocking first use.

## Interaction and responsive checks

- Begin is enabled.
- Advanced routing opens and exposes the model selector.
- Workspace navigation opens the dedicated bounded-workspace screen.
- Tasks, Workspace, Memory, and Settings were visually checked after the primary-screen redesign.
- The 390 × 844 compact layout was captured and kept the prompt, Begin action, activity state, and advanced disclosure usable.
- Browser console errors and warnings: none.
- Automated contracts: 16 passed. JavaScript syntax check passed.

## Comparison history

- Earlier implementation placed the old Home heading before the composer and showed empty agent internals at idle. The heading was removed and the internals became a compact idle card.
- The right rail was temporarily empty after simplification. A concise live-status panel was restored, with values mirrored from the local model, workspace, helper, and route state.
- Post-fix evidence: `.hermes/audits/guided-ritual/home-idle-status-1440x1024.jpg` and `.hermes/audits/guided-ritual/comparison-status-restored-final.jpg`.

## Implementation checklist

- [x] Keep the Home prompt first.
- [x] Keep the running-state context visible without expanding advanced controls.
- [x] Keep Terminal reachable for experienced users.
- [x] Verify desktop and compact layouts.

final result: passed
