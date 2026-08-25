"""Build a private, paired Thor/Loki OBus distribution with a fresh shared key."""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "OBus-Thor-Loki-Paired"


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def build(executable: Path, output: Path, thor_name: str, loki_name: str, loki_url: str) -> Path:
    parsed = urlparse(loki_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("--loki-url must be an absolute http(s) URL")
    if not executable.is_file():
        raise FileNotFoundError(f"OBus executable not found: {executable}")

    token = secrets.token_urlsafe(32)
    pair_id = secrets.token_hex(8)
    created = datetime.now(UTC).isoformat()
    if output.exists():
        shutil.rmtree(output)
    loki_dir = output / "Loki-Portal"
    thor_dir = output / "Thor-Client"
    loki_dir.mkdir(parents=True)
    thor_dir.mkdir(parents=True)

    shared = {
        "schema": 1,
        "pair_id": pair_id,
        "created_utc": created,
        "thor": {"name": thor_name, "role": "portal-client"},
        "loki": {"name": loki_name, "role": "local-resource-host", "portal_url": loki_url.rstrip("/")},
        "portal_key": token,
    }
    _write_json(loki_dir / "thor-loki.pairing.json", shared)
    _write_json(thor_dir / "thor-loki.pairing.json", shared)
    shutil.copy2(executable, loki_dir / "OBus.exe")

    (loki_dir / "Start-Loki-Portal.ps1").write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "$config = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'thor-loki.pairing.json') | ConvertFrom-Json\n"
        "$env:OBUS_THOR_TOKEN = $config.portal_key\n"
        "$env:OBUS_HOST = '0.0.0.0'\n"
        "& (Join-Path $PSScriptRoot 'OBus.exe')\n",
        encoding="utf-8",
    )
    (thor_dir / "Invoke-Thor-Portal.ps1").write_text(
        "param([Parameter(Mandatory=$true)][string]$Prompt, [string]$Model)\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$config = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'thor-loki.pairing.json') | ConvertFrom-Json\n"
        "$headers = @{ Authorization = \"Bearer $($config.portal_key)\" }\n"
        "$body = @{ prompt = $Prompt }; if ($Model) { $body.model = $Model }\n"
        "Invoke-RestMethod -Method Post -Uri \"$($config.loki.portal_url)/api/portal/thor/generate\" -Headers $headers -ContentType 'application/json' -Body ($body | ConvertTo-Json)\n",
        encoding="utf-8",
    )
    notice = (
        "PRIVATE PAIRED BUILD — DO NOT COMMIT OR SHARE PUBLICLY\n\n"
        f"Pair: {thor_name} -> {loki_name} ({pair_id})\n"
        f"Portal: {loki_url.rstrip('/')}\n\n"
        "Loki: run Loki-Portal/Start-Loki-Portal.ps1.\n"
        "Thor: copy Thor-Client privately and run Invoke-Thor-Portal.ps1 -Prompt 'hello'.\n"
        "Restrict the Loki firewall rule to Thor's private/Tailscale IP. Rotate by rebuilding.\n"
    )
    (output / "PRIVATE-README.txt").write_text(notice, encoding="utf-8")

    files = sorted(path for path in output.rglob("*") if path.is_file())
    (output / "SHA256SUMS.txt").write_text(
        "\n".join(f"{_sha256(path)}  {path.relative_to(output).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    archive = output.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
        for path in sorted(item for item in output.rglob("*") if item.is_file()):
            package.write(path, f"{output.name}/{path.relative_to(output).as_posix()}")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, default=ROOT / "dist" / "OBus.exe")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--thor-name", default="Thor")
    parser.add_argument("--loki-name", default="Loki")
    parser.add_argument("--loki-url", default="http://100.73.36.108:8000")
    args = parser.parse_args()
    archive = build(args.executable.resolve(), args.output.resolve(), args.thor_name, args.loki_name, args.loki_url)
    print(archive)


if __name__ == "__main__":
    main()
