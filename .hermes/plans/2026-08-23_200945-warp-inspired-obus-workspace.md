# Warp-Inspired OBus Open Agentic Workspace Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Improve OBus from a dense dashboard into a configurable, agent-first local development workspace inspired by Warp’s open-source direction: a terminal-first surface, a minimal agent workspace, and a full ADE surface with portable settings, transparent routing, local workspace context, and verifiable run handoffs.

**Architecture:** Keep the existing FastAPI + single-file static frontend + PyInstaller architecture, but add small backend modules for non-secret user settings and bounded workspace inspection instead of expanding `backend/main.py` further. The UI will consume the existing route-plan/route-run contracts, add a command palette and workspace modes, and expose a read-only local context layer. OBus’s current invariants remain unchanged: Tarot cards are personas, Solomon’s Keys are authorization references, local Ollama remains the primary scout/orchestrator, only Ready and connected Keys are callable, the Luna aggregate remains after local execution, and offline mode stays honest.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, vanilla HTML/CSS/JavaScript in `backend/static/index.html`, JSON state with atomic writes, PyInstaller, `unittest`/FastAPI `TestClient`.

---

## Research basis and adaptation

Source reviewed with agent-reach: https://www.warp.dev/blog/warp-is-now-open-source

Relevant Warp ideas to adapt rather than copy:

- Agent implementation is paired with human specification and verification, so OBus should make route plans, evidence, and verification receipts first-class.
- A configurable product can range from “just a terminal” through a minimal agent-development surface to a full ADE; OBus should let users choose how much UI is visible instead of forcing all eleven current pages on every user.
- Multi-model/multi-harness routing and an “auto (open)” route suggest an explicit open-model routing policy, but OBus must implement this through its existing Ready-Key/cooldown rules rather than account cycling or hidden credential behavior.
- A programmatic settings file improves portability between machines; OBus should export/import only validated non-secret settings and keep credentials as environment-variable/file references.
- Public roadmap/issues are useful for collaborative development; OBus should produce redacted, reproducible run receipts and a review checklist that can be attached to an issue without leaking prompts, credentials, or private room transcripts.

This is not a Warp clone and does not import Warp source, branding, or closed implementation details.

## Current context / assumptions

- The primary UI is the monolithic SPA at `backend/static/index.html:1-417`; it already has a Hermes-style route composer, dynamic Tarot/Key harness, rooms/forums, memory, Forge, hardening, runtime agents, and settings.
- The backend is concentrated in `backend/main.py`; state normalization and atomic persistence are at `backend/main.py:308-426`, settings validation is at `backend/main.py:480-564` and `1623-1636`, dashboard data is at `backend/main.py:1516-1556`, and route planning/execution is at `backend/main.py:2982-3057` and `3360-3530`.
- Existing routing already has local-first execution and a reserved `GPT 5.6 Luna` aggregate. The new “Auto (open)” mode must select only eligible open-source/local Ready Keys and must never bypass verification or cooldowns.
- Existing tests in `tests/test_runtime.py` and `tests/test_integrated_dashboard.py` assert secret safety, honest offline mode, UI controls, route traces, usage metrics, room isolation, and packaged-runtime contracts. New work must preserve these tests.
- The working tree contains user modifications and untracked deployment/integration files. Implementation must touch only the files listed below and must not overwrite or clean unrelated work.

## Proposed user-visible result

1. On first launch, OBus offers three workspace surfaces:
   - **Terminal**: route composer, live output, status, and command palette.
   - **Operator**: Terminal plus cards/keys, memory, runtime, and rooms.
   - **ADE**: all current OBus pages, including Forge, hardening, forum, and integrations.
2. `Ctrl/Cmd+K` opens a searchable command palette with keyboard navigation for route actions, page changes, refresh, GPU warmup, settings, and receipt export.
3. A selected local workspace root can be inspected as a bounded file tree and redacted diff/context panel. It is read-only by default; no arbitrary shell execution is added.
4. Routing exposes an explicit `Auto (open)` policy and a human-readable explanation of why each Tarot persona received its temporary Key/model assignment.
5. Completed routes can be exported as a secret-safe run receipt containing the prompt hash, plan, assignment metadata, trace, usage, verification status, and final answer, with private room transcripts excluded.
6. Settings can be exported/imported as a versioned JSON document containing UI/profile/routing preferences only.

---

## Task 1: Establish the settings schema and workspace-surface model

