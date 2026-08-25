# GitHub App integration

OBus uses a GitHub App installation token instead of a personal access token. The app can synchronize OBus memory and receive signed workflow events for optional Codex repair objectives.

## Create and install the app

1. In GitHub, open **Settings → Developer settings → GitHub Apps → New GitHub App**.
2. Set the callback URL to your externally reachable OBus URL. OBus does not require OAuth for installation-token operation.
3. Set the webhook URL to `https://YOUR_OBUS_HOST/api/integrations/github-app/webhook`.
4. Generate a cryptographically random webhook secret and set the same value as `OBUS_GITHUB_WEBHOOK_SECRET` on the OBus host.
5. Grant only the permissions needed by your workflow. Memory synchronization requires **Contents: Read and write**. Workflow-failure notification requires **Actions: Read** and **Checks: Read**.
6. Subscribe to **Workflow run** and **Check suite** events if automated repair notification is desired.
7. Install the app on the intended repository and record the App ID and installation ID.
8. Generate a private key, store the PEM file outside the repository with access restricted to the OBus service account, and enter its path in OBus GitHub App settings.

## Runtime configuration

```dotenv
OBUS_GITHUB_WEBHOOK_SECRET=replace-with-a-long-random-secret
OBUS_GITHUB_AUTO_REPAIR=false
OBUS_GITHUB_WEBHOOK_DB=C:/ProgramData/OBus/github-webhooks.sqlite3
OBUS_WORKSPACE=C:/path/to/managed/workspace
```

`OBUS_GITHUB_AUTO_REPAIR` is disabled by default. When enabled, only correctly signed, non-replayed `workflow_run` or `check_suite` completion events with a failed or timed-out conclusion create a Codex objective. Existing harness approval policy, checkpoints, rollback, receipts, and circuit breakers remain in force.

The webhook body is never persisted. OBus stores only the delivery ID, event, action, repository, sender, timestamp, and resulting objective ID. GitHub delivery IDs are unique and serve as replay protection.

## Validation

- Use the GitHub App settings screen to save the App ID, installation ID, repository, and private-key path.
- Run **Test connection** to request an installation token and read the configured repository.
- Open `GET /api/integrations/github-app/webhook/status` locally to confirm webhook configuration and delivery count.
- In GitHub App **Advanced** settings, redeliver a recent event. A valid delivery returns HTTP 202; a repeated delivery returns HTTP 202 with `duplicate: true` and does not queue work twice.

Never commit the private key, webhook secret, installation token, or generated webhook database.
