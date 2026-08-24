# Warp-Inspired OBus AUI Upgrade Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Upgrade OBus into a responsive, keyboard-first, accessible, information-dense local AI workbench modeled on the useful interaction patterns of WarpUI while preserving OBus's Tarot, Solomon's Keys, MOA, Rooms, Forums, memory, safety, and local-first runtime functions.

**Architecture:** Keep the existing FastAPI backend and local static web application, but replace the current monolithic UI behavior with a versioned AUI contract, modular frontend assets, a command/action registry, responsive workbench layout, and live runtime event surfaces. Warp will be treated as an architectural and ergonomic reference—not copied or embedded—and OBus identity, privacy boundaries, and local-first routing remain authoritative.

**Tech Stack:** FastAPI, Python, existing JSON state/runtime modules, HTML/CSS/vanilla JavaScript modules, vendored Warp Rust source for reference, Node syntax checks, pytest/TestClient, PyInstaller packaging verification, browser/native UI smoke checks.

---

## Current Context and Assumptions

- Warp source is vendored under `third_party/warpdotdev-warp/`.
- Relevant Warp references include:
  - `crates/warpui_core/src/core/app.rs` for app/view/action lifecycle.
  - `crates/warpui_core/src/actions.rs` for action vocabulary.
  - `crates/warpui_core/src/accessibility.rs` for value/role/help announcements.
  - `crates/warpui_core/src/keymap*` for keyboard binding precedence and discoverability.
- OBus currently uses:
  - `backend/main.py` as a large FastAPI application.
  - `backend/static/index.html` as a large inline SPA.
  - Existing pages for routing, Keys, agents, runtime jobs, Rooms, Forums, receipts, studios, Forge, memory, safety, and settings.
  - Existing `backend/aui.py` and `/api/aui/manifest` as the first AUI contract layer.
- Do not embed Warp's proprietary/AGPL application behavior into OBus. Preserve the existing optional companion boundary in `backend/warp_companion.py`.
- Do not add provider secrets, tokens, OAuth values, private keys, or credential input fields.
- Do not commit or package until the user explicitly requests that step.

## Research Deliverable

Create a research note before visual implementation using `agent-reach` for current public references and the vendored source for local evidence. Compare Warp, Raycast, Linear, Ollama, Superhuman, and terminal-native interfaces. Capture only actionable patterns:

- block-based command history and result grouping;
- keyboard-first command discovery;
- focus restoration and modal behavior;
- sidebar/workspace navigation;
- responsive pane collapse and density controls;
- accessible live announcements;
- status, progress, cancellation, and error presentation;
- information-dense but calm dark-mode visual systems.

Record URLs, license notes, screenshots or textual observations, and which patterns are adopted, rejected, or adapted for OBus. Do not copy brand assets or proprietary code.

---

## Phase 1: Contract and Information Architecture

### Task 1: Freeze the current baseline

**Objective:** Establish a reproducible baseline before changing UI behavior.

**Files:**
- Read: `backend/main.py`
- Read: `backend/aui.py`
- Read: `backend/static/index.html`
- Read: `tests/`

**Steps:**
1. Run `pytest -q tests` and record failures that predate this work.
2. Run the existing focused UI tests.
3. Extract the inline script and run `node --check`.
4. Record the current routes, page IDs, controls, and API calls in the research note.

**Validation:** Baseline failures are documented and not misreported as regressions.

### Task 2: Define the canonical AUI information architecture

**Objective:** Establish the stable workspace model before restyling individual screens.

**Files:**
- Modify: `backend/aui.py`
- Test: `tests/test_aui_contract.py`

**Structure:**
- Run: prompt composer, active route blocks, live stages, cancellation, output handoff.
- Sessions: history, receipts, bookmarks, retry, export, compare.
- Agents: Tarot persona catalog, persistent agents, runtime events.
- Councils: Rooms, Chymeria packets, Forums.
- Providers: Solomon's Keys, readiness, context windows, capability filters.
- Context: workspace tree/file/diff, memory, graph context.
- Studios: ComfyUI, Understand Anything, Warp companion status.
- Safety: Tentacle Worms, verification, audit history.
- Settings: surface, density, theme, keyboard shortcuts, routing policy, accessibility.