**Objective:** Add a versioned, non-secret settings model that can represent the selected OBus surface and routing policy without breaking legacy `obus_state.json`.

**Files:**
- Create: `backend/user_settings.py`
- Modify: `backend/main.py:308-400`, `480-489`, `551-564`
- Test: `tests/test_user_settings.py`

**Step 1: Write failing tests**

Cover:

- legacy state receives defaults for `workspace_surface="operator"`, `routing_policy="local-first"`, `workspace_root=None`, and `settings_schema_version=1`;
- invalid surface/policy values normalize to safe defaults;
- secret-shaped keys (`api_key`, `token`, `password`, private-key contents) are rejected from import/export payloads;
- normalization preserves existing RAG, model, deck, harness, memory, and autoscroll settings.

**Step 2: Run the focused test**

Run:

```bash
python -m unittest tests.test_user_settings -v
```

Expected: FAIL because the settings module and new fields do not exist.

**Step 3: Implement the minimal schema**

Use a small dataclass or Pydantic model with:

```python
WORKSPACE_SURFACES = {"terminal", "operator", "ade"}
ROUTING_POLICIES = {"local-first", "auto-open", "manual"}
DEFAULT_USER_SETTINGS = {
    "settings_schema_version": 1,
    "workspace_surface": "operator",
    "routing_policy": "local-first",
    "workspace_root": None,
}
```

Keep secrets out of the model entirely. Add migration/validation helpers and have `get_settings()` merge the new defaults with existing state settings.

**Step 4: Run the focused test again**

Expected: PASS, with all existing settings tests still passing.

**Step 5: Verify legacy compatibility**

