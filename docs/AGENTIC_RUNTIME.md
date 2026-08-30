# OBus agentic runtime

OBus uses a coordinator-and-task-graph design rather than pretending several model calls form one larger context window.

## Autonomy

The default `autonomy_level` is `high`. Agents inspect available state, infer reasonable defaults, execute reversible local work, verify it, and continue through recoverable failures. They still stop for credentials, external authority, destructive or irreversible effects, and choices that materially change the requested outcome. Persistent agents, parallel teams, and executable orchestrations reject major destructive or hardware-risk objectives at the server boundary before any autonomous run, agent record, or task ledger is created. Those actions must use a guarded manual flow with explicit local approval.

`conservative`, `balanced`, and `high` are available through `PUT /api/settings`.

## Context allocation

Each Ollama call receives an explicit `options.num_ctx`. In automatic mode OBus selects the largest context advertised for the model and uses `context_utilization_percent` (95% by default), leaving generation and runtime headroom. `per_agent_context_window` can override the automatic value; zero restores automatic sizing. Overrides are capped by the model/key limit.

The desktop route composer has a separate model-aware input budget: it permits up to 55% of the active effective context, with a 65,536-token / 262,144-character ceiling, then reserves the remainder for the local harness, retrieval, and generated answer. The composer shows a local character-based estimate before execution and the server enforces the same budget. This removes the former fixed 4,000-character route ceiling without claiming that different agents can combine their context windows.

## Local voice input

The Home agent window can record a prompt only after the user presses **Voice**. The desktop browser captures the microphone, sends the recording only to OBus's loopback endpoint, and inserts the resulting local Faster-Whisper transcript into the composer; it never starts a task by itself. A pre-existing model path in `OBUS_LOCAL_STT_MODEL_PATH` and Faster-Whisper are required. `sounddevice` is not required for this browser-capture path, and OBus does not download voice models or use a cloud fallback automatically.

## Local attachments

The desktop composer can stage up to eight user-selected text or code files (512 KB each, 1 MB total). Browser-side staging means OBus does not create a separate attachment directory or retain those files after the page is closed. Each attachment appears as a removable chip, contributes to the same model-aware input budget, and is sent only with the route the user explicitly starts. A remote aggregate still requires its separate confirmation, so local attachments are never silently transferred outside the computer.

## Native workspace selection

On Windows desktop builds, **Choose folder** opens the system folder dialog only after an explicit local click. Cancelling does not alter the configured workspace. A selection still passes OBus’s normal workspace validation—including real-directory, containment, and secret-path checks—before it is saved; the picker does not scan a directory or grant agents access by itself.

## Recent local projects

OBus remembers at most twelve previously validated workspace paths on this machine. This is only a local list of paths: it stores no project files, does not rescan a project in the background, and cannot grant an agent access. Selecting a recent entry deliberately revalidates the directory before making it active; a missing or secret-shaped path is refused. Entries can be forgotten without changing the project or its files.

## Quick Start for ordinary work

The **Quick Start** button begins a one-time task from the active local workspace using the best ready provider, normal priority, and three bounded repair attempts. The Home composer exposes the same safe lane as **Autonomous run**, so ordinary workspace work does not require opening the task queue or selecting provider settings first. It does not expose a hidden higher-autonomy mode. Objectives matching destructive, recovery-disabling, firmware, disk-layout, or hardware-control risk are refused by Quick Start and must use the explicit guarded-task approval control instead. Staged route attachments are intentionally excluded from Autonomous run; choose **Begin** when that attachment text should be included in a route.

## Home autonomous monitor

When Home starts an autonomous task, it keeps a redacted live monitor beneath the route area. It reconnects through local polling if the task event stream is unavailable, restores the most recent Home task for that browser session, and stops its subscription after the task reaches a terminal state. **Stop** calls the same existing cancellation endpoint as the task queue; it requests cancellation and rolls back the active checkpoint when applicable. The monitor never bypasses the workspace, provider, or major-risk policies.

Every persistent agent gets its own provider call and therefore its own context window. Context windows are not added together. OBus reserves bounded portions of each window for:

- the agent's private history;
- shared findings from sibling agents;
- the current objective, instructions, and generated answer.

## Parallel task graphs

`POST /api/runtime/orchestrate` asks the local orchestrator to decompose independent branches and auto-start executable agents. Up to 20 agent runs may execute concurrently. The response includes `task_ledger_id`.

The shared task ledger records each branch's findings without merging private histories. After all started branches terminate, a separate local synthesis call resolves disagreements and stores one result. Inspect it through:

- `GET /api/runtime/task-ledgers`
- `GET /api/runtime/task-ledgers/{task_ledger_id}`

### Parallel-lane isolation and integration

Inspired by Orca's worktree-per-agent model, each newly created OBus parallel ledger now makes its isolation and integration boundary explicit. OBus's built-in parallel route is an **evidence lane**, not a repository-writing runner: each agent has a private context and a separately reviewable result; shared material is redacted ledger evidence only. The ledger and launch response declare:

- `workspace_isolation.mode: "private-context-evidence-lanes"`
- `workspace_writes: false`
- `automatic_merge: false`
- `integration_status: "review_required"`

This is intentional. Orca can safely give code-writing agents separate Git worktrees and let a user compare diffs. OBus does not silently create worktrees, write to the selected workspace, merge branches, or delete worktrees from a review team. A synthesis is therefore a decision artifact for the user to review and apply through OBus's separately approved workspace-task flow.

## Settings

```json
{
  "autonomy_level": "high",
  "auto_parallelize": true,
  "shared_task_context": true,
  "context_utilization_percent": 95,
  "per_agent_context_window": 0,
  "max_parallel_agents": 20
}
```

High context and high parallelism increase RAM/VRAM pressure. Reduce `max_parallel_agents`, lower `context_utilization_percent`, or set a smaller `per_agent_context_window` if Ollama unloads models or reports allocation failures.
## Home parallel team

The Home composer offers **Parallel team** for an ordinary workspace goal. It starts no more than three independent reviewers and never exceeds the user’s configured helper limit. The launcher pins every reviewer to one verified local Key, gives each agent a separate bounded context window, and carries only redacted ledger findings into synthesis. Major destructive and hardware-risk objectives are rejected before any agent is created; this control never grants approval or falls back to a remote Key.
