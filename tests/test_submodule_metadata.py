import configparser
import unittest
from pathlib import Path


class SubmoduleMetadataTests(unittest.TestCase):
    def test_every_indexed_submodule_has_a_reproducible_mapping(self):
        root = Path(__file__).resolve().parents[1]
        parser = configparser.ConfigParser()
        parser.read(root / ".gitmodules", encoding="utf-8")

        mappings = {
            parser[section]["path"]: parser[section]["url"]
            for section in parser.sections()
            if section.startswith("submodule ")
        }

        self.assertEqual(
            mappings,
            {
                "Understand-Anything": "https://github.com/Egonex-AI/Understand-Anything.git",
                "warp": "https://github.com/nvidia/warp.git",
                "third_party/warpdotdev-warp": "https://github.com/warpdotdev/warp.git",
            },
        )


if __name__ == "__main__":
    unittest.main()
