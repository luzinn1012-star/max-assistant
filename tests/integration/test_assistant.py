import io
import logging
import unittest
from dataclasses import replace

from brain.provider import Answer, BrainProvider, Health, ProviderError
from config import Settings
from core.assistant import Assistant
from core.context import Conversation


class FakeProvider(BrainProvider):
    def __init__(self, name, *, healthy=True, fail=False):
        self.name = name
        self.healthy = healthy
        self.fail = fail
        self.calls = []
        self.checks = 0

    def health_check(self):
        self.checks += 1
        return Health(self.name, self.healthy, "test", "ok" if self.healthy else "offline")

    def ask(self, messages):
        self.calls.append(list(messages))
        if self.fail:
            raise ProviderError(self.name, "timeout", "Tempo esgotado.")
        return Answer("Meu nome é Max.", self.name, "test")


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.codex = FakeProvider("codex")
        self.ollama = FakeProvider("ollama")
        self.assistant = Assistant(Settings(), {"codex": self.codex, "ollama": self.ollama})

    def test_primary_success_does_not_call_fallback(self):
        reply = self.assistant.ask("Qual é o seu nome?")
        self.assertEqual(reply.provider, "codex")
        self.assertFalse(reply.fallback_used)
        self.assertEqual(self.ollama.calls, [])
        self.assertEqual(self.ollama.checks, 0)

    def test_unavailable_primary_uses_local_model(self):
        self.codex.healthy = False
        reply = self.assistant.ask("Olá")
        self.assertTrue(reply.fallback_used)
        self.assertEqual(reply.provider, "ollama")
        self.assertEqual(self.codex.calls, [])

    def test_runtime_failure_falls_back_with_same_context(self):
        self.assistant.ask("Minha cor de teste é azul.")
        self.codex.fail = True
        reply = self.assistant.ask("Qual era a cor?")
        self.assertTrue(reply.fallback_used)
        self.assertEqual(self.codex.calls[-1], self.ollama.calls[-1])
        self.assertEqual([m.role for m in self.ollama.calls[-1]], ["user", "assistant", "user"])

    def test_failed_request_does_not_pollute_context(self):
        self.codex.fail = self.ollama.fail = True
        with self.assertRaises(ProviderError):
            self.assistant.ask("Não guardar")
        self.assertEqual(len(self.assistant.context.for_request("Outra")), 1)
        self.assertIsNone(self.assistant.active_provider)

    def test_cooldown_avoids_repeated_primary_timeouts(self):
        self.codex.fail = True
        self.assistant.ask("Primeira")
        self.assistant.ask("Segunda")
        self.assertEqual(len(self.codex.calls), 1)
        self.assistant.retry()
        self.codex.fail = False
        self.assertEqual(self.assistant.ask("Terceira").provider, "codex")

    def test_explicit_provider_does_not_switch(self):
        self.assistant.settings = replace(Settings(), provider="codex")
        self.codex.fail = True
        with self.assertRaises(ProviderError):
            self.assistant.ask("Olá")
        self.assertEqual(self.ollama.calls, [])

    def test_reset_clears_conversation(self):
        self.assistant.ask("Primeira")
        self.assistant.reset()
        self.assistant.ask("Segunda")
        self.assertEqual(len(self.codex.calls[-1]), 1)

    def test_invalid_input_does_not_reach_provider(self):
        for text in (" ", "a" * 6001):
            with self.assertRaises(ValueError):
                self.assistant.ask(text)
        self.assertEqual(self.codex.calls, [])

    def test_logs_do_not_contain_user_text(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("max")
        previous = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        try:
            self.assistant.ask("Senha hipotética de teste: DO_NOT_LOG_THIS")
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous)
        self.assertIn("duration_ms=", stream.getvalue())
        self.assertNotIn("DO_NOT_LOG_THIS", stream.getvalue())
        self.assertNotIn("Senha", stream.getvalue())

    def test_context_retains_complete_recent_turns(self):
        context = Conversation(2, 20)
        context.commit("aaaa", "bbbb")
        context.commit("cccc", "dddd")
        context.commit("eeee", "ffff")
        messages = context.for_request("123456789")
        self.assertEqual([m.content for m in messages], ["eeee", "ffff", "123456789"])
