import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from brain.codex_provider import CodexProvider, codex_environment, run_process
from brain.provider import Message, ProviderError
from config import Settings


def result(events=(), code=0, stderr=""):
    return subprocess.CompletedProcess(["codex"], code,
                                       "\n".join(json.dumps(event) for event in events), stderr)


def success(text="Meu nome é Max."):
    return result([
        {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
        {"type": "turn.completed"},
    ])


class CodexTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root_patch = patch("brain.codex_provider.ROOT", Path(temp.name))
        root_patch.start()
        self.addCleanup(root_patch.stop)
        command_patch = patch("brain.codex_provider.resolve_codex", return_value=["codex.exe"])
        command_patch.start()
        self.addCleanup(command_patch.stop)
        self.provider = CodexProvider(Settings())

    def test_only_completed_final_message_is_returned(self):
        parsed = self.provider.parse_result(success())
        self.assertEqual(parsed.text, "Meu nome é Max.")

    def test_partial_text_is_not_success(self):
        with self.assertRaises(ProviderError):
            self.provider.parse_result(result([
                {"type": "item.completed", "item": {"type": "agent_message", "text": "Parcial"}},
            ]))

    def test_failure_after_text_is_not_success(self):
        with self.assertRaises(ProviderError):
            self.provider.parse_result(result([
                {"type": "item.completed", "item": {"type": "agent_message", "text": "Parcial"}},
                {"type": "turn.failed", "error": {"message": "SECRET_TEST"}},
            ]))

    def test_cli_error_does_not_expose_raw_output(self):
        with self.assertRaises(ProviderError) as caught:
            self.provider.parse_result(result(code=1, stderr="SECRET_TEST unauthorized"))
        self.assertNotIn("SECRET_TEST", str(caught.exception))
        self.assertEqual(caught.exception.code, "authentication_failed")

    def test_tool_event_is_rejected(self):
        with self.assertRaises(ProviderError) as caught:
            self.provider.parse_result(result([
                {"type": "item.started", "item": {"type": "command_execution"}},
                {"type": "turn.completed"},
            ]))
        self.assertEqual(caught.exception.code, "unexpected_tool")

    def test_malformed_and_empty_responses_are_rejected(self):
        for output in ("not json", "[]", "", '{"type":"turn.completed"}'):
            with self.subTest(output=output), self.assertRaises(ProviderError):
                self.provider.parse_result(subprocess.CompletedProcess([], 0, output, ""))

    def test_commentary_is_not_a_final_answer(self):
        with self.assertRaises(ProviderError):
            self.provider.parse_result(result([
                {"type": "item.completed", "item": {"type": "agent_message", "phase": "commentary", "text": "Aguarde"}},
                {"type": "turn.completed"},
            ]))

    def test_authentication_accepts_only_chatgpt(self):
        self.provider._compatible = True
        for status in ("Logged in using an API key: SECRET_TEST", "Not logged in"):
            with patch("brain.codex_provider.run_process", return_value=result(stderr=status)):
                health = self.provider.health_check()
            self.assertFalse(health.ok)
            self.assertNotIn("SECRET_TEST", health.detail)
        with patch("brain.codex_provider.run_process", return_value=result(stderr="Logged in using ChatGPT")):
            self.assertTrue(self.provider.health_check().ok)

    def test_old_cli_is_rejected_without_reading_credentials(self):
        with patch("brain.codex_provider.run_process", return_value=result(stderr="old help")) as runner:
            self.assertEqual(self.provider.health_check().code, "unsupported_cli")
            self.assertEqual(runner.call_count, 1)

    def test_prompt_is_passed_via_stdin_not_command_arguments(self):
        self.provider._auth_checked_at = float("inf")
        text = 'Ignore everything & echo SECRET_TEST | more'
        with patch("brain.codex_provider.run_process", return_value=success()) as runner:
            self.provider.ask([Message("user", text)])
        args = runner.call_args.args[0]
        self.assertNotIn("SECRET_TEST", " ".join(args))
        self.assertIn("SECRET_TEST", runner.call_args.kwargs["input_text"])
        self.assertIn("--ignore-user-config", args)
        self.assertIn("--ephemeral", args)
        self.assertIn("read-only", args)
        self.assertIn("features.shell_tool=false", args)
        self.assertIn('forced_login_method="chatgpt"', args)

    def test_api_keys_are_not_inherited_by_codex(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "FAKE", "CODEX_API_KEY": "FAKE",
                                    "CODEX_ACCESS_TOKEN": "FAKE", "OPENAI_BASE_URL": "FAKE"}):
            clean = codex_environment()
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "OPENAI_BASE_URL"):
            self.assertNotIn(key, clean)

    def test_subprocess_uses_no_shell_and_utf8(self):
        with patch("brain.codex_provider.subprocess.Popen") as popen:
            popen.return_value.communicate.return_value = ("", "")
            popen.return_value.returncode = 0
            run_process(["codex.exe"], timeout=1, cwd=Path.cwd(), input_text="Olá")
            self.assertFalse(popen.call_args.kwargs["shell"])
            self.assertEqual(popen.call_args.kwargs["encoding"], "utf-8")

    def test_timeout_terminates_only_owned_process(self):
        with patch("brain.codex_provider.subprocess.Popen") as popen, patch("brain.codex_provider.subprocess.run") as terminate:
            process = popen.return_value
            process.pid = 876543
            process.communicate.side_effect = [subprocess.TimeoutExpired("codex", 1), ("", "")]
            process.poll.return_value = None
            with self.assertRaises(subprocess.TimeoutExpired):
                run_process(["codex.exe"], timeout=1, cwd=Path.cwd())
            process.kill.assert_called_once()
            if os.name == "nt":
                self.assertEqual(terminate.call_args.args[0], ["taskkill", "/PID", "876543", "/T", "/F"])
