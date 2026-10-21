import io
import logging
import unittest
from dataclasses import replace
from unittest.mock import patch

from config import ConfigError, Settings
from core.assistant import Assistant
from core.intent import Intent, Rule
from core.permissions import RiskLevel
from skills.base import Skill, SkillError, SkillResult
from skills.bootstrap import build_registry
from tests.phase2_doubles import FakeAudio, FakeWindows, SpyBrain


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeWindows()
        self.audio = FakeAudio()
        self.codex = SpyBrain("codex")
        self.ollama = SpyBrain("ollama")
        self.settings = Settings()
        self.registry = build_registry(self.settings, self.backend, lambda: self.audio)
        self.assistant = Assistant(
            self.settings, {"codex": self.codex, "ollama": self.ollama}, self.registry
        )

    def assert_no_brain(self):
        self.assertEqual(self.codex.ask_calls, [])
        self.assertEqual(self.ollama.ask_calls, [])
        self.assertEqual(self.codex.health_calls, 0)
        self.assertEqual(self.ollama.health_calls, 0)

    def test_acceptance_commands_use_skills_without_any_brain_calls(self):
        expected = [
            ("Max, abra o Spotify.", "open_app", "apps"),
            ("Max, abra o Discord.", "open_app", "apps"),
            ("Max, abra Downloads.", "open_folder", "folders"),
            ("Max, volume 30.", "set_volume", "volume"),
            ("Max, mute.", "mute_volume", "volume"),
            ("Max, como está o PC?", "system_status", "system"),
            ("Max, tira do mudo.", "unmute_volume", "volume"),
            ("ajuda", "help", "help"),
        ]
        for text, intent, skill in expected:
            with self.subTest(text=text):
                reply = self.assistant.ask(text)
                self.assertTrue(reply.success)
                self.assertEqual(reply.route, "local")
                self.assertEqual(reply.intent, intent)
                self.assertEqual(reply.skill, skill)
                self.assertFalse(reply.llm_used)
                self.assert_no_brain()

    def test_local_result_does_not_pollute_brain_context(self):
        self.assistant.ask("abra spotify")
        self.assistant.ask("explique relatividade")
        self.assertEqual(len(self.codex.ask_calls[0]), 1)
        self.assertEqual(self.codex.ask_calls[0][0].content, "explique relatividade")

    def test_low_confidence_calls_codex(self):
        reply = self.assistant.ask("abra programa desconhecido")
        self.assertEqual(reply.route, "brain")
        self.assertEqual(reply.provider, "codex")
        self.assertTrue(reply.llm_used)
        self.assertEqual(len(self.codex.ask_calls), 1)
        self.assertEqual(self.backend.calls, [])

    def test_unknown_calls_codex(self):
        reply = self.assistant.ask("Max, explique relatividade.")
        self.assertEqual(reply.intent, "unknown")
        self.assertEqual(reply.provider, "codex")
        self.assertEqual(len(self.codex.ask_calls), 1)

    def test_codex_failure_falls_back_to_ollama(self):
        self.codex.fail = True
        reply = self.assistant.ask("Max, explique relatividade.")
        self.assertEqual(reply.provider, "ollama")
        self.assertTrue(reply.fallback_used)
        self.assertEqual(self.codex.ask_calls[0], self.ollama.ask_calls[0])
        self.assertEqual(self.backend.calls, [])

    def test_forced_ollama_affects_conversation_only(self):
        self.assistant.settings = replace(self.settings, provider="ollama")
        local = self.assistant.ask("volume 30")
        self.assertEqual(local.provider, "local")
        self.assert_no_brain()
        brain = self.assistant.ask("Explique uma API.")
        self.assertEqual(brain.provider, "ollama")
        self.assertEqual(self.codex.ask_calls, [])

    def test_configured_threshold_prevents_execution(self):
        self.assistant.local.settings = replace(self.settings, router_threshold=1.0)
        reply = self.assistant.ask("abra spotify")
        self.assertEqual(reply.route, "brain")
        self.assertEqual(self.backend.calls, [])

    def test_invalid_volume_is_error_without_llm(self):
        reply = self.assistant.ask("volume alto")
        self.assertFalse(reply.success)
        self.assertEqual(reply.status, "invalid_volume")
        self.assertEqual(self.audio.calls, [])
        self.assert_no_brain()

    def test_skill_error_does_not_fall_through_to_brain(self):
        with patch.object(
            self.backend, "launch", side_effect=SkillError("missing", "Não instalado.")
        ):
            reply = self.assistant.ask("abra spotify")
        self.assertFalse(reply.success)
        self.assertEqual(reply.status, "missing")
        self.assert_no_brain()

    def test_os_permission_error_is_not_retried_through_other_route(self):
        with patch.object(self.backend, "launch", side_effect=PermissionError("SECRET_TEST")):
            reply = self.assistant.ask("abra spotify")
        self.assertFalse(reply.success)
        self.assertEqual(reply.status, "PermissionError")
        self.assertNotIn("SECRET_TEST", reply.text)
        self.assert_no_brain()

    def test_timings_have_required_stages(self):
        reply = self.assistant.ask("volume 30")
        self.assertEqual(
            set(reply.timings), {"normalization_ms", "routing_ms", "skill_ms", "total_ms"}
        )
        self.assertTrue(all(value >= 0 for value in reply.timings.values()))
        self.assertAlmostEqual(reply.elapsed_seconds * 1000, reply.timings["total_ms"])


