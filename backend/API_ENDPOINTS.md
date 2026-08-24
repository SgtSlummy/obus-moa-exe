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

### GET /api/workspace/status
Return whether an explicitly configured local workspace root is valid. The context service is read-only.

### GET /api/workspace/tree?path={relative_path}
Return a bounded tree of safe relative paths. Traversal, root escapes, symlink escapes, and secret-shaped files are rejected or omitted.

### GET /api/workspace/file?path={relative_path}
Return bounded UTF-8 text or metadata-only binary context for one file under the configured root.

### GET /api/workspace/diff?path={relative_path}
Return bounded file context and explain that no Git/shell adapter is enabled by default.

## Routing policies

Route requests may use `local-first`, **Auto (open)** (`auto-open`), or `manual`. `auto-open` only considers Ready, connected Keys explicitly marked local/open-model, honors cooldowns, excludes the Luna aggregate, and returns an honest offline plan if no eligible Key exists. Automatic Tarot card-to-Key matches are temporary.

## Run receipts

### GET /api/runs
List redacted route receipt summaries.

### GET /api/runs/{receipt_id}
Return a redacted receipt containing prompt hash, plan metadata, temporary assignments, trace, usage, status, and bounded task output. Private room transcripts and credentials are excluded.

### GET /api/runs/{receipt_id}/export
Export a redacted Markdown handoff receipt.