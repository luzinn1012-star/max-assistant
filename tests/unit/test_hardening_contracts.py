import ast
from dataclasses import asdict

import pytest

from brain.provider import Answer, ProviderResult
from config import ROOT
from core.capabilities import Capability, CapabilityPolicy
from core.errors import (
    AppNotFound,
    ConfirmationRequired,
    InvalidParameter,
    PermissionDenied,
    ProviderError,
    ProviderUnavailable,
    SkillExecutionError,
)
from core.intent import Intent, IntentResult
from core.observability import current_request_id, request_scope
from skills.apps import AppsSkill, load_apps
from skills.base import SkillError, SkillResult
from tests.phase2_doubles import FakeWindows


@pytest.mark.parametrize("confidence", [-1, 1.01, float("nan"), float("inf"), True, "0.9"])
def test_invalid_confidence_is_rejected(confidence):
    with pytest.raises(InvalidParameter):
        IntentResult("open_app", confidence)


@pytest.mark.parametrize("intent,slots", [("", {}), (1, {}), ("help", []), ("help", {1: "bad"})])
def test_invalid_intent_shape_is_rejected(intent, slots):
    with pytest.raises(InvalidParameter):
        IntentResult(intent, 1.0, slots)


def test_legacy_result_names_preserve_json_contract():
    assert Intent is IntentResult
    assert Answer is ProviderResult
    assert SkillError is SkillExecutionError
    assert asdict(Answer("ok", "ollama", "qwen3:4b")) == {
        "text": "ok",
        "provider": "ollama",
        "model": "qwen3:4b",
    }
    assert asdict(SkillResult("ok"))["success"] is True


def test_intent_does_not_retain_callers_slot_dictionary():
    slots = {"app": "calculator"}
    result = IntentResult("open_app", 0.99, slots)
    slots["app"] = "other"
    assert result.slots["app"] == "calculator"


def test_provider_result_rejects_non_text():
    with pytest.raises(InvalidParameter):
        ProviderResult(None, "codex", "test")


@pytest.mark.parametrize(
    "error_type", [AppNotFound, PermissionDenied, ConfirmationRequired, InvalidParameter]
)
def test_specific_skill_errors_remain_compatible(error_type):
    error = error_type("safe_code", "Safe message")
    assert isinstance(error, SkillExecutionError)
    assert error.code == "safe_code"


def test_provider_unavailable_preserves_provider_error_contract():
    error = ProviderUnavailable("codex", "offline", "Not available")
    assert isinstance(error, ProviderError)
    assert error.provider == "codex"
    assert error.code == "offline"


@pytest.mark.parametrize(
    "capability",
    [Capability.PROCESS_TERMINATE, Capability.FILESYSTEM_WRITE, Capability.SYSTEM_POWER],
)
def test_unsupported_capabilities_are_denied_by_default(capability):
    with pytest.raises(PermissionDenied):
        CapabilityPolicy().require({capability})


def test_request_scope_is_reset_even_on_exception():
    assert current_request_id() == "-"
    with pytest.raises(RuntimeError), request_scope():
        assert current_request_id() != "-"
        raise RuntimeError("test")
    assert current_request_id() == "-"


def test_nested_request_scope_restores_parent():
    with request_scope() as outer:
        with request_scope() as inner:
            assert outer != inner
        assert current_request_id() == outer
    assert current_request_id() == "-"


def test_skills_have_no_process_or_shell_dependencies():
    forbidden = {"subprocess", "ctypes", "winreg"}
    for path in (ROOT / "skills").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] in forbidden for alias in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert not (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr in {"system", "popen", "startfile"}
                ), path


def test_unknown_app_raises_specific_error():
    skill = AppsSkill(FakeWindows(), load_apps(ROOT / "apps.json"))
    with pytest.raises(AppNotFound):
        skill.validate(Intent("open_app", 0.99, {"app": "does_not_exist"}))


def test_invalid_capability_is_rejected_at_registration():
    from skills.help import HelpSkill
    from skills.registry import SkillRegistry

    skill = HelpSkill()
    skill.required_capabilities = {"help": frozenset({"unknown.operation"})}
    with pytest.raises(ValueError):
        SkillRegistry().register(skill)


def test_benchmark_statistics_and_no_real_side_effects():
    from benchmarks.local import benchmark, distribution

    assert distribution([1, 2, 3, 4, 5])["p95_ms"] == 5
    result = benchmark(samples=10, warmup=2)
    assert result["local_provider_calls"] == 0
    assert result["real_windows_launch_measured"] is False
    with pytest.raises(ValueError):
        benchmark(0)


@pytest.mark.parametrize(
    "kwargs", [{"text": 1}, {"success": "yes"}, {"status": ""}, {"data": []}, {"error": 1}]
)
def test_invalid_skill_result_is_rejected(kwargs):
    with pytest.raises(InvalidParameter):
        SkillResult(**({"text": "ok"} | kwargs))