Add stable IDs, surface minimums, roles, shortcuts, descriptions, and action targets to the manifest. Test Terminal < Operator < ADE visibility and reject unknown surfaces safely.

### Task 3: Map every visible control to a real function

**Objective:** Ensure no polished control is a dead button or placeholder.

**Files:**
- Create or modify: `backend/aui.py`
- Modify: `backend/main.py`
- Test: `tests/test_aui_control_map.py`

**Steps:**
1. Enumerate each action with `action_id`, label, shortcut, target, required API, and expected state change.
2. Map route execution, cancellation, refresh, navigation, receipts, agent jobs, room runs, provider probes, workspace selection, memory, studios, and safety controls.
3. Add an endpoint returning the action/control contract without secrets.
4. Test that every manifest action has either a known frontend handler or an explicit unavailable state.

---

## Phase 2: Frontend Foundation and Visual System

### Task 4: Extract design tokens

**Objective:** Replace scattered inline color/layout values with a maintainable design system.

**Files:**
- Create: `backend/static/aui/tokens.css`
- Create: `backend/static/aui/components.css`
- Modify: `backend/static/index.html`
- Test: `tests/test_aui_visual_contract.py`

**Design direction:** Combine Warp's terminal/block model with Linear/Raycast precision and Ollama/OpenCode terminal restraint. Define tokens for background layers, borders, semantic status colors, Tarot accents, spacing, radii, typography, density, focus rings, motion, and reduced-motion behavior.

Use CSS custom properties and semantic names. Preserve the occult identity through original Tarot/Key imagery and restrained sigil accents rather than adding decorative clutter.

### Task 5: Add modular frontend bootstrap

**Objective:** Reduce the risk of the 140KB-plus inline script becoming unmaintainable.

**Files:**
- Create: `backend/static/aui/app.js`
- Create: `backend/static/aui/api.js`
- Create: `backend/static/aui/state.js`
- Create: `backend/static/aui/actions.js`
- Create: `backend/static/aui/announcements.js`
- Modify: `backend/static/index.html`

Move only shared AUI behavior first: API wrapper, state store, action dispatch, focus restoration, announcements, and manifest loading. Leave feature-specific functions in place until their tests and boundaries are stable.

### Task 6: Implement the responsive workbench shell

**Objective:** Make the UI usable from narrow laptop windows through wide desktop displays.

**Files:**
- Modify: `backend/static/aui/components.css`
- Modify: `backend/static/index.html`
- Test: `tests/test_responsive_ui_contract.py`

Implement:
- collapsible sidebar;
- command rail that becomes a bottom/overlay rail on narrow windows;
- resizable main/inspector panes with CSS grid and `ResizeObserver`;
- density modes: Compact, Comfortable, Spacious;
- breakpoint behavior at approximately 720px, 960px, 1280px, and 1600px;
- safe overflow handling for cards, transcripts, code, tables, and long provider names;
- persistent layout preferences through the existing settings allowlist.

### Task 7: Build the Warp-style route block model

**Objective:** Present each route as a structured, inspectable command block instead of one linear output area.

**Files:**
- Create: `backend/static/aui/route-blocks.js`
- Modify: `backend/static/index.html`
- Modify: `backend/main.py` only if missing event/receipt fields
- Test: `tests/test_terminal_workbench.py`, `tests/test_route_blocks.py`

Each block should expose prompt metadata, plan, specialist stages, synthesis, verification, aggregate status, timing, usage, cancellation state, redacted receipt ID, bookmark, retry, copy, export, and expand/collapse controls. Never expose credentials or private room transcripts in public receipt blocks.

### Task 8: Upgrade command palette and keyboard ergonomics

**Objective:** Make every important function discoverable and executable without a mouse.

**Files:**
- Modify: `backend/aui.py`
- Modify: `backend/static/aui/actions.js`
- Modify: `backend/static/aui/app.js`
- Test: `tests/test_command_palette.py`, `tests/test_keyboard_actions.py`

