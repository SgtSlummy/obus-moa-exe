from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_containerfile_runs_production_server_as_non_root() -> None:
    content = (ROOT / "Containerfile.podman").read_text(encoding="utf-8")

    assert content.startswith("FROM python:3.12-slim-bookworm")
    assert "USER obus" in content
    assert '"backend.main:app"' in content
    assert '"--host", "0.0.0.0"' in content
    assert "HEALTHCHECK" in content
    assert "pytest" not in content


def test_compose_profile_is_parallel_persistent_and_hardened() -> None:
    content = (ROOT / "compose.podman.yaml").read_text(encoding="utf-8")

    assert '127.0.0.1:${OBUS_PODMAN_PORT:-38183}:38173' in content
    assert "obus_podman_state:/var/lib/obus" in content
    assert "host.containers.internal:11434" in content
    assert "read_only: true" in content
    assert "no-new-privileges:true" in content
    assert "cap_drop:" in content and "- ALL" in content
    assert "38173:38173" not in content


def test_helper_preserves_native_service_and_state_volume() -> None:
    content = (ROOT / "scripts" / "obus_podman.ps1").read_text(encoding="utf-8")

    assert "HostPort = 38183" in content
    assert "native_service_untouched" in content
    assert '@("down", "--remove-orphans")' in content
    assert "--volumes" not in content
    assert "host.containers.internal:11434" in content


def test_readme_links_podman_pilot() -> None:
    content = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/podman.md" in content
