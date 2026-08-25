import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_thor_loki_pair import build


class ThorLokiPairBuildTests(unittest.TestCase):
    def test_build_creates_matching_private_pair_with_strong_unique_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "OBus.exe"
            executable.write_bytes(b"verified-executable")
            output = root / "OBus-Thor-Loki-Paired"

            archive = build(executable, output, "Thor Prime", "Loki Node", "http://100.73.36.108:8000")

            loki = json.loads((output / "Loki-Portal" / "thor-loki.pairing.json").read_text(encoding="utf-8"))
            thor = json.loads((output / "Thor-Client" / "thor-loki.pairing.json").read_text(encoding="utf-8"))
            self.assertEqual(loki, thor)
            self.assertEqual(loki["thor"]["name"], "Thor Prime")
            self.assertEqual(loki["loki"]["name"], "Loki Node")
            self.assertEqual(loki["loki"]["portal_url"], "http://100.73.36.108:8000")
            self.assertGreaterEqual(len(loki["portal_key"]), 43)
            self.assertNotIn(loki["portal_key"], (output / "PRIVATE-README.txt").read_text(encoding="utf-8"))
            self.assertTrue((output / "Loki-Portal" / "OBus.exe").is_file())
            startup = (output / "Loki-Portal" / "Start-Loki-Portal.ps1").read_text(encoding="utf-8")
            self.assertIn("$env:OBUS_PORT = '8000'", startup)
            self.assertIn("-ArgumentList '--serve'", startup)
            self.assertIn("/api/portal/thor/status", startup)
            self.assertIn("did not become ready", startup)
            self.assertTrue((output / "SHA256SUMS.txt").is_file())
            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())
            self.assertIn("OBus-Thor-Loki-Paired/Loki-Portal/OBus.exe", names)
            self.assertIn("OBus-Thor-Loki-Paired/Thor-Client/thor-loki.pairing.json", names)

    def test_build_rejects_non_http_portal_url(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "OBus.exe"
            executable.write_bytes(b"exe")
            with self.assertRaises(ValueError):
                build(executable, root / "out", "Thor", "Loki", "file:///secret")


if __name__ == "__main__":
    unittest.main()