Implement:
- Ctrl/Cmd+K and Ctrl/Cmd+Shift+P palette opening;
- fuzzy search by action, page, feature, and shortcut;
- recent and favorite actions;
- arrow-key navigation, Enter execution, Escape close;
- Ctrl/Cmd+L route focus;
- Ctrl/Cmd+R live refresh;
- Escape returns focus to the route composer when no modal is open;
- deterministic focus restoration after dialogs and transient panels;
- visible shortcut hints and `aria-keyshortcuts`.

---

## Phase 3: Functionality and Human UI Optimization

### Task 9: Add live runtime event transport

**Objective:** Replace slow page-level polling for active routes with live progress updates.

**Files:**
- Create: `backend/aui_events.py`
- Modify: `backend/main.py`
- Modify: `backend/route` execution helpers as needed
- Create: `backend/static/aui/live-events.js`
- Test: `tests/test_aui_events.py`

Prefer a loopback-only Server-Sent Events endpoint first because it fits the existing FastAPI app and avoids unnecessary websocket complexity. Stream redacted lifecycle events: planned, specialist started, specialist complete, synthesis, verification, aggregate, complete, failed, cancelled. Retain polling fallback for packaged/offline environments.

### Task 10: Add cancellation and retry semantics

**Objective:** Give users control over long-running work.

**Files:**
- Modify: `backend/main.py`
- Modify: route/runtime execution modules
- Modify: `backend/static/aui/route-blocks.js`
- Test: `tests/test_route_cancellation.py`, `tests/test_runtime.py`

Add bounded cancellation tokens per route/job, idempotent cancellation, visible status transitions, retry-from-receipt using redacted metadata, and explicit behavior when a provider cannot be interrupted. Never claim cancellation succeeded until the backend confirms it.

### Task 11: Improve provider and Key operations

**Objective:** Make Solomon's Keys easier to understand, test, and manage.

**Files:**
- Modify: provider rendering modules in `backend/static/aui/`
- Modify: `backend/main.py` only where contracts are incomplete
- Test: existing provider tests plus `tests/test_aui_provider_controls.py`

Add filterable readiness lanes for Ready, Staged, Disabled, Unreachable, and Rate Limited. Show context window, capabilities, last probe, cooldown, local/open-model classification, and aggregate eligibility. Add safe bulk actions that operate only on references and never accept credential values.

### Task 12: Improve workspace/context ergonomics

**Objective:** Make local project context as quick to use as a terminal file picker without allowing shell execution.

**Files:**
- Modify: `backend/static/aui/workspace.js`
- Modify: `backend/workspace_context.py` only if contract gaps exist
- Test: existing workspace tests plus `tests/test_aui_workspace.py`

Add tree filtering, recent files, breadcrumb navigation, selected-file preview, diff preview, context budget indicator, and one-click insertion into the route composer. Preserve traversal, symlink, secret-shaped file, byte, depth, and line limits.

### Task 13: Upgrade Rooms, Forums, and persistent agents

**Objective:** Present multi-agent work as human-readable team operations rather than raw records.

**Files:**
- Modify: `backend/static/aui/councils.js`
- Modify: `backend/static/aui/runtime.js`
- Modify: existing room/runtime backend modules only where needed
- Test: existing room/runtime tests plus `tests/test_aui_councils.py`

Add room cards with seats, Chymeria, phase, progress, latest decision, and privacy boundary. Add transcript filters by phase/agent, public-versus-private labeling, forum round status, persistent-agent health, run/stop/delete actions, and visible error recovery.

---

## Phase 4: Accessibility, Packaging, and Validation

### Task 14: Complete accessibility implementation

**Objective:** Turn the Warp-inspired role/value/help model into actual DOM behavior.

**Files:**
- Modify: `backend/aui.py`
- Modify: `backend/static/aui/announcements.js`
- Modify: `backend/static/index.html`
- Test: existing accessibility tests plus `tests/test_accessibility_contract.py`

Implement semantic landmarks, dialog focus traps, keyboard access for every action, status/live regions, visible focus rings, reduced motion, contrast checks, descriptive labels for Tarot art and Key sigils, and concise announcements for route and room state changes.

### Task 15: Add frontend contract and smoke tests

