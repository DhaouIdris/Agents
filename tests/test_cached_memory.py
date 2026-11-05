"""Contrats du parcours M3 intégré ; aucun modèle, tokenizer ou réseau requis."""

import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

from passerelle import Assistant, ChatResult, Metrics, OllamaError, Settings, SQLiteStore
from passerelle.summary_cache import (
    SummaryCache,
    SummaryCacheEntry,
    is_cache_valid,
    make_summarizer_fingerprint,
    prepare_cached_context,
    refresh_summary_cache,
    select_context,
    source_hash,
)


def history_with_pairs(n, *, pending=True):
    messages = [{"role": "system", "content": "Assistant factuel."}]
    for i in range(n):
        messages.extend(
            [
                {"role": "user", "content": f"Question {i}"},
                {"role": "assistant", "content": f"Réponse {i}"},
            ]
        )
    if pending:
        messages.append({"role": "user", "content": "Question actuelle"})
    return messages


def response(text="Résumé", reason="stop"):
    return ChatResult(text, Metrics(1, None, None, None, None, None, None), reason)


def fake_counter(messages):
    return len(messages) * 10


class CachedMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "memory.db"
        self.cache = SummaryCache(self.path)
        self.generate = Mock(return_value=response())
        self.history = history_with_pairs(2)
        self.options = dict(num_ctx=80, reserved_output=20, summary_tokens=20, margin=10)

    def prepare(self, history=None, **overrides):
        options = {**self.options, **overrides}
        return prepare_cached_context(
            history if history is not None else self.history,
            self.cache,
            "alice",
            "one",
            "v1",
            fake_counter,
            self.generate,
            keep_pairs=1,
            **options,
        )

    def refresh(self, **overrides):
        return refresh_summary_cache(
            self.cache,
            "alice",
            "one",
            self.history,
            3,
            "v1",
            fake_counter,
            self.generate,
            **{**self.options, **overrides},
        )

    def test_full_history_fits_no_summary_and_no_shared_dicts(self):
        context = self.prepare(num_ctx=100)
        self.generate.assert_not_called()
        self.assertEqual(context, self.history)
        self.assertTrue(all(a is not b for a, b in zip(context, self.history)))

    def test_reuses_cache_for_identical_context_and_keeps_original_history(self):
        from exercises import summary_cache as exercise

        before = deepcopy(self.history)
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(first, second)
        self.assertEqual(self.generate.call_count, 1)
        self.assertEqual(self.history, before)
        self.assertEqual(len(first), 4)
        self.assertEqual(first[0], self.history[0])
        self.assertEqual(first[1:3], self.history[3:5])
        self.assertTrue(first[-1]["content"].endswith(self.history[-1]["content"]))
        self.assertIn("<conversation_summary>\nRésumé\n", first[-1]["content"])
        self.assertTrue(all(a is not b for a, b in zip(first[1:], self.history[3:])))
        self.assertEqual([m["role"] for m in first], ["system", "user", "assistant", "user"])
        request = self.generate.call_args.args[0]
        self.assertEqual(json.loads(request[1]["content"]), self.history[1:3])
        self.assertEqual(self.generate.call_args.kwargs, {"max_tokens": 20, "num_ctx": 80})
        # Vérifier aussi le contrôleur récemment poussé par l'apprenant.
        exercise_generate = Mock(return_value=response())
        for _ in range(2):
            exercise.prepare_cached_context(
                self.history,
                self.cache,
                "alice",
                "exercise",
                "v1",
                fake_counter,
                exercise_generate,
                keep_pairs=1,
                **self.options,
            )
        self.assertEqual(exercise_generate.call_count, 1)

    def test_cache_survives_reopening(self):
        self.prepare()
        self.cache = SummaryCache(self.path)
        self.prepare()
        self.assertEqual(self.generate.call_count, 1)

    def test_cache_partition_and_sql_bound_values(self):
        self.prepare()
        entry = self.cache.load("alice", "one")
        self.assertIsNone(self.cache.load("bob", "one"))
        self.assertIsNone(self.cache.load("alice", "two"))
        self.cache.save("alice' OR 1=1 --", "one", replace(entry, summary_text="autre"))
        self.assertEqual(self.cache.load("alice", "one"), entry)

    def test_upsert_updates_without_duplicate(self):
        self.prepare()
        entry = self.cache.load("alice", "one")
        updated = replace(entry, summary_text="Corrigé")
        self.cache.save("alice", "one", updated)
        self.assertEqual(SummaryCache(self.path).load("alice", "one"), updated)

    def test_changed_source_and_summarizer_invalidate_cache(self):
        self.prepare()
        entry = self.cache.load("alice", "one")
        extended = self.history + [
            {"role": "assistant", "content": "Réponse"},
            {"role": "user", "content": "Suite"},
        ]
        self.assertTrue(is_cache_valid(entry, extended, "v1"))
        self.assertFalse(is_cache_valid(entry, self.history[:2], "v1"))
        self.assertFalse(is_cache_valid(entry, self.history, "v2"))
        self.history[1]["content"] = "Correction du message ancien"
        self.assertFalse(is_cache_valid(entry, self.history, "v1"))
        self.prepare()
        self.assertEqual(self.generate.call_count, 2)

    def test_invalid_cache_is_not_selected(self):
        entry = SummaryCacheEntry("Ancien résumé", 3, "faux-hash", "v1")
        for candidate in (None, entry):
            self.assertIsNone(
                select_context(
                    self.history,
                    candidate,
                    "v1",
                    fake_counter,
                    num_ctx=80,
                    reserved_output=20,
                    margin=10,
                )
            )

    def test_summary_errors_preserve_existing_cache(self):
        self.prepare()
        before = self.cache.load("alice", "one")
        for result in (response("Texte", "length"), response("   ")):
            self.generate.return_value = result
            with self.assertRaises(RuntimeError):
                self.refresh()
            self.assertEqual(self.cache.load("alice", "one"), before)
        self.generate.side_effect = OllamaError("Connexion interrompue")
        with self.assertRaises(OllamaError):
            self.refresh()
        self.assertEqual(self.cache.load("alice", "one"), before)

    def test_final_context_over_budget_preserves_cache(self):
        self.prepare()
        before = self.cache.load("alice", "one")
        self.generate.return_value = response("Autre résumé")
        with self.assertRaisesRegex(ValueError, "contexte résumé"):
            self.refresh(num_ctx=65)
        self.assertEqual(self.cache.load("alice", "one"), before)

    def test_summary_input_over_budget_fails_before_model_or_write(self):
        self.prepare()
        before = self.cache.load("alice", "one")
        self.generate.reset_mock()

        def counter(messages):
            if messages[0]["content"] == self.history[0]["content"]:
                return 10 * len(messages)
            return 1000  # Le prompt du résumeur et le JSON comptent aussi.

        with self.assertRaisesRegex(ValueError, "résumer trop volumineuse"):
            refresh_summary_cache(
                self.cache,
                "alice",
                "one",
                self.history,
                3,
                "v1",
                counter,
                self.generate,
                **self.options,
            )
        self.generate.assert_not_called()
        self.assertEqual(self.cache.load("alice", "one"), before)

    def test_oversized_system_and_question_fail_before_model(self):
        with self.assertRaisesRegex(ValueError, "système et la question"):
            self.prepare(num_ctx=45, summary_tokens=10)
        self.generate.assert_not_called()

    def test_no_old_pair_and_bad_settings_fail_before_model(self):
        with self.assertRaisesRegex(ValueError, "Aucun couple"):
            self.prepare(history=history_with_pairs(1), num_ctx=60, summary_tokens=10)
        for overrides in ({"margin": -1}, {"reserved_output": -1}, {"summary_tokens": 0}):
            with self.assertRaises(ValueError):
                self.prepare(**overrides)
        self.generate.assert_not_called()

    def test_coverage_cannot_end_after_user_or_only_system(self):
        for invalid in (True, 1, 2, 4, 99):
            with self.assertRaises(ValueError):
                source_hash(self.history, invalid)

    def test_fingerprint_depends_on_model_prompt_version_and_generation_settings(self):
        settings = Settings()
        original = make_summarizer_fingerprint(settings)
        self.assertNotEqual(original, make_summarizer_fingerprint(settings, "v2"))
        for changed in (replace(settings, model="autre"), replace(settings, summary_tokens=128)):
            self.assertNotEqual(original, make_summarizer_fingerprint(changed))


class CachedAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "conversation.db"
        self.store = SQLiteStore(self.path)
        self.client = Mock()
        self.client.settings = Settings(num_ctx=100, max_tokens=20, summary_tokens=20)
        self.client.generate.return_value = response()
        self.assistant = self.new_assistant()
        self.initial_history = history_with_pairs(3, pending=False)
        self.store.save("alice", "one", self.initial_history)

    def new_assistant(self):
        return Assistant(
            self.client,
            SQLiteStore(self.path),
            max_pairs=1,
            token_counter=fake_counter,
            margin=10,
        )

    def test_growth_reuses_then_refreshes_cache_and_retains_full_history(self):
        self.assistant.chat("alice", "one", "Question A", stream=False)
        self.assertEqual(self.client.generate.call_count, 2)  # Résumé + réponse.
        first = self.assistant.summary_cache.load("alice", "one")
        self.assertEqual(first.covered_until, 5)
        self.assistant.chat("alice", "one", "Question B", stream=False)
        self.assertEqual(self.client.generate.call_count, 3)  # Réponse seule.
        self.assertEqual(self.assistant.summary_cache.load("alice", "one"), first)
        self.assistant.chat("alice", "one", "Question C", stream=False)
        self.assertEqual(self.client.generate.call_count, 5)  # Nouveau résumé + réponse.
        updated = self.assistant.summary_cache.load("alice", "one")
        self.assertEqual(updated.covered_until, 9)
        saved = self.store.load("alice", "one")
        self.assertEqual(saved[:7], self.initial_history)
        self.assertEqual(len(saved), 13)
        self.assertFalse(any("Résumé des échanges" in m["content"] for m in saved))
        for call in self.client.generate.call_args_list:
            self.assertLessEqual(fake_counter(call.args[0]) + 20 + 10, 100)
            if "max_tokens" in call.kwargs:
                self.assertEqual(call.kwargs["num_ctx"], 100)

    def test_restart_reuses_cache_and_other_users_do_not_receive_it(self):
        self.assistant.chat("alice", "one", "Question A", stream=False)
        reopened = self.new_assistant()
        reopened.chat("alice", "one", "Question B", stream=False)
        self.assertEqual(self.client.generate.call_count, 3)
        reopened.chat("bob", "one", "Bonjour", stream=False)
        self.assertIsNone(reopened.summary_cache.load("bob", "one"))
        sent = self.client.generate.call_args.args[0]
        self.assertEqual(len(sent), 2)
        self.assertNotIn("Résumé", sent[1]["content"])

    def test_summary_failure_does_not_save_turn_or_replace_cache(self):
        self.assistant.chat("alice", "one", "Question A", stream=False)
        self.assistant.chat("alice", "one", "Question B", stream=False)
        before = self.store.load("alice", "one")
        old_cache = self.assistant.summary_cache.load("alice", "one")
        self.client.generate.return_value = response("incomplet", "length")
        with self.assertRaises(RuntimeError):
            self.assistant.chat("alice", "one", "Question C", stream=False)
        self.assertEqual(self.store.load("alice", "one"), before)
        self.assertEqual(self.assistant.summary_cache.load("alice", "one"), old_cache)

    def test_answer_failure_keeps_history_and_valid_derivative_cache(self):
        self.client.generate.side_effect = [
            response("Résumé valable"),
            OllamaError("Erreur réponse"),
        ]
        with self.assertRaises(OllamaError):
            self.assistant.chat("alice", "one", "Question A", stream=False)
        self.assertEqual(self.store.load("alice", "one"), self.initial_history)
        entry = self.assistant.summary_cache.load("alice", "one")
        self.assertTrue(
            is_cache_valid(entry, self.initial_history, self.assistant.summarizer_fingerprint)
        )

    def test_another_model_requires_an_explicit_counter(self):
        self.client.settings = Settings(model="autre-modèle")
        with self.assertRaisesRegex(ValueError, "token_counter"):
            Assistant(self.client, self.store)

    def test_recent_mode_sends_original_recent_pairs_without_summary_generation(self):
        self.assistant.chat("alice", "one", "Question actuelle", mode="recent", stream=False)
        self.assertEqual(self.client.generate.call_count, 1)
        sent = self.client.generate.call_args.args[0]
        self.assertEqual(sent[0], self.initial_history[0])
        self.assertEqual(sent[1:-1], self.initial_history[3:])
        self.assertEqual(sent[-1], {"role": "user", "content": "Question actuelle"})
        self.assertLessEqual(fake_counter(sent) + 20 + 10, 100)
        self.assertIsNone(self.assistant.summary_cache.load("alice", "one"))
        saved = self.store.load("alice", "one")
        self.assertEqual(saved[:7], self.initial_history)
        self.assertEqual(len(saved), 9)

    def test_recent_mode_refuses_irreducible_oversize_without_saving_or_generating(self):
        self.assistant.token_counter = lambda messages: 1000
        with self.assertRaisesRegex(ValueError, "système et la dernière question"):
            self.assistant.chat("alice", "one", "Trop long", mode="recent", stream=False)
        self.client.generate.assert_not_called()
        self.assertEqual(self.store.load("alice", "one"), self.initial_history)


if __name__ == "__main__":
    unittest.main()
