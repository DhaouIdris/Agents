import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from passerelle import Assistant, ChatResult, Metrics, OllamaError, Settings, SQLiteStore


def response(text="Réponse", reason="stop"):
    return ChatResult(text, Metrics(1, None, None, None, None, None, None), reason)


class StorageAndAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "data" / "conversations.db"
        self.store = SQLiteStore(self.path)
        self.client = Mock()
        self.client.settings = Settings()
        self.client.generate.return_value = response()
        self.assistant = Assistant(self.client, self.store)

    def test_persistence_and_user_conversation_partition(self):
        self.assistant.chat("alice", "same", "Je m'appelle Lina.", stream=False)
        self.assistant.chat("bob", "same", "Je m'appelle Karim.", stream=False)
        reopened = SQLiteStore(self.path)
        self.assertEqual(reopened.load("alice", "same")[1]["content"], "Je m'appelle Lina.")
        self.assertEqual(reopened.load("bob", "same")[1]["content"], "Je m'appelle Karim.")
        self.assertIsNone(reopened.load("alice", "other"))
        self.assertIsNone(reopened.load("other", "same"))

    def test_sql_values_are_bound_and_updates_do_not_create_duplicate_rows(self):
        key = "alice' OR 1=1 --"
        self.store.save(key, "same", [{"role": "system", "content": "été"}])
        self.store.save(key, "same", [{"role": "system", "content": "mise à jour"}])
        self.assertEqual(self.store.load(key, "same")[0]["content"], "mise à jour")
        self.assertIsNone(self.store.load("alice", "same"))

    def test_failure_does_not_save_user_or_partial_assistant_turn(self):
        self.assistant.chat("alice", "one", "Bonjour", stream=False)
        before = self.store.load("alice", "one")
        self.client.generate.side_effect = OllamaError("interrompu")
        with self.assertRaises(OllamaError):
            self.assistant.chat("alice", "one", "Question suivante")
        self.assertEqual(self.store.load("alice", "one"), before)
        with self.assertRaises(OllamaError):
            self.assistant.chat("bob", "new", "Bonjour")
        self.assertIsNone(self.store.load("bob", "new"))

    def test_truncated_answer_is_not_saved(self):
        self.client.generate.return_value = response(reason="length")
        with self.assertRaisesRegex(OllamaError, "tour non sauvegardé"):
            self.assistant.chat("alice", "one", "Bonjour")
        self.assertIsNone(self.store.load("alice", "one"))

    def test_summary_does_not_replace_full_history_in_sqlite(self):
        self.assistant = Assistant(self.client, self.store, max_pairs=1)
        self.assistant.chat("alice", "one", "Mon prénom est Lina", stream=False)
        self.assistant.chat("alice", "one", "Je travaille sans GPU", stream=False)
        self.client.generate.side_effect = [response("Lina."), response("Votre prénom est Lina.")]
        self.assistant.chat("alice", "one", "Mon prénom ?", stream=False)
        saved = self.store.load("alice", "one")
        self.assertEqual(len(saved), 7)
        self.assertEqual(saved[1]["content"], "Mon prénom est Lina")
        self.assertFalse(any("Note de continuité" in m["content"] for m in saved))

    def test_reopening_store_does_not_reset_existing_conversation(self):
        self.assistant.chat("alice", "one", "Je m'appelle Lina", stream=False)
        second = Assistant(self.client, SQLiteStore(self.path))
        second.chat("alice", "one", "Mon prénom ?", stream=False)
        sent = self.client.generate.call_args.args[0]
        self.assertIn("Lina", sent[1]["content"])
        self.assertEqual(len(self.store.load("alice", "one")), 5)

    def test_bad_input_and_saved_incomplete_turn_fail_before_model_call(self):
        for user, conv, text in [
            ("", "one", "Bonjour"),
            ("alice", "", "Bonjour"),
            ("alice", "one", " "),
        ]:
            with self.assertRaises(ValueError):
                self.assistant.chat(user, conv, text)
        self.store.save(
            "alice",
            "one",
            [
                {"role": "system", "content": "Assistant"},
                {"role": "user", "content": "Tour inachevé"},
            ],
        )
        with self.assertRaisesRegex(ValueError, "inachevé"):
            self.assistant.chat("alice", "one", "Suite")
        self.client.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