class ConfirmationTests(unittest.TestCase):
    assert_no_brain = IntegrationTests.assert_no_brain

    def setUp(self):
        IntegrationTests.setUp(self)
        self.backend.running.add("notepad")

    def test_close_waits_for_explicit_confirmation(self):
        request = self.assistant.ask("Max, fecha o Bloco de Notas.")
        self.assertTrue(request.pending_confirmation)
        self.assertEqual(request.status, "confirmation_required")
        self.assertNotIn(("close", "notepad"), self.backend.calls)
        reply = self.assistant.ask("sim")
        self.assertEqual(reply.status, "close_requested")
        self.assertIn(("close", "notepad"), self.backend.calls)
        self.assertFalse(reply.pending_confirmation)
        self.assert_no_brain()

    def test_cancel_does_not_close(self):
        self.assistant.ask("fecha notepad")
        self.assistant.ask("não")
        self.assertNotIn(("close", "notepad"), self.backend.calls)
        self.assert_no_brain()

    def test_confirmation_is_single_use(self):
        self.assistant.ask("fecha notepad")
        self.assistant.ask("sim")
        second = self.assistant.ask("sim")
        self.assertEqual(second.status, "absent")
        self.assertEqual(self.backend.calls.count(("close", "notepad")), 1)

    def test_unrelated_message_cancels_previous_request(self):
        self.assistant.ask("fecha notepad")
        self.assistant.ask("volume 30")
        self.assistant.ask("sim")
        self.assertNotIn(("close", "notepad"), self.backend.calls)

    def test_expired_confirmation_does_not_close(self):
        self.assistant.ask("fecha notepad")
        self.assistant.local.permissions.pending.deadline = 0
        reply = self.assistant.ask("sim")
        self.assertEqual(reply.status, "expired")
        self.assertNotIn(("close", "notepad"), self.backend.calls)

    def test_reset_clears_confirmation(self):
        self.assistant.ask("fecha notepad")
        self.assistant.reset()
        reply = self.assistant.ask("sim")
        self.assertEqual(reply.status, "absent")
        self.assertNotIn(("close", "notepad"), self.backend.calls)

    def test_changed_window_is_not_retargeted(self):
        self.assistant.ask("fecha notepad")
        self.backend.snapshot[0]["created"] = 999.0
        reply = self.assistant.ask("sim")
        self.assertFalse(reply.success)
        self.assertEqual(reply.status, "target_changed")
        self.assertNotIn(("close", "notepad"), self.backend.calls)

    def test_protected_explorer_never_prompts_or_closes(self):
        reply = self.assistant.ask("fecha explorador")
        self.assertFalse(reply.success)
        self.assertEqual(reply.status, "protected_app")
        self.assertIsNone(self.assistant.local.permissions.pending)
        self.assert_no_brain()


