"""Contrats de l'exercice : échec attendu tant que les fonctions restent à compléter.

Partie A : python -m unittest exercises.test_summary_cache.CacheStorageTests -v
Partie B : python -m unittest exercises.test_summary_cache.CacheValidityTests -v
Ces tests sont volontairement exclus de la commande CI `discover -s tests`.
"""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from copy import deepcopy
from pathlib import Path

from exercises.summary_cache import (
    SummaryCache,
    SummaryCacheEntry,
    is_cache_valid,
    source_hash,
)


def sample_history():
    return [
        {"role": "system", "content": "Assistant"},
        {"role": "user", "content": "Je m'appelle Lina."},
        {"role": "assistant", "content": "Bien reçu."},
        {"role": "user", "content": "Question suivante"},
    ]


def sample_entry():
    return SummaryCacheEntry(
        summary_text="L'utilisateur se présente comme Lina.",
        covered_until=3,
        source_hash=source_hash(sample_history(), 3),
        summarizer_fingerprint="qwen2.5:3b|summary-prompt-v1",
    )


class CacheStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "conversations.db"
        self.cache = SummaryCache(self.path)

    def test_missing_summary_returns_none(self):
        self.assertIsNone(self.cache.load("alice", "one"))

    def test_round_trip_preserves_all_fields_and_accents(self):
        entry = sample_entry()
        self.cache.save("alice", "one", entry)
        self.assertEqual(self.cache.load("alice", "one"), entry)

    def test_same_conversation_id_does_not_share_cache_between_users(self):
        entry = sample_entry()
        self.cache.save("alice", "one", entry)
        self.assertIsNone(self.cache.load("bob", "one"))
        self.assertIsNone(self.cache.load("alice", "two"))

    def test_update_replaces_existing_entry_without_duplicate(self):
        self.cache.save("alice", "one", sample_entry())
        updated = SummaryCacheEntry("Résumé corrigé.", 3, "new-hash", "prompt-v2")
        self.cache.save("alice", "one", updated)
        self.assertEqual(self.cache.load("alice", "one"), updated)
        with closing(sqlite3.connect(self.path)) as con:
            count = con.execute(
                "SELECT COUNT(*) FROM summaries WHERE user_id=? AND conversation_id=?",
                ("alice", "one"),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_new_instance_recovers_persisted_summary(self):
        self.cache.save("alice", "one", sample_entry())
        reopened = SummaryCache(self.path)
        self.assertEqual(reopened.load("alice", "one"), sample_entry())

    def test_sql_values_are_parameters(self):
        identity = "alice' OR 1=1 --"
        self.cache.save(identity, "one", sample_entry())
        self.assertEqual(self.cache.load(identity, "one"), sample_entry())
        self.assertIsNone(self.cache.load("alice", "one"))


class CacheValidityTests(unittest.TestCase):
    def test_absent_cache_is_invalid(self):
        self.assertFalse(
            is_cache_valid(None, sample_history(), sample_entry().summarizer_fingerprint)
        )

    def test_unchanged_source_and_summarizer_are_valid(self):
        entry = sample_entry()
        self.assertTrue(is_cache_valid(entry, sample_history(), entry.summarizer_fingerprint))

    def test_appended_messages_do_not_invalidate_covered_prefix(self):
        entry = sample_entry()
        extended = sample_history() + [
            {"role": "assistant", "content": "Réponse"},
            {"role": "user", "content": "Encore une question"},
        ]
        self.assertTrue(is_cache_valid(entry, extended, entry.summarizer_fingerprint))

    def test_changed_covered_message_invalidates_cache_without_mutating_history(self):
        entry = sample_entry()
        changed = sample_history()
        changed[1]["content"] = "Je m'appelle Karim."
        before = deepcopy(changed)
        self.assertFalse(is_cache_valid(entry, changed, entry.summarizer_fingerprint))
        self.assertEqual(changed, before)

    def test_changed_summarizer_invalidates_cache(self):
        self.assertFalse(is_cache_valid(sample_entry(), sample_history(), "prompt-v2"))

    def test_shortened_source_invalidates_cache_without_exception(self):
        entry = sample_entry()
        self.assertFalse(is_cache_valid(entry, sample_history()[:2], entry.summarizer_fingerprint))


if __name__ == "__main__":
    unittest.main()
