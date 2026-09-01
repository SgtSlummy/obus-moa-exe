## Key‑rotation reference

This reference contains the high‑level workflow and the supporting script that performs rotation based on an `expires_at` timestamp. It is kept separate from the skill definition because the skill is user‑owned.  The script is located in `scripts/key_rotate.py` and can be invoked manually or scheduled with Hermes’ `cronjob`.

### Workflow steps
1. Load keys from `/api/keys`.
2. Identify keys where `expires_at \u003c= now`.
3. Mark the key as `staged` via PUT.
4. POST `/api/keys/\u003cid\u003e/test`.
5. If test succeeds, mark the key `ready`; otherwise leave it `staged`.
6. Log all actions.

The script automatically imports the OBus URL and API key from environment variables `OCCULTBUS_BASE_URL` and `OCCULTBUS_API_KEY`.

---
*If you need the script again, see `scripts/key_rotate.py`.
