"""Assemble a secret-free Thor→Loki OBus deployment ZIP from verified artifacts."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "deploy" / "thor-loki"
DIST_DIR = ROOT / "dist"
STAGING_DIR = DIST_DIR / "OBus-Thor-Loki-Deployment"
ARCHIVE_BASE = DIST_DIR / "OBus-Thor-Loki-Deployment"


def main() -> None:
    executable = DIST_DIR / "OBus.exe"
    if not executable.is_file():
        raise SystemExit(f"Missing verified executable: {executable}")

    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True)

    for template in TEMPLATE_DIR.iterdir():
        if template.is_file():
            shutil.copy2(template, STAGING_DIR / template.name)
    shutil.copy2(executable, STAGING_DIR / "OBus.exe")

    archive = ARCHIVE_BASE.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for packaged_file in sorted(STAGING_DIR.iterdir()):
            if packaged_file.is_file():
                package.write(packaged_file, f"{STAGING_DIR.name}/{packaged_file.name}")
    print(archive)


if __name__ == "__main__":
    main()
