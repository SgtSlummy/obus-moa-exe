# OBus API Endpoints

## Tarot Card Endpoints

### GET /api/cards
Get all tarot cards (agent personas)
```json
[
  {
    "id": "card-high-priestess",
    "name": "The High Priestess",
    "symbol": "👑",
    "persona": "Synthesis/Aggregator",
    "image": "/static/tarot/high-priestess.svg",
    "reversed": false,
    "active": false,
    "assigned_key_id": "key-codex-oauth",
    "capabilities": ["analysis", "synthesis", "review"]
  }
]
```

### PUT /api/cards/{card_id}
Update a tarot card
```json
{
  "name": "Updated Name",
  "symbol": "🔮",
  "assigned_key_id": "key-local-ollama",
  "persona": "Routing specialist"
}
```

## Solomon's Key Endpoints

### GET /api/keys
Get all Solomon's keys (LLM providers)
```json
[
  {
    "id": "key-codex-oauth",
    "name": "Codex OAuth",
    "provider": "openai",
    "model": "gpt-5.6-terra",
    "symbol": "🗝️",
    "verified": false,
    "approved": false,
    "active": false,
    "can_aggregate": true,
    "auth_type": "oauth"
  }
]
```

### PUT /api/keys/{key_id}
Update a Solomon's key
```json
{
  "name": "Updated Name",
  "provider": "nvidia",
  "model": "nemotron-3-super",
  "api_key_env": "NVIDIA_API_KEY",
  "base_url": "http://localhost:11434/api"
}
```

### POST /api/keys/{key_id}/verify
Verify a key with API authentication

## Authentication Endpoints

### POST /api/login
Handle login for various providers
```json
POST /api/login
{
  "provider": "codex|ollama|nvidia|nous",
  "token": "your-token-or-empty",
  "url": "http://localhost:11434" // for ollama
}

Response:
{
  "success": true,
  "message": "Successfully authenticated",
  "key_id": "key-codex-oauth"
}
```

## MOA Routing

### GET /api/plan?prompt={task}
Get routing plan for a task

### POST /api/plan/execute
Turn an explicitly reviewed plan into a bounded, local-first persistent team. The request includes `prompt`, `mode`, and `max_agents`; OBus selects the previewed card personas, gives each a separate context window, and writes only redacted findings to the shared task ledger. The endpoint rejects major destructive or hardware-risk objectives before creating a ledger or agent; use a guarded manual flow with explicit local approval for those actions.

### GET /api/route/context-budget?model={model}
Get the active route composer's effective context window, model-aware input budget, and reserved generation headroom. `POST /api/route/plan` and `POST /api/route/run` accept up to 262,144 prompt characters, then enforce this same budget after secret filtering.

### POST /api/execute
Execute task through MOA routing
```json
{
  "prompt": "Review this code for security vulnerabilities..."
}
```

## Status

### GET /api/status
System status
```json
{
  "cards": 24,
  "keys": 4,
  "verified_keys": 0,
  "active_assignments": 0,
  "uptime": "00:00:00"
}
```

### GET /health
Health check endpoint

## Warp-inspired workspace

The desktop UI supports three surfaces: **Terminal**, **Operator**, and **ADE**. Terminal focuses on routing; Operator adds core OBus operations; ADE exposes the full workspace.

### GET /api/settings/export
Return a versioned, non-secret portable settings document. Credentials, tokens, machine access state, private-key material, rooms, and memory are excluded.

### POST /api/settings/import
Validate and merge an allowlisted portable settings document.

### GET /api/desktop/capabilities
Return availability of non-sensitive local desktop features. The native workspace picker is reported only for the Windows desktop process.

### POST /api/desktop/quick-task
Start one ordinary task in the active local workspace with the best ready provider, priority `50`, and at most three attempts. The endpoint is local-only. It rechecks the workspace and rejects every major destructive or hardware-risk objective; use `POST /api/harness/tasks` with explicit local approval for that path.

### POST /api/desktop/quick-team
Start up to three independent, local-only reviewers for ordinary work in the active workspace. Each reviewer receives its own bounded context window; they share only redacted findings through the existing task ledger before synthesis. The endpoint rechecks the workspace and refuses every major destructive or hardware-risk objective. It never falls back to a remote Key.

### POST /api/desktop/select-workspace
Open the visible native Windows folder dialog after an explicit local UI action. Cancellation preserves the existing workspace. A selected directory must pass the normal workspace and secret-path checks before its path is saved; this endpoint does not scan or execute anything in the directory.

### GET /api/workspace/recent
Return at most twelve locally remembered, previously validated workspace paths. This history contains paths and timestamps only; the endpoint does not open, scan, or validate each project.

### POST /api/workspace/recent/select
Activate one explicitly clicked recent path only after current workspace and secret-path validation succeeds. A missing or unsafe path is rejected and does not replace the active workspace.

### DELETE /api/workspace/recent
Forget one history entry specified as `{ "root": "…" }`. This alters only OBus’s local MRU list, never the workspace or its files.

