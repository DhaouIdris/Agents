"""La validation locale doit détecter les pertes observées, même après HTTP 200."""

import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from passerelle import ChatResult, Metrics


def load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_m3.py"
    spec = importlib.util.spec_from_file_location("m3_validation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveValidationTests(unittest.TestCase):
    def test_observed_summary_loss_and_wrong_count_are_detected(self):
        module = load_script()
        observed = "Vous travaillez à Lyon avec uniquement un CPU. Vous avez 24 dossiers fictifs."
        checks = module.check_fixture_facts(observed)
        self.assertFalse(checks["name_present"])
        self.assertFalse(checks["record_count_claim_consistent"])
        self.assertTrue(checks["city_present"])
        self.assertTrue(checks["hardware_present"])

    def test_live_control_flow_reports_success_and_failure_with_simulated_dependencies(self):
        module = load_script()

        def counter(messages):
            return sum(len(m["content"].split()) + 5 for m in messages) + 3

        for text, should_pass in (
            ("Lina works in Lyon and uses only a CPU.", True),
            ("Your message is incomplete. Please provide your name.", False),
        ):

            def generate(client, messages, **kwargs):
                return ChatResult(text, Metrics(0, None, 0, 0, 0, counter(messages), 10), "stop")

            output = io.StringIO()
            with (
                self.subTest(text=text),
                patch("passerelle.tokens.count_tokens", side_effect=counter),
                patch.object(module.OllamaClient, "generate", generate),
                redirect_stdout(output),
            ):
                if should_pass:
                    module.run_live(diagnose=True)
                else:
                    with self.assertRaises(SystemExit):
                        module.run_live()
            self.assertIn('"manual_review_required": true', output.getvalue())


if __name__ == "__main__":
    unittest.main()
