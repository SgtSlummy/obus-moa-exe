# Configure the Obus GitHub App integration

Obus can authenticate as a GitHub App installation for repository-scoped memory synchronization. This is distinct from Windows executable certification: GitHub App identity is configured on GitHub; Windows trust requires Authenticode signing.

## Register the app

1. In GitHub, open **Settings → Developer settings → GitHub Apps → New GitHub App**.
2. Name the app, set its homepage to this repository, and disable webhooks unless you are adding a separately secured public webhook receiver. The local Obus server does not require a webhook or OAuth callback.
3. Grant the minimum repository permissions needed by your workflow. For the current memory sync, use **Contents: Read and write** and no organization/account permissions.
4. Create the app, note its numeric **App ID**, generate a private key, and install the app only on the repositories Obus should access.
5. Note the numeric installation ID from the installation URL.
6. Store the downloaded PEM outside the repository in a user-readable location. Never paste PEM content into the UI or commit it.

## Connect it in Obus

Open **Integrations → GitHub App** and provide:

- App ID and installation ID
- repository owner, repository name, and branch
- repository-relative memory path (default `obus/memory.json`)
- absolute local path to the PEM private-key file
- optional app slug

Save, then use **Test GitHub App**. Obus persists only the key path, validates numeric IDs and safe repository/path syntax, creates short-lived installation tokens, and never returns private-key contents through its API.

GitHub does not offer a generic “certified app” switch for private integrations. Verification in GitHub Marketplace is a separate application and review process with GitHub and cannot be self-issued by repository code. The configuration above creates a least-privilege, installable GitHub App; Marketplace verification must be requested from GitHub when the product and publisher meet its current requirements.
