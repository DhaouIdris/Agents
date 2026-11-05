import json
import unittest
from copy import deepcopy
from unittest.mock import Mock

from passerelle import ChatResult, ContextManager, Metrics, OllamaError, Settings, build_context
from passerelle.memory import summarize_history


def history():
    return [
        {"role": "system", "content": "Assistant"},
        {"role": "user", "content": "Je m'appelle Lina, sans GPU."},
        {"role": "assistant", "content": "Bien reçu."},
        {"role": "user", "content": "Réponds en français."},
        {"role": "assistant", "content": "Entendu."},
        {"role": "user", "content": "Mon prénom et ma contrainte ?"},
    ]


def result(content="Lina travaille sans GPU.", reason="stop"):
    return ChatResult(content, Metrics(1, None, None, None, None, None, None), reason)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.settings = Settings()
        self.client.generate.return_value = result()

    def test_window_preserves_system_latest_question_and_complete_pairs(self):
        source = history()
        self.assertEqual(build_context(source, 1), [source[0], *source[-3:]])
        self.assertEqual(build_context(source, 0), [source[0], source[-1]])
        self.assertEqual(build_context(source, 10), source)

    def test_returned_messages_do_not_alias_original_history(self):
        source = history()
        before = deepcopy(source)
        for pairs in (0, 1, 10):
            context = build_context(source, pairs)
            context[0]["content"] = "modifié"
            context[-1]["content"] = "modifié"
        self.assertEqual(source, before)

    def test_summary_receives_only_dropped_prefix(self):
        source = history()
        prepared = ContextManager(self.client, max_pairs=1).prepare(source)
        sent = self.client.generate.call_args.args[0]
        self.assertEqual(json.loads(sent[1]["content"]), source[1:3])
        self.assertEqual(prepared.messages[0], source[0])
        self.assertEqual(prepared.messages[-3:], source[-3:])
        self.assertEqual(prepared.messages[1]["role"], "user")
        self.assertEqual(prepared.omitted_messages, 2)
        self.assertEqual(prepared.summary, "Lina travaille sans GPU.")

    def test_no_summary_request_when_all_messages_fit_or_mode_is_window(self):
        ContextManager(self.client, 10).prepare(history())
        ContextManager(self.client, 1).prepare(history(), "window")
        ContextManager(self.client, 1).prepare(history(), "full")
        self.client.generate.assert_not_called()

    def test_summary_rejects_empty_and_truncated_output(self):
        for generated in (result(""), result(reason="length")):
            with self.subTest(generated=generated):
                self.client.generate.return_value = generated
                with self.assertRaises(OllamaError):
                    summarize_history(history(), self.client)

    def test_system_only_history_does_not_call_summarizer(self):
        self.assertEqual(summarize_history(history()[:1], self.client), "")
        self.client.generate.assert_not_called()

    def test_invalid_history_and_configuration_are_rejected(self):
        cases = [[], history()[1:], history()[:-1], history() + [history()[1]]]
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    build_context(source)
        for pairs in (-1, 1.5, True):
            with self.subTest(pairs=pairs):
                with self.assertRaises(ValueError):
                    build_context(history(), pairs)


if __name__ == "__main__":
    unittest.main()
