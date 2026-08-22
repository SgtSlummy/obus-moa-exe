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