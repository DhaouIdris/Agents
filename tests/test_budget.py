"""Tests du sélecteur, sans tokenizer téléchargé ni appel à Ollama."""

import unittest
from copy import deepcopy

from passerelle.memory import fit_recent_context


def sample_history():
    return [
        {"role": "system", "content": "Assistant"},
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "R1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "R2"},
        {"role": "user", "content": "Q3"},
    ]


def fake_counter(messages):
    """Dix unités par message : valeurs contrôlées pour tester l'algorithme."""
    return 10 * len(messages)


class BudgetTests(unittest.TestCase):
    def fit(self, history, input_budget):
        return fit_recent_context(
            history,
            fake_counter,
            num_ctx=input_budget + 5,
            reserved_output=5,
            margin=0,
        )

    def test_all_messages_fit_including_exact_boundary(self):
        source = sample_history()
        self.assertEqual(self.fit(source, 60), source)

    def test_oldest_complete_pair_is_removed(self):
        source = sample_history()
        self.assertEqual(self.fit(source, 40), [source[0], *source[-3:]])

    def test_can_remove_all_pairs_but_preserves_system_and_question(self):
        source = sample_history()
        self.assertEqual(self.fit(source, 20), [source[0], source[-1]])

    def test_minimum_context_over_budget_raises(self):
        with self.assertRaisesRegex(ValueError, "dernière question"):
            self.fit(sample_history(), 19)

    def test_output_reservation_and_margin_are_both_accounted_for(self):
        source = sample_history()
        result = fit_recent_context(
            source,
            fake_counter,
            num_ctx=70,
            reserved_output=10,
            margin=20,
        )
        self.assertEqual(fake_counter(result), 40)

    def test_original_and_returned_messages_are_independent(self):
        source = sample_history()
        before = deepcopy(source)
        for budget in (20, 40, 60):
            returned = self.fit(source, budget)
            returned[0]["content"] = "modifié"
            returned[-1]["content"] = "modifié"
        self.assertEqual(source, before)

    def test_passed_counter_is_used_for_the_minimum_check_too(self):
        source = sample_history()
        result = fit_recent_context(
            source,
            len,
            num_ctx=5,
            reserved_output=1,
            margin=0,
        )
        self.assertEqual(result, [source[0], *source[-3:]])

    def test_zero_or_negative_available_budget_raises(self):
        for reserved, margin in [(20, 0), (15, 6)]:
            with self.subTest(reserved=reserved, margin=margin):
                with self.assertRaises(ValueError):
                    fit_recent_context(
                        sample_history(),
                        fake_counter,
                        num_ctx=20,
                        reserved_output=reserved,
                        margin=margin,
                    )

    def test_invalid_parameters_and_history_are_rejected(self):
        for params in ({"num_ctx": 0}, {"reserved_output": -1}, {"margin": -1}):
            with self.subTest(params=params):
                with self.assertRaises(ValueError):
                    fit_recent_context(sample_history(), fake_counter, **params)
        with self.assertRaises(ValueError):
            self.fit(sample_history()[:-1], 60)


if __name__ == "__main__":
    unittest.main()
