---
name: obus-setup
description: Launches Obus locally and creates a start‑menu link.
title: Obus Setup and Launch
category: utilities
---
When to use:
- Run this skill when you need to start the local Obus service and create a Start‑Menu shortcut to `http://localhost:8081`.

This skill provides reusable scripts and step‑by‑step instructions for:

1. **Starting the Obus service** (Docker container or local Node/React app).
2. **Creating a Start‑Menu shortcut** that points to `http://localhost:8081`.
3. **Reproducing the setup** using the support files in the `references/`, `scripts/`, and `templates/` directories.

> **Reference** – see `references/obos_setup_detail.md` for the full command history, error logs, and troubleshooting notes.

> **Scripts** – `scripts/start_obus.sh` starts the service; `scripts/create_start_menu_link.ps1` creates the URL shortcut.
