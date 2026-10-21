import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from config import ConfigError, Settings, load_settings


class ConfigTests(unittest.TestCase):
    def test_default_requires_no_api_key(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True), patch("config.ROOT", Path(directory)):
            self.assertEqual(load_settings().provider, "auto")

    def test_rejects_invalid_types_and_ranges(self):
        cases = ({"provider": []}, {"provider": "api"}, {"codex_timeout": 0},
                 {"health_timeout": True}, {"retry_cooldown": float("inf")},
                 {"history_turns": 1.5}, {"max_input_chars": 13000},
                 {"ollama_model": ""}, {"ollama_url": 42})
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ConfigError):
                Settings(**kwargs)

    def test_rejects_remote_or_credentialed_ollama_urls(self):
        for url in ("https://example.com", "http://user:secret@localhost:11434",
                    "http://127.0.0.1:11434/path", "http://127.0.0.1:11434?token=secret",
                    "http://127.0.0.1:bad"):
            with self.subTest(url=url), self.assertRaises(ConfigError):
                Settings(ollama_url=url)

    def test_invalid_configuration_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for content in ("{", "[]", '{"unknown":"SECRET_TEST"}'):
                path.write_text(content, encoding="utf-8")
                with self.subTest(content=content), self.assertRaises(ConfigError) as caught:
                    load_settings(path)
                self.assertNotIn("SECRET_TEST", str(caught.exception))

    def test_explicit_missing_config_is_not_silently_ignored(self):
        # A configuração padrão pode não existir; caminho explícito deve falhar.
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ConfigError):
                load_settings(Path(directory) / "missing.json")

    def test_environment_overrides_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"provider": "auto"}), encoding="utf-8")
            with patch.dict("os.environ", {"MAX_PROVIDER": "ollama"}):
                self.assertEqual(load_settings(path).provider, "ollama")
