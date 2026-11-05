"""Vérifier le matériel du TP sans compléter ni exécuter le chargeur de l'apprenant."""

import unittest
from datetime import date
from pathlib import Path

from exercises.ingestion import read_manifest, resolve_source


class CorpusFixtureTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / "corpus" / "passerelle"
        self.records = read_manifest(self.root)

    def test_manifest_has_unique_ids_existing_utf8_sources_and_required_metadata(self):
        self.assertEqual(len(self.records), 6)
        self.assertEqual(len({r["doc_id"] for r in self.records}), 6)
        required = {
            "doc_id",
            "title",
            "language",
            "version",
            "status",
            "published_on",
            "access_groups",
            "source_path",
        }
        for record in self.records:
            with self.subTest(doc_id=record["doc_id"]):
                self.assertEqual(set(record), required)
                self.assertIn(record["language"], ("fr", "en"))
                self.assertIn(record["status"], ("current", "archived"))
                date.fromisoformat(record["published_on"])
                self.assertTrue(record["access_groups"])
                text = resolve_source(self.root, record["source_path"]).read_text(encoding="utf-8")
                self.assertTrue(text.strip())
                self.assertTrue("synthétique" in text or "synthetic" in text)

    def test_corpus_contains_bilingual_current_sources_archived_version_and_restricted_note(self):
        records = {r["doc_id"]: r for r in self.records}
        self.assertEqual(records["teletravail-fr-v2"]["status"], "current")
        self.assertEqual(records["teletravail-en-v2"]["version"], "2")
        self.assertEqual(records["teletravail-fr-v1"]["status"], "archived")
        self.assertEqual(records["note-rh-fr-v1"]["access_groups"], ["hr"])

    def test_source_resolution_refuses_outside_paths_and_unhandled_formats(self):
        for source in ("../outside.md", str(self.root / "teletravail_fr_v2.md"), "file.pdf"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                resolve_source(self.root, source)


if __name__ == "__main__":
    unittest.main()
