import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from passerelle import OllamaClient, OllamaError, Settings

MESSAGES = [{"role": "user", "content": "Bonjour"}]


def final_event(content="Bonjour", **extra):
    return {
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": "stop",
        "load_duration": 100_000_000,
        "prompt_eval_duration": 200_000_000,
        "eval_duration": 2_000_000_000,
        "prompt_eval_count": 12,
        "eval_count": 10,
        **extra,
    }


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient(Settings())
        self.response = MagicMock()
        self.response.__enter__.return_value = self.response

    def test_complete_response_and_server_metrics(self):
        self.response.json.return_value = final_event()
        with patch("passerelle.client.requests.post", return_value=self.response) as post:
            result = self.client.generate(MESSAGES)
        self.assertEqual(result.content, "Bonjour")
        self.assertEqual(result.metrics.generation_s, 2)
        self.assertEqual(result.metrics.tokens_per_second, 5)
        self.assertIsNone(result.metrics.first_content_s)
        payload = post.call_args.kwargs["json"]
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"]["num_ctx"], 2048)

    def test_stream_reconstructs_content_including_final_fragment(self):
        events = [
            b"",
            json.dumps({"message": {"content": "Bon"}, "done": False}).encode(),
            json.dumps(final_event("jour")).encode(),
        ]
        self.response.iter_lines.return_value = iter(events)
        fragments = []
        with patch("passerelle.client.requests.post", return_value=self.response):
            result = self.client.generate(MESSAGES, stream=True, on_token=fragments.append)
        self.assertEqual(result.content, "Bonjour")
        self.assertEqual(fragments, ["Bon", "jour"])
        self.assertIsNotNone(result.metrics.first_content_s)
        self.response.iter_lines.assert_called_once_with(chunk_size=1)

    def test_interrupted_stream_does_not_return_partial_success(self):
        self.response.iter_lines.return_value = [b'{"message":{"content":"partiel"},"done":false}']
        with patch("passerelle.client.requests.post", return_value=self.response):
            with self.assertRaisesRegex(OllamaError, "interrompu"):
                self.client.generate(MESSAGES, stream=True)

    def test_http_failure_is_actionable(self):
        with patch(
            "passerelle.client.requests.post", side_effect=requests.ConnectionError("offline")
        ):
            with self.assertRaisesRegex(OllamaError, "Vérifie qu'Ollama"):
                self.client.generate(MESSAGES)

    def test_api_error_and_empty_response_are_rejected(self):
        for event in ({"error": "model absent"}, final_event("")):
            with self.subTest(event=event):
                self.response.json.return_value = event
                with patch("passerelle.client.requests.post", return_value=self.response):
                    with self.assertRaises(OllamaError):
                        self.client.generate(MESSAGES)

    def test_invalid_stream_json_is_rejected(self):
        self.response.iter_lines.return_value = [b"not json"]
        with patch("passerelle.client.requests.post", return_value=self.response):
            with self.assertRaisesRegex(OllamaError, "JSON"):
                self.client.generate(MESSAGES, stream=True)

    def test_unknown_metrics_are_not_reported_as_zero(self):
        self.response.json.return_value = {
            "message": {"content": "OK"},
            "done": True,
            "done_reason": "stop",
        }
        with patch("passerelle.client.requests.post", return_value=self.response):
            metrics = self.client.generate(MESSAGES).metrics
        self.assertIsNone(metrics.load_s)
        self.assertIsNone(metrics.tokens_per_second)

    def test_truncation_is_explicit(self):
        self.response.json.return_value = final_event(done_reason="length")
        with patch("passerelle.client.requests.post", return_value=self.response):
            self.assertTrue(self.client.generate(MESSAGES).truncated)


if __name__ == "__main__":
    unittest.main()
