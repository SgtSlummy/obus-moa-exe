"""Shared implementation for machine-bound OBus administrator installers."""
from __future__ import annotations

import argparse
import base64
import ctypes
import getpass
import hashlib
import json
import os
import secrets
import shutil
import sys
from pathlib import Path


def _machine_binding() -> str:
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
        machine_guid = str(winreg.QueryValueEx(key, "MachineGuid")[0])
    return hashlib.sha256(machine_guid.encode("utf-8")).hexdigest()


def _admin_required() -> None:
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise SystemExit("Run this installer from an elevated Administrator console.")


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def _password_verifier() -> dict:
    first = getpass.getpass("Create local OBus access password: ")
    second = getpass.getpass("Confirm local OBus access password: ")
    if not first or first != second:
        raise SystemExit("Passwords did not match. Nothing was installed.")
    salt = secrets.token_bytes(32)
    iterations = 600_000
    verifier = hashlib.pbkdf2_hmac("sha256", first.encode("utf-8"), salt, iterations)
    return {
        "version": 1,
        "iterations": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
        "password_hash": base64.b64encode(verifier).decode("ascii"),
    }


def install(role: str, label: str, peer_label: str, peer_ip: str) -> None:
    _admin_required()
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--voice-model-path", default="")
    args = parser.parse_args()
    voice_path = Path(args.voice_model_path).expanduser() if args.voice_model_path else None
    if voice_path and not voice_path.exists():
        raise SystemExit(f"Voice model path does not exist: {voice_path}")

    verifier = _password_verifier()
    root = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "OBus" / label
    state_root = root / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    source_exe = _resource_root() / "OBus.exe"
    if not source_exe.is_file():
        raise SystemExit("Bundled OBus.exe resource is missing.")
    shutil.copy2(source_exe, root / "OBus.exe")

    state = {
        "settings": {"selected_model": "gpt-oss:20b", "selected_deck": "auto", "harness_enabled": True, "output_autoscroll": True},
        "machine_setup": {"role": role, "label": label, "peer_label": peer_label, "transport": "tailscale-ssh", "mode": "guide-only"},
        "partner": {"peer_label": peer_label, "tailscale_ip": peer_ip, "transport": "tailscale-ssh", "enabled": False},
    }
    (state_root / "obus_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    verifier.update({"role": role, "label": label, "machine_binding": _machine_binding()})
    (state_root / "access.json").write_text(json.dumps(verifier, indent=2), encoding="utf-8")
    if voice_path:
        (state_root / "voice-model-path.txt").write_text(str(voice_path.resolve()), encoding="utf-8")

    start = "@echo off\r\nset \"OBUS_HOME=%~dp0\"\r\nset \"OCCULTBUS_HOME=%OBUS_HOME%state\"\r\nset \"OBUS_ACCESS_CONFIG=%OCCULTBUS_HOME%\\access.json\"\r\nif exist \"%OCCULTBUS_HOME%\\voice-model-path.txt\" set /p \"OBUS_LOCAL_STT_MODEL_PATH=\"<\"%OCCULTBUS_HOME%\\voice-model-path.txt\"\r\nstart \"\" \"%OBUS_HOME%OBus.exe\"\r\n"
    (root / f"Start-OBus-{label}.cmd").write_text(start, encoding="ascii")
    print(f"Installed {label} {role} partner at: {root}")
    print(f"Peer route: {peer_label} ({peer_ip}) via Tailscale SSH guide")
    print("No SSH key, remote shell, or credential was created or copied.")


if __name__ == "__main__":
    raise SystemExit("Use a role-specific installer entry point.")