### GET /api/workspace/status
Return whether an explicitly configured local workspace root is valid. The context service is read-only.

### GET /api/workspace/tree?path={relative_path}
Return a bounded tree of safe relative paths. Traversal, root escapes, symlink escapes, and secret-shaped files are rejected or omitted.

### GET /api/workspace/file?path={relative_path}
Return bounded UTF-8 text or metadata-only binary context for one file under the configured root.

### PUT /api/workspace/file
Atomically save one explicitly selected local text draft after its original SHA-256 still matches disk. The API refuses binary, oversized, secret-shaped, secret-like, stale, or path-escaping files. It performs no shell command; major destructive or hardware-risk text requires explicit local approval.

### GET /api/workspace/diff?path={relative_path}
Return a bounded, redacted review of one safe text file against `HEAD` when local Git is available. The inspection disables external diff programs and text-conversion filters, does not prompt, does not use Git configuration or credentials, does not run hooks, and never writes to the workspace. Binary, oversized, untracked, non-Git, and unavailable-Git cases return a clear read-only reason instead.

## Routing policies

Route requests may use `local-first`, **Auto (open)** (`auto-open`), or `manual`. `auto-open` only considers Ready, connected Keys explicitly marked local/open-model, honors cooldowns, excludes the Luna aggregate, and returns an honest offline plan if no eligible Key exists. Automatic Tarot card-to-Key matches are temporary.

## Run receipts

### GET /api/runs
List redacted route receipt summaries.

### GET /api/runs/{receipt_id}
Return a redacted receipt containing prompt hash, plan metadata, temporary assignments, trace, usage, status, and bounded task output. Private room transcripts and credentials are excluded.

## Guarded autonomous jobs

### POST /api/harness/tasks
Start one immediate workspace task with `objective`, `workspace`, `provider`, bounded `max_attempts`, and `priority`. Its workspace must already exist. The task runs through the guarded provider contract, creates a checkpoint per attempt, records redacted events and a final receipt, and can be cancelled from the local desktop. Major destructive, recovery-disabling, firmware, disk-layout, and hardware-control work never accepts a boolean bypass: the first local submission creates (or reuses) an inspectable approval request, and a later exact-match submission must supply its single-use, locally approved `approval_id`. Remote callers cannot create, read, resolve, or consume this approval path.

### GET /api/harness/approvals and POST /api/harness/approvals
List a local-only, redacted approval queue or explicitly create a request for a major-risk one-time task. Each request is bound to the objective fingerprint, workspace, provider, retry limit, priority, and detected risk categories; it does not start a task.

### POST /api/harness/approvals/{approval_id}/approve and /reject
Resolve one pending approval only on the local desktop. Approval is single-use: after an exact-match task consumes it, the record remains as a redacted provenance receipt and cannot authorize another task.

### GET /api/harness/tasks and GET /api/harness/tasks/{task_id}
List or inspect durable task state. Objectives, workspace labels, results, errors, and events are redacted and bounded before leaving the harness API.

### DELETE /api/harness/tasks/{task_id}
Request cancellation for one task. A running attempt receives cancellation and its recovery checkpoint is rolled back; queued work is cancelled before execution.

### GET /api/harness/tasks/{task_id}/events
Return the redacted activity sequence used by the desktop task inspector. The corresponding `/events/stream` endpoint emits the same redacted payloads as server-sent events.

### GET /api/harness/tasks/{task_id}/changes
Return the latest task checkpoint’s bounded, read-only manifest of added, modified, deleted, or unreviewable safe files. Secret-shaped paths, binary data, oversized files, and secret-like contents do not appear as diffs. The manifest never executes tools, creates a checkpoint, rolls back, or alters the workspace.

### GET /api/harness/tasks/{task_id}/changes/{relative_path}
Return one explicitly selected, bounded, redacted unified diff against the task checkpoint. Only a path that first appeared in that task’s change manifest may be reviewed. This is display-only and not an apply or rollback action.

### GET /api/harness/objectives
List durable local objectives scheduled through the Agent Jobs surface. Each row exposes its next run, last submitted task ID, enabled state, and a bounded start/skip error when relevant.

### POST /api/harness/objectives
Create a local workspace objective with `name`, `objective`, `workspace`, `interval_seconds`, and `provider`. The workspace must already exist; this endpoint never creates folders. Major destructive, recovery-disabling, firmware, disk-layout, and hardware-control work is rejected for scheduled execution and must instead be requested as a one-time, locally approved task.

### PATCH /api/harness/objectives/{objective_id}
Pause or resume an ordinary objective with `{ "enabled": true|false }`.

### DELETE /api/harness/objectives/{objective_id}
Remove one explicit schedule. The local desktop presents this as a direct operator action.

Scheduler runs never overlap: when a previous task is still active, the interval is skipped and visible in the schedule state. A missing workspace or failed launch disables the schedule rather than retrying unboundedly.

### GET /api/runs/{receipt_id}/export
Export a redacted Markdown handoff receipt.