Run:

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_rag_toggle_persists_through_settings_endpoint -v
```

Expected: PASS; the existing settings endpoint still persists ordinary settings.

---

## Task 2: Add settings export/import contracts

**Objective:** Make non-secret OBus preferences portable between Thor, Loki, and future machines without exporting credentials or machine-bound access data.

**Files:**
- Modify: `backend/main.py:480-489`, `1623-1636`
- Modify: `backend/static/index.html:224`, `398-414`
- Test: `tests/test_user_settings.py`

**Step 1: Write failing API tests**

Add tests for:

- `GET /api/settings/export` returning a versioned JSON-safe document;
- export excluding access tokens, API-key values, OAuth tokens, private-key contents, and machine-local access-gate state;
- `POST /api/settings/import` accepting only the allowlisted settings shape;
- invalid ranges returning `400`/`422` without changing persisted state;
- importing settings using atomic persistence and preserving unknown future fields only if explicitly allowed by the schema.

**Step 2: Run the focused tests**

Expected: FAIL because the endpoints do not exist.

**Step 3: Implement the endpoints**

Add explicit request/response models. Reuse the existing `get_settings()` validation rules, then add `export_user_settings()` and `import_user_settings()` helpers. Do not accept arbitrary dictionaries. Import must never change `keys`, `machine_setup`, `access_gate`, rooms, memory, or GitHub private-key references.

**Step 4: Add real UI controls**

In the Setup page, add `Export settings` and `Import settings` controls. Export should download a Blob created from the API response. Import should use a file input, parse JSON locally, show the keys being changed, and require a deliberate Apply action before posting. Display backend validation errors through the existing toast path.

**Step 5: Verify**

Run:

```bash
python -m unittest tests.test_user_settings tests.test_runtime.RuntimeContractTests.test_rag_toggle_persists_through_settings_endpoint -v
```

Expected: PASS, including secret-redaction assertions.

---

## Task 3: Implement workspace surface modes in the frontend

**Objective:** Let users choose Terminal, Operator, or ADE without deleting or weakening existing functionality.

**Files:**
- Modify: `backend/static/index.html:31-58`, `61-225`, `277-414`
- Modify: `backend/main.py:1516-1556`
- Test: `tests/test_workspace_surface.py`

**Step 1: Write failing UI/API contract tests**

Assert that the dashboard exposes `settings.workspace_surface`, the Setup page contains a surface selector, and the HTML contains stable IDs for the three surface modes and the surface-aware navigation container.

**Step 2: Run the focused test**

Expected: FAIL because the new selector and dashboard field are absent.

**Step 3: Implement surface-aware rendering**

Add a single `applyWorkspaceSurface(surface)` function in the SPA. It should toggle navigation/page visibility using a data attribute, not duplicate page markup. Keep the route composer and live status visible in all modes. Terminal mode hides advanced panels; Operator reveals the core OBus panels; ADE reveals all existing panels. Persist the selection through `/api/settings`.

Use the existing `titles`, `setPage()`, and `renderDashboard()` paths so navigation remains compatible with current tests.

**Step 4: Add responsive layout polish**

Make the Terminal surface prioritize the composer and result stream, while Operator/ADE retain the existing cards and panels. Add accessible labels, focus-visible styles, and a clear “current surface” badge; do not replace the existing OBus emblem or Tarot/Key identity.

**Step 5: Verify**

Run:

```bash
python -m unittest tests.test_workspace_surface tests.test_runtime.RuntimeContractTests.test_modern_ui_exposes_real_controls_not_simulated_alerts -v
```

Expected: PASS; no existing page IDs disappear from ADE mode.

---

## Task 4: Add the global command palette

**Objective:** Provide Warp-like keyboard-first navigation and actions without introducing a new frontend framework.

**Files:**
- Modify: `backend/static/index.html:277-414`
- Test: `tests/test_command_palette.py`

**Step 1: Write failing static contract tests**

Require stable IDs/functions:

- `command-palette`
- `command-palette-input`
- `command-palette-results`
- `openCommandPalette`
- `runCommandPaletteAction`
- `Ctrl/Cmd+K` handling
- `Escape` close handling

Also assert the palette action list includes route, refresh, warm GPU, Settings, Memory, Cards & Keys, Rooms, and receipt export.

**Step 2: Run the focused test**

Expected: FAIL because no palette exists.

**Step 3: Implement the minimal accessible palette**

Add a `<dialog>` or modal surface with:

- text filtering;
- arrow-key selection;
- Enter to execute;
- Escape to close;
- focus restoration to the previously focused element;
- action descriptions and disabled states where the backend is unavailable.

Route actions through existing functions (`run`, `refresh`, `warmGpu`, `setPage`) rather than duplicating behavior. Do not use `window.prompt` for palette operations.

**Step 4: Verify keyboard behavior**

Use a small pure-JS/static contract test for action registration and run the existing UI contract suite. If browser automation is available during implementation, verify `Ctrl+K`, type “memory”, Enter, and confirm the Memory page opens.

---

## Task 5: Add the bounded local workspace context service

**Objective:** Give the agentic workspace a useful file tree and diff/context view while keeping the packaged app local, read-only, bounded, and secret-safe.

**Files:**
- Create: `backend/workspace_context.py`
- Modify: `backend/main.py` to register workspace endpoints and settings models
- Modify: `backend/static/index.html` to add the Terminal/Operator workspace context panel
- Test: `tests/test_workspace_context.py`

**Step 1: Write failing security and behavior tests**

Cover:

- a configured workspace root returns a bounded tree of relative paths;
- traversal (`..`), absolute paths outside the root, symlinks/reparse points escaping the root, and missing roots are rejected;
- output is capped by file count, depth, and bytes;
- `.env`, credential files, private keys, OAuth files, and configured OBus secret locations are omitted or marked redacted;
- text files can return bounded content/diff metadata, while binary files return metadata only;
- no shell command is executed.

**Step 2: Run the focused tests**

Expected: FAIL because the service and endpoints do not exist.

**Step 3: Implement read-only inspection**

Use `pathlib.Path.resolve()` and an explicit root containment check. Expose only operations such as:

- `GET /api/workspace/status`
- `GET /api/workspace/tree?path=...`
- `GET /api/workspace/file?path=...`
- `GET /api/workspace/diff?path=...`

Do not run `git`, a shell, or arbitrary user commands from these endpoints. If a Git diff is later needed, make it an optional, separately verified adapter rather than a default command executor.

**Step 4: Add the UI**

Add a file-tree/context panel with refresh, selected-file preview, byte/line limits, and an explicit “read-only local context” label. Include a “Use in next route” action that inserts a bounded context reference into the prompt, never the entire workspace.

**Step 5: Verify**

Run:

```bash
python -m unittest tests.test_workspace_context -v
```

Expected: PASS, including traversal and secret-redaction tests.

---

## Task 6: Add explicit `Auto (open)` routing policy

**Objective:** Adapt Warp’s open-model routing idea to OBus’s Tarot Router and Solomon’s Keys without bypassing readiness, cooldowns, local-first ordering, or the reserved aggregate.

**Files:**
- Modify: `backend/user_settings.py`
- Modify: `backend/main.py:2900-3050`, provider-selection helpers, and route execution
- Modify: `backend/static/index.html:77-84`, route plan rendering, and settings
- Test: `tests/test_open_routing_policy.py`

**Step 1: Write failing routing tests**

Cover:

- `routing_policy="auto-open"` selects only Ready, connected, non-aggregator Keys whose provider/model is identified as open/local by the existing catalog metadata;
- staged, disabled, unverified, disconnected, cooldown-active, and reserved aggregate Keys are excluded;
- the local Ollama scout remains first when available;
- no permanent Tarot card→Key binding is written during auto selection;
- when no eligible open Key exists, OBus returns an honest offline/partial plan rather than silently falling back to a closed provider;
- manual mode preserves current explicit assignment behavior.

**Step 2: Run the focused tests**

Expected: FAIL because `auto-open` is not a valid policy.

**Step 3: Implement policy selection**

Add a policy parameter to planning and the settings endpoint. Keep selection centralized in the existing matching function or a narrowly extracted helper. Return a `routing_explanation` object for each assignment containing capability overlap, readiness, cooldown result, locality/open-model classification, and the reason it won or was excluded. Never include credential values.

**Step 4: Implement UI controls**

Add a settings selector with `Local-first`, `Auto (open)`, and `Manual`. Show the active policy and a collapsible explanation beside each planned Tarot assignment. Keep the visible aggregate row labeled as the post-local Luna stage.

**Step 5: Verify**

Run:

```bash
python -m unittest tests.test_open_routing_policy tests.test_runtime.RuntimeContractTests.test_gpt_56_luna_is_reserved_aggregate_after_local_stage -v
```

Expected: PASS; existing Luna and dynamic assignment behavior remains intact.

---

## Task 7: Persist redacted run receipts and handoff packets

**Objective:** Turn OBus route output into a reproducible artifact for human verification, agent handoff, and future public issue/roadmap workflows.

**Files:**
- Create: `backend/run_receipts.py`
- Modify: `backend/main.py:3360-3530`
- Modify: `backend/static/index.html:61-116`, command palette actions, and route completion rendering
- Test: `tests/test_run_receipts.py`

**Step 1: Write failing tests**

Assert that a completed local, partial, and offline route can produce a receipt containing:

- receipt ID and timestamp;
- stable prompt hash, not necessarily the raw prompt;
- selected deck, temporary assignment metadata, policy, model names, stages, trace, usage, latency, and final status;
- verification/aggregate status and explicit unavailable reasons;
- bounded final output;
- no API-key values, OAuth tokens, passwords, private-key contents, access tokens, or private room messages.

Test deterministic redaction with strings such as `api_key=...`, `Bearer ...`, and PEM blocks.

**Step 2: Run the focused tests**

Expected: FAIL because receipts are not persisted or returned.

**Step 3: Implement receipt storage and API**

Add an atomic bounded JSON-lines or JSON-array receipt store under the existing OBus data directory, with a retention cap. Extend `/api/route/run` to return a receipt summary and add:

- `GET /api/runs`
- `GET /api/runs/{receipt_id}`
- `GET /api/runs/{receipt_id}/export`

The export endpoint may return Markdown or JSON, but it must be derived from the same redacted canonical receipt.

**Step 4: Add UI handoff controls**

Add “Export receipt” after route completion and a Runs/Receipts view in Operator/ADE. The receipt view must distinguish public handoff data from private room deliberation and show provenance/status rather than claiming verification that did not happen.

**Step 5: Verify**

Run:

```bash
python -m unittest tests.test_run_receipts tests.test_integrated_dashboard tests.test_runtime -v
```

Expected: PASS with receipt redaction and current route/room behavior preserved.

---

## Task 8: Update documentation and packaged-artifact contracts

**Objective:** Document the new workspace model and prove the EXE includes the new backend modules, UI, settings behavior, and receipt/workspace data paths.

**Files:**
- Modify: `README_OBUS_EXE.md`
- Modify: `backend/API_ENDPOINTS.md`
- Modify: `OBus.spec`
- Modify: `tests/test_integrated_dashboard.py`
- Modify: `tests/test_thor_deployment_package.py` if the deployment contract needs a new settings/receipt path

**Step 1: Add documentation tests**

Assert that the API docs mention the workspace surface/settings import-export, workspace context limits, `auto-open` policy, and run receipt endpoints. Assert the spec includes any newly created backend modules and required static assets.

**Step 2: Update user documentation**

Document:

- Terminal/Operator/ADE modes;
- `Ctrl/Cmd+K` palette;
- settings portability and what is intentionally excluded;
- read-only workspace context and security limits;
- open-model routing eligibility and honest fallback behavior;
- run receipt export and privacy boundary;
- correct current ports and paths, fixing stale troubleshooting references to port 8080 while touching the README.

**Step 3: Update PyInstaller data/import declarations**

Include new Python modules as hidden imports if PyInstaller analysis does not discover them and ensure the existing `backend/static` recursive packaging continues to include the expanded UI. Do not hard-code a different machine’s data directory for mutable settings or receipts.

**Step 4: Verify source contracts**

Run:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all existing and new tests pass.

**Step 5: Verify the packaged chain during implementation**

Following the packaged-desktop verification workflow:

```bash
pyinstaller --clean --noconfirm OBus.spec
```

Then, with the development server stopped, launch the newly built executable and verify `/health`, `/`, `/api/settings/export`, `/api/workspace/status`, and a real offline route/receipt flow. Confirm the process, port, build output, and deployed copy by hash before claiming the EXE is improved. This step is for implementation execution, not this planning turn.

---

## Files likely to change

Create:

- `backend/user_settings.py`
- `backend/workspace_context.py`
- `backend/run_receipts.py`
- `tests/test_user_settings.py`
- `tests/test_workspace_surface.py`
- `tests/test_command_palette.py`
- `tests/test_workspace_context.py`
- `tests/test_open_routing_policy.py`
- `tests/test_run_receipts.py`

Modify:

- `backend/main.py`
- `backend/static/index.html`
- `README_OBUS_EXE.md`
- `backend/API_ENDPOINTS.md`
- `OBus.spec`
- deployment tests only if the packaged data contract requires it

Do not modify or overwrite the existing untracked deployment/headless files unless a later implementation task proves they are directly required.

## Validation matrix

- Unit/API: new focused tests plus `python -m unittest discover -s tests -p 'test_*.py' -v`.
- Secret safety: recursively inspect exported settings, workspace responses, route plans, traces, and receipts for key/token/password/PEM values.
- UI contracts: assert all existing IDs remain in ADE mode and new palette/surface/workspace/receipt IDs exist.
- Runtime: prove local-first route, open-policy route, partial route, offline route, receipt export, and settings round-trip.
- Workspace security: prove root containment, traversal rejection, symlink escape rejection, size limits, binary handling, and no shell invocation.
- Packaging: build with the checked-in `OBus.spec`, inspect bundle contents, launch the EXE without a development server, call health/UI/API endpoints, and visually verify the selected surface and working controls.

## Risks, tradeoffs, and open questions

- **Scope risk:** the existing SPA is a 417-line HTML file with very dense inline JavaScript. Prefer additive helpers and stable IDs first; defer a framework migration or broad component split.
- **Workspace privacy:** the default should be no configured workspace root. Require an explicit local root and show a read-only warning. Never scan the user’s home directory implicitly.
- **Git integration:** a file tree/diff view is valuable, but invoking Git or arbitrary commands from the API expands the trust boundary. Start with bounded file metadata/content; add a separate reviewed Git adapter only if needed.
- **Open-model classification:** the existing Key catalog must gain an explicit non-secret `open_model`/`local` classification rather than inferring openness from provider names. Unknown custom providers must not qualify for `auto-open` automatically.
- **Receipt contents:** raw prompts and final answers may contain sensitive project information even after credential redaction. Default exports should use a prompt hash plus bounded, user-selected answer text, with a clear “contains task content” warning.
- **Settings portability:** machine role, access gate, credentials, private-key paths, and deployment identity must not be imported. A future explicit “machine profile” feature can handle those separately.
- **Tarot/Key invariant:** `auto-open` is a routing policy, not a permanent card assignment. Any implementation that writes `assigned_key_id` during automatic planning is incorrect.
- **Existing working tree:** implementation must preserve the current modified emblem and untracked headless/deployment files; inspect `git status` before each mutation and do not commit unless separately requested.

## Sources

- Warp announcement and contribution model: https://www.warp.dev/blog/warp-is-now-open-source
- OBus current runtime and packaging contracts: `README_OBUS_EXE.md`, `OBus.spec`, `backend/main.py`, `backend/static/index.html`, `tests/test_runtime.py`, and `tests/test_integrated_dashboard.py`.