**Objective:** Verify controls and structure without requiring a remote provider.

**Files:**
- Create: `tests/test_aui_navigation_contract.py`
- Create: `tests/test_aui_responsive_contract.py`
- Modify: existing UI contract tests

Validate required IDs, manifest-to-handler coverage, keyboard strings, surface filtering, no secret-shaped AUI fields, all navigation targets, and safe formatted output. Extract the inline or bundled JavaScript and run `node --check`.

### Task 16: Run source-runtime verification

**Objective:** Prove the development artifact works end-to-end.

**Commands:**
```bash
.venv/Scripts/python.exe -m pytest -q tests
.venv/Scripts/python.exe -m py_compile backend/*.py
node --check build/aui-inline-check.js
```

Start an isolated server on a free loopback port and verify:
- `/health`;
- `/api/aui/manifest?surface=terminal`;
- `/api/aui/manifest?surface=operator`;
- `/api/aui/manifest?surface=ade`;
- `/` contains the AUI build marker and required controls;
- one offline route plan or other real local operation succeeds;
- a route receipt is produced without secrets.

Use browser/native UI verification for layout, focus, palette execution, route submission, responsive resizing, and at least one state-changing control. If browser remote debugging requires user permission, stop and report it rather than clicking permission prompts without consent.

### Task 17: Verify the packaged EXE chain

**Objective:** Ensure the upgraded UI is present in the actual desktop artifact, not just the source server.

**Files:**
- Inspect/modify only if necessary: `OBus.spec`, `pyinstaller.spec`, launcher/build scripts
- Test: packaging smoke scripts under `tests/`

Follow the packaged-app verification chain:
1. build with the intended interpreter;
2. inspect bundle contents for `backend/aui.py` and static assets;
3. launch the new executable on an isolated port;
4. verify health, manifest, UI marker, and one real operation;
5. hash the verified artifact;
6. only deploy/copy after explicit user approval;
7. verify the deployed copy separately.

### Task 18: Update documentation and release checklist

**Objective:** Make the new AUI understandable and supportable.

**Files:**
- Modify: `README_OBUS_EXE.md`
- Create or modify: `docs/obus-aui.md`
- Create: `.hermes/plans/aui-verification-notes.md` only if needed for release evidence

Document the information architecture, keyboard map, surfaces, accessibility behavior, route blocks, provider safety boundaries, responsive behavior, troubleshooting, research provenance, and known limitations. Clearly state that Warp is a reference and optional companion, not an embedded dependency.

---

## Acceptance Criteria

- All major OBus functions are reachable from navigation and the command palette.
- Every visible action maps to a tested backend or local frontend operation.
- Terminal, Operator, and ADE surfaces expose only their intended action/page sets.
- Route execution shows live structured blocks with honest status, timing, usage, and failure state.
- Long-running route and runtime jobs can be stopped or retried with confirmed backend state.
- Keyboard-only users can navigate, execute, close, and return focus predictably.
- Screen readers receive concise value/role/help announcements for meaningful state changes.
- Layout remains usable across narrow, normal, and wide desktop window sizes.
- AUI output remains secret-free and does not expose credentials, tokens, private keys, or private room transcripts.
- Source tests, JavaScript syntax checks, live API checks, visible UI checks, and packaged EXE checks all produce concrete evidence.
- Existing unrelated test failures remain separately identified and are not hidden by the upgrade.

## Risks and Tradeoffs

- The current single-file SPA is large; extract shared infrastructure incrementally to avoid breaking existing feature handlers.
- SSE improves responsiveness but needs a polling fallback for packaged/offline environments.
- More information density can harm clarity; use progressive disclosure, collapsible blocks, and density preferences.
- Browser/native UI verification may require explicit user permission for remote debugging.
- Warp source licensing and branding must remain isolated; adopt interaction principles, not copied implementation or assets.
- A full EXE rebuild may be slower and should be a separate approval boundary after source/runtime verification.

## Execution Handoff

Implement task-by-task using subagent-driven-development with a fresh context per task, TDD for each behavior, and spec-compliance plus code-quality review before moving to the next task. Do not commit, package, deploy, or overwrite user-generated state without explicit approval.
