import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.memory_hub import MemoryHub


class MemoryHubTests(unittest.TestCase):
    def test_reports_each_local_memory_source_without_exposing_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            obus = root / "obus-memory.json"
            obus.write_text(json.dumps([{"id": "o1", "text": "local routing fact"}]), encoding="utf-8")
            hermes = root / "MEMORY.md"
            hermes.write_text("# Memory\n\n- Hermes routing fact\n", encoding="utf-8")
            mem0 = root / "mem0.db"
            connection = sqlite3.connect(mem0)
            connection.execute("create table history (id integer)")
            connection.execute("create table messages (id integer, content text)")
            connection.execute("insert into history values (1)")
            connection.execute("insert into messages values (1, 'mem0 fact')")
            connection.commit()
            connection.close()
            tarot = root / "tarot.sqlite3"
            tarot.write_bytes(b"sqlite")

            hub = MemoryHub(
                obus_memory=obus,
                hermes_memory=hermes,
                mempalace_root=root / "missing-mempalace",
                mempalace_palace=root / "empty-palace",
                mem0_db=mem0,
                tarot_db=tarot,
                mythos_root=root / "mythos",
                moa_root=root / "moa",
            )
            report = hub.status()

            self.assertEqual(report["obus"]["chunks"], 1)
            self.assertEqual(report["hermes"]["lines"], 3)
            self.assertEqual(report["mem0"]["messages"], 1)
            self.assertEqual(report["tarot_rag"]["present"], True)
            self.assertNotIn("local routing fact", json.dumps(report))

    def test_search_merges_obus_and_hermes_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            obus = root / "obus-memory.json"
            obus.write_text(json.dumps([{"id": "o1", "text": "shared integration decision"}]), encoding="utf-8")
            hermes = root / "MEMORY.md"
            hermes.write_text("- shared integration preference\n", encoding="utf-8")
            hub = MemoryHub(
                obus_memory=obus,
                hermes_memory=hermes,
                mempalace_root=root / "missing-mempalace",
                mempalace_palace=root / "empty-palace",
                mem0_db=root / "missing.db",
                tarot_db=root / "missing.sqlite3",
                mythos_root=root / "mythos",
                moa_root=root / "moa",
            )

            results = hub.search("shared integration")
            sources = {item["source"] for item in results}
            self.assertEqual(sources, {"obus", "hermes"})
            self.assertTrue(all("text" in item for item in results))

    def test_search_includes_indexed_mempalace_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            palace = root / "palace"
            palace.mkdir()
            (palace / "chroma.sqlite3").write_bytes(b"indexed")
            cli = root / "mempalace" / ".venv" / "Scripts" / "python.exe"
            cli.parent.mkdir(parents=True)
            cli.write_bytes(b"python")
            hub = MemoryHub(
                obus_memory=root / "missing.json",
                hermes_memory=root / "missing.md",
                mempalace_root=root / "mempalace",
                mempalace_palace=palace,
                mem0_db=root / "missing.db",
                tarot_db=root / "missing.sqlite3",
                mythos_root=root / "mythos",
                moa_root=root / "moa",
            )
            with mock.patch("backend.memory_hub.subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0, stdout="[1] Indexed memory result\n", stderr="")
                results = hub.search("indexed")
            self.assertEqual(results, [{"source": "mempalace", "text": "Indexed memory result"}])
            command = run.call_args.args[0]
            self.assertIn("search", command)
            self.assertIn("--results", command)

    def test_search_includes_tarot_rag_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tarot = root / "rag.sqlite3"
            connection = sqlite3.connect(tarot)
            connection.execute("create virtual table chunks using fts5(path, chunk_no UNINDEXED, content)")
            connection.execute("insert into chunks(path, chunk_no, content) values ('router.md', 1, 'tarot routing integration')")
            connection.commit()
            connection.close()
            hub = MemoryHub(
                obus_memory=root / "missing.json",
                hermes_memory=root / "missing.md",
                mempalace_root=root / "missing-mempalace",
                mempalace_palace=root / "empty-palace",
                mem0_db=root / "missing.db",
                tarot_db=tarot,
                mythos_root=root / "mythos",
                moa_root=root / "moa",
            )
            results = hub.search("tarot integration")
            self.assertEqual(results, [{"source": "tarot_rag", "path": "router.md", "chunk": 1, "text": "tarot routing integration"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
