"""Risk gate for requests that must never start as unattended work."""
from __future__ import annotations

import re


_MAJOR_RISK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "bulk_or_irrecoverable_deletion",
        re.compile(
            r"\b(?:delete|erase|wipe|destroy|purge|format)\b.{0,80}"
            r"\b(?:all|entire|recursive|recursively|drive|disk|volume|database|backups?|history)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "boot_firmware_or_disk_layout",
        re.compile(
            r"\b(?:bios|uefi|firmware|bootloader|partition table|diskpart|format-volume|clear-disk)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "hardware_safety_controls",
        re.compile(
            r"\b(?:overclock|overvolt|undervolt|fan curve|thermal limit|power[-_\s]?limit|flash (?:the )?(?:gpu|bios|firmware))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "security_or_recovery_disablement",
        re.compile(
            r"\b(?:disable|remove|bypass)\b.{0,80}"
            r"\b(?:antivirus|defender|firewall|bitlocker|recovery|backups?|audit logs?|sandbox|approvals?)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


def classify_major_risk(objective: str) -> list[str]:
    """Return deterministic risk categories that require local approval."""

    text = str(objective or "")[:65_536]
    return [name for name, pattern in _MAJOR_RISK_RULES if pattern.search(text)]
