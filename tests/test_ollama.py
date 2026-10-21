import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

from brain.ollama_provider import OllamaProvider
from brain.provider import Message, ProviderError
from config import Settings


class Handler(BaseHTTPRequestHandler):
    body = {}
    code = 200
    payloads = []

    def do_GET(self):
        self.respond()

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).payloads.append(payload)
        self.respond()

    def respond(self):
        self.send_response(type(self).code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = type(self).body
        self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode("utf-8"))

    def log_message(self, *args):
        pass


class OllamaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        Handler.code = 200
        Handler.payloads = []
        Handler.body = {"model": "qwen3:4b", "message": {"role": "assistant", "content": "Meu nome é Max."},
                        "done": True, "done_reason": "stop"}
        self.provider = OllamaProvider(Settings(ollama_url=f"http://127.0.0.1:{self.server.server_port}"))

    def test_real_local_http_request_and_utf8(self):
        answer = self.provider.ask([Message("user", "Qual é o seu nome?")])
        self.assertEqual(answer.text, "Meu nome é Max.")
        payload = Handler.payloads[-1]
        self.assertEqual(payload["model"], "qwen3:4b")
        self.assertFalse(payload["think"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["messages"][-1]["content"], "Qual é o seu nome?\n/no_think")
        self.assertEqual(payload["messages"][0]["role"], "system")

    def test_health_detects_installed_model(self):
        Handler.body = {"models": [{"name": "qwen3:4b"}]}
        self.assertTrue(self.provider.available())

    def test_missing_model_is_reported_without_downloading(self):
        Handler.body = {"models": []}
        self.assertEqual(self.provider.health_check().code, "model_missing")
        self.assertEqual(Handler.payloads, [])

    def test_http_error_does_not_expose_server_body(self):
        Handler.code = 503
        Handler.body = {"error": "SECRET_TEST"}
        with self.assertRaises(ProviderError) as caught:
            self.provider.ask([Message("user", "Olá")])
        self.assertEqual(caught.exception.code, "http_503")
        self.assertNotIn("SECRET_TEST", str(caught.exception))

    def test_malformed_and_nonobject_json_are_rejected(self):
        for body in (b"{broken", [], b"\xff"):
            Handler.body = body
            with self.subTest(body=body), self.assertRaises(ProviderError):
                self.provider.ask([Message("user", "Olá")])

    def test_incomplete_empty_and_tool_responses_are_rejected(self):
        variants = [
            {"message": {"content": ""}, "done": True},
            {"message": {"content": "Parcial"}, "done": False},
            {"message": {"content": "Parcial"}, "done": True, "done_reason": "length"},
            {"message": {"content": "Executado", "tool_calls": [{"name": "shell"}]}, "done": True},
            {"message": {"content": "Interno</think>"}, "done": True},
            {"message": {"content": "<think>Interno"}, "done": True},
        ]
        for body in variants:
            Handler.body = body
            with self.subTest(body=body), self.assertRaises(ProviderError):
                self.provider.ask([Message("user", "Olá")])

    def test_internal_channel_is_never_returned(self):
        for text in ("<think>INTERNAL_TEST</think>Meu nome é Max.",
                     "INTERNAL_TEST</think>\nMeu nome é Max."):
            Handler.body["message"]["content"] = text
            answer = self.provider.ask([Message("user", "Olá")])
            self.assertEqual(answer.text, "Meu nome é Max.")

    def test_connection_error_is_sanitized(self):
        with patch.object(self.provider.http, "open", side_effect=URLError("SECRET_TEST")):
            health = self.provider.health_check()
        self.assertFalse(health.ok)
        self.assertNotIn("SECRET_TEST", health.detail)

    def test_redirect_does_not_send_prompt_to_another_server(self):
        from urllib.request import Request
        from brain.ollama_provider import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(Request("http://localhost"), None, 302, "", {}, "https://example.com"))