class ExtraSkill(Skill):
    name = "extra"
    description = "Skill de teste"
    intents = ("test_extra",)
    rules = (Rule("teste extra", lambda match: Intent("test_extra", 1.0)),)

    def __init__(self):
        self.executions = 0

    def execute(self, intent, prepared):
        self.executions += 1
        return SkillResult("Executado.")


class RegistryPermissionsTests(unittest.TestCase):
    def build(self, extra):
        from skills.registry import SkillRegistry

        registry = SkillRegistry()
        registry.register(extra)
        codex, ollama = SpyBrain("codex"), SpyBrain("ollama")
        return Assistant(Settings(), {"codex": codex, "ollama": ollama}, registry)

    def test_new_skill_is_usable_without_changing_router(self):
        extra = ExtraSkill()
        reply = self.build(extra).ask("teste extra")
        self.assertEqual(reply.skill, "extra")
        self.assertFalse(reply.llm_used)
        self.assertEqual(extra.executions, 1)

    def test_requires_confirmation_is_enforced(self):
        extra = ExtraSkill()
        extra.requires_confirmation = True
        assistant = self.build(extra)
        reply = assistant.ask("teste extra")
        self.assertTrue(reply.pending_confirmation)
        self.assertEqual(extra.executions, 0)
        assistant.ask("sim")
        self.assertEqual(extra.executions, 1)

    def test_dangerous_skill_is_not_executed(self):
        extra = ExtraSkill()
        extra.risk_level = RiskLevel.DANGEROUS
        reply = self.build(extra).ask("teste extra")
        self.assertFalse(reply.success)
        self.assertEqual(reply.status, "dangerous_not_implemented")
        self.assertEqual(extra.executions, 0)


class AuditAndConfigTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeWindows()
        self.audio = FakeAudio()
        self.settings = Settings()
        self.assistant = Assistant(
            self.settings,
            {"codex": SpyBrain("codex"), "ollama": SpyBrain("ollama")},
            build_registry(self.settings, self.backend, lambda: self.audio),
        )
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.logger = logging.getLogger("max")
        previous = self.logger.level
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.addCleanup(self.logger.removeHandler, self.handler)
        self.addCleanup(self.logger.setLevel, previous)

    def test_safe_command_logs_normalized_intent_parameters_and_duration(self):
        self.assistant.ask("Max, volume 30.")
        self.assertIn('"normalized_input": "volume 30"', self.stream.getvalue())
        self.assertIn('"parameters": {"value": 30.0}', self.stream.getvalue())
        self.assertIn('"llm_used": false', self.stream.getvalue())

    def test_free_text_and_invalid_parameters_are_omitted(self):
        self.assistant.ask("Minha senha de teste é NEVER_LOG_THIS")
        self.assistant.ask("volume NEVER_LOG_THIS")
        self.assertNotIn("NEVER_LOG_THIS", self.stream.getvalue())
        self.assertIn("[omitted]", self.stream.getvalue())

    def test_nonfinite_input_does_not_break_structured_logging(self):
        reply = self.assistant.ask("volume " + "9" * 500)
        self.assertFalse(reply.success)
        self.assertNotIn("Infinity", self.stream.getvalue())

    def test_settings_validation(self):
        for kwargs in (
            {"router_threshold": 0},
            {"router_threshold": 1.1},
            {"router_threshold": float("nan")},
            {"volume_step": True},
            {"volume_step": 0},
            {"confirmation_timeout": 0},
            {"launch_verify_timeout": -1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ConfigError):
                Settings(**kwargs)

    def test_custom_volume_increment(self):
        registry = build_registry(
            replace(self.settings, volume_step=7), self.backend, lambda: self.audio
        )
        assistant = Assistant(
            self.settings, {"codex": SpyBrain("codex"), "ollama": SpyBrain("ollama")}, registry
        )
        assistant.ask("aumenta o volume")
        self.assertEqual(self.audio.volume, 57)
