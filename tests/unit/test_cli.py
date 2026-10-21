import json
import logging
from unittest.mock import patch

import pytest

import main
from brain.provider import Health, ProviderError
from config import ConfigError, Settings
from core.assistant import Reply
from core.logging_setup import setup_logging
from scripts.dev import interpreter


def test_cli_ask_json_does_not_require_live_providers(capsys):
    result = Reply("ok", "local", "", 0.001, False, (), route="local", llm_used=False)
    with patch("main.setup_logging"), patch("main.Assistant") as assistant:
        assistant.return_value.ask.return_value = result
        assert main.main(["--ask", "ajuda", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["llm_used"] is False


def test_cli_health_uses_structured_status(capsys):
    with patch("main.setup_logging"), patch("main.Assistant") as assistant:
        assistant.return_value.settings = Settings()
        assistant.return_value.active_provider = None
        assistant.return_value.status.return_value = [Health("codex", True, "test")]
        assert main.main(["--health", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["providers"][0]["ok"] is True


def test_cli_invalid_json_combination_is_rejected():
    with pytest.raises(SystemExit) as error:
        main.main(["--json"])
    assert error.value.code == 2


@pytest.mark.parametrize(
    "error", [ConfigError("bad config"), ProviderError("codex", "offline", "Unavailable")]
)
def test_cli_errors_are_nonzero_json(error, capsys):
    with patch("main.load_settings", side_effect=error):
        assert main.main(["--ask", "test", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_interactive_commands_do_not_execute_windows(capsys):
    with (
        patch("main.setup_logging"),
        patch("main.Assistant") as assistant,
        patch("builtins.input", side_effect=["", "/limpar", "/tentar", "/status", "/sair"]),
    ):
        assistant.return_value.settings = Settings()
        assistant.return_value.status.return_value = []
        assert main.main([]) == 0
        assistant.return_value.reset.assert_called_once()
        assistant.return_value.retry.assert_called_once()
        assistant.return_value.ask.assert_not_called()
    assert "Até mais" in capsys.readouterr().out


def test_logging_setup_is_idempotent_and_writes_request_id(tmp_path):
    logger = logging.getLogger("max")
    previous = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = []
    try:
        setup_logging(tmp_path)
        setup_logging(tmp_path)
        assert len(logger.handlers) == 1
        logger.info("safe test event")
        logger.handlers[0].flush()
        assert "request_id=-" in (tmp_path / "max.log").read_text(encoding="utf-8")
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers, logger.level, logger.propagate = previous


def test_dev_tool_uses_local_venv_and_preserves_exit_status(tmp_path):
    import scripts.dev as dev

    executable = tmp_path / ".venv" / "Scripts" / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    assert interpreter(tmp_path) == str(executable)
    with (
        patch.object(dev, "interpreter", return_value="python"),
        patch.object(dev.subprocess, "run") as run,
    ):
        run.return_value.returncode = 7
        assert dev.main(["ruff", "check", "."]) == 7
        assert run.call_args.kwargs["shell"] is False
    assert dev.main(["unsupported"]) == 2
