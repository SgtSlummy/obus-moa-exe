from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_build_script_uses_a_project_runtime_and_the_complete_spec():
    script = (ROOT / "tools" / "obus_launcher" / "build_and_install.ps1").read_text(encoding="utf-8")

    assert '.build-venv\\Scripts\\python.exe' in script
    assert '.venv\\Scripts\\python.exe' in script
    assert '$spec = Join-Path $repoRoot "OBus.spec"' in script
    assert '& $python -m PyInstaller $spec --noconfirm --clean' in script
    assert '[string]$OutputDirectory = ""' in script
    assert '--hidden-import backend.main' not in script


def test_readme_does_not_recommend_path_python_for_the_supported_build():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert '.\\tools\\obus_launcher\\build_and_install.ps1 -SkipInstall' in readme
    assert '-SkipInstall -PythonPath python' not in readme


def test_root_spec_does_not_declare_unused_template_engine_hidden_imports():
    spec = (ROOT / "OBus.spec").read_text(encoding="utf-8")

    assert '"jinja2.environment"' not in spec
    assert '"markupsafe"' not in spec
    assert '"faster_whisper"' in spec
    assert '"pystray._win32"' in spec
