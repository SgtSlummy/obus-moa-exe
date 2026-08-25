import unittest
from pathlib import Path


class ThorDeploymentPackageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.package_dir = self.root / "deploy" / "thor-loki"

    def test_thor_deployment_templates_are_present_and_secret_safe(self):
        required = {
            "Install-OBus-Thor.ps1",
            "Start-OBus-Thor.cmd",
            "Test-Loki-Route.ps1",
            "thor-loki-state.json",
            "README.md",
            "Enable-OBus-Thor-Portal.ps1",
            "Invoke-OBus-Portal.ps1",
        }
        self.assertEqual({path.name for path in self.package_dir.iterdir()}, required)

        combined = "\n".join((self.package_dir / name).read_text(encoding="utf-8") for name in required)
        self.assertIn("100.73.36.108", combined)
        self.assertIn("OBUS_LOCAL_STT_MODEL_PATH", combined)
        self.assertIn("OCCULTBUS_HOME", combined)
        self.assertIn("guide-only", combined)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", combined)
        self.assertNotIn("PRIVATE KEY-----", combined)
        self.assertNotIn("ssh-rsa ", combined)

    def test_thor_installer_requires_an_explicit_existing_voice_model_path(self):
        installer = (self.package_dir / "Install-OBus-Thor.ps1").read_text(encoding="utf-8")
        self.assertIn("LocalSttModelPath", installer)
        self.assertIn("Test-Path -LiteralPath $LocalSttModelPath", installer)
        self.assertNotIn("huggingface", installer.lower())
        self.assertNotIn("download", installer.lower())


if __name__ == "__main__":
    unittest.main()
