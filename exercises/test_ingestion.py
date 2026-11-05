"""Contrats M4.1 : à lancer explicitement après implémentation du chargeur."""

import hashlib
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from exercises.ingestion import Document, load_document


class LoadDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "corpus"
        self.root.mkdir()
        self.raw = "# Politique\r\n\r\nÉquipement et été.  \r\n".encode("utf-8")
        (self.root / "source.md").write_bytes(self.raw)
        self.metadata = {
            "doc_id": "policy-fr-v2",
            "title": "Politique équipement",
            "language": "fr",
            "version": "2",
            "status": "current",
            "published_on": "2026-04-01",
            "access_groups": ["staff", "hr"],
            "source_path": "source.md",
        }

    def test_loads_all_metadata_with_source_text_and_byte_hash(self):
        doc = load_document(self.root, self.metadata)
        expected = Document(
            doc_id="policy-fr-v2",
            title="Politique équipement",
            language="fr",
            version="2",
            status="current",
            published_on="2026-04-01",
            access_groups=("staff", "hr"),
            source_path="source.md",
            text=self.raw.decode("utf-8"),
            content_hash=hashlib.sha256(self.raw).hexdigest(),
        )
        self.assertEqual(doc, expected)

    def test_preserves_accents_whitespace_and_original_line_endings(self):
        doc = load_document(self.root, self.metadata)
        self.assertEqual(doc.text.encode("utf-8"), self.raw)
        self.assertIn("Équipement", doc.text)
        self.assertTrue(doc.text.endswith("  \r\n"))

    def test_metadata_is_not_mutated_and_groups_are_immutable(self):
        before = deepcopy(self.metadata)
        doc = load_document(self.root, self.metadata)
        self.assertEqual(self.metadata, before)
        self.assertIsInstance(doc.access_groups, tuple)
        self.metadata["access_groups"].append("other")
        self.assertEqual(doc.access_groups, ("staff", "hr"))

    def test_changed_bytes_change_hash_but_not_declared_identity(self):
        first = load_document(self.root, self.metadata)
        (self.root / "source.md").write_bytes(self.raw + b"nouvelle ligne\n")
        second = load_document(self.root, self.metadata)
        self.assertNotEqual(first.content_hash, second.content_hash)
        self.assertEqual(first.doc_id, second.doc_id)
        self.assertEqual(replace(first, text=second.text, content_hash=second.content_hash), second)

    def test_preserves_archived_status_and_restricted_groups_without_filtering(self):
        meta = {**self.metadata, "status": "archived", "access_groups": ["hr"]}
        doc = load_document(self.root, meta)
        self.assertEqual(doc.status, "archived")
        self.assertEqual(doc.access_groups, ("hr",))

    def test_missing_source_raises_file_not_found(self):
        meta = {**self.metadata, "source_path": "absent.md"}
        with self.assertRaises(FileNotFoundError):
            load_document(self.root, meta)

    def test_invalid_utf8_is_not_silently_replaced(self):
        (self.root / "source.md").write_bytes(b"\xff\xfe")
        with self.assertRaises(UnicodeDecodeError):
            load_document(self.root, self.metadata)

    def test_escaping_path_is_rejected_before_reading(self):
        (self.root.parent / "outside.md").write_text("hors corpus", encoding="utf-8")
        meta = {**self.metadata, "source_path": "../outside.md"}
        with self.assertRaises(ValueError):
            load_document(self.root, meta)


if __name__ == "__main__":
    unittest.main()
