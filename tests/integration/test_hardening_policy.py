import json
import logging
from concurrent.futures import ThreadPoolExecutor

import pytest

from config import Settings
from core.assistant import Assistant
from core.capabilities import Capability, CapabilityPolicy
from core.observability import current_request_id, request_scope
from skills.bootstrap import build_registry
from tests.phase2_doubles import FakeAudio, FakeWindows, SpyBrain


def build():
    backend, audio = FakeWindows(), FakeAudio()
    providers = {"codex": SpyBrain("codex"), "ollama": SpyBrain("ollama")}
    assistant = Assistant(Settings(), providers, build_registry(Settings(), backend, lambda: audio))
    return assistant, backend, audio, providers


@pytest.mark.parametrize(
    "command,capability",
    [
        ("abra calculadora", Capability.APP_LAUNCH),
        ("abra calculadora", Capability.PROCESS_INSPECT),
        ("volume 30", Capability.AUDIO_WRITE),
        ("mute", Capability.AUDIO_READ),
        ("abra Downloads", Capability.FILESYSTEM_READ),
        ("como esta o pc", Capability.PROCESS_INSPECT),
    ],
)
def test_denial_precedes_adapter_and_provider_calls(command, capability):
    assistant, backend, audio, providers = build()
    policy = assistant.local.capability_policy
    policy.allowed = policy.allowed - {capability}
    reply = assistant.ask(command)
    assert not reply.success and reply.error == "capability_denied"
    assert not reply.llm_used
    assert not backend.calls and not audio.calls
    assert all(not p.ask_calls and p.health_calls == 0 for p in providers.values())


def test_network_denial_does_not_touch_any_provider():
    assistant, _, _, providers = build()
    assistant.local.capability_policy = CapabilityPolicy(frozenset())
    reply = assistant.ask("Explique relatividade.")
    assert reply.status == "capability_denied"
    assert not reply.llm_used
    assert all(not p.ask_calls and p.health_calls == 0 for p in providers.values())
    assert all(not health.ok for health in assistant.status())
    assert all(p.health_calls == 0 for p in providers.values())


def test_capability_revocation_invalidates_pending_close_without_execution():
    assistant, backend, _, _ = build()
    backend.running.add("notepad")
    assert assistant.ask("fecha notepad").pending_confirmation
    assistant.local.capability_policy.allowed -= {Capability.APP_CLOSE}
    assert assistant.ask("sim").status == "capability_denied"
    assert not any(call[0] == "close" for call in backend.calls)
    assert assistant.ask("sim").status == "absent"


def test_default_policy_keeps_close_confirmation_required():
    assistant, backend, _, _ = build()
    backend.running.add("notepad")
    assert assistant.ask("fecha notepad").pending_confirmation
    assert not any(call[0] == "close" for call in backend.calls)
    assert assistant.ask("sim").status == "close_requested"


def test_request_ids_correlate_attempts_and_replies_without_logging_free_text(caplog):
    assistant, _, _, providers = build()
    providers["codex"].fail = True
    with caplog.at_level(logging.INFO, logger="max"):
        reply = assistant.ask("Sensitive hypothetical input NEVER_LOG_ME")
    assert reply.fallback_used and reply.provider == "ollama"
    assert current_request_id() == "-"
    assert "NEVER_LOG_ME" not in caplog.text
    records = [r for r in caplog.records if r.name == "max"]
    assert all(r.request_id == reply.request_id for r in records)
    dispatch = [
        json.loads(r.getMessage().split("event=dispatch ", 1)[1])
        for r in records
        if "event=dispatch " in r.getMessage()
    ][0]
    assert dispatch["fallback"] is True and dispatch["request_id"] == reply.request_id
    assert dispatch["duration_ms"] >= 0 and dispatch["error"] is None
    assert len(reply.request_id) == 32


def test_requests_use_distinct_ids():
    assistant, _, _, _ = build()
    assert assistant.ask("ajuda").request_id != assistant.ask("ajuda").request_id


def test_context_ids_are_isolated_across_threads():
    def operation(_):
        with request_scope() as value:
            assert current_request_id() == value
            return value

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(operation, range(16)))
    assert len(set(ids)) == 16
    assert current_request_id() == "-"


def test_policy_can_be_injected_at_composition_boundary():
    providers = {"codex": SpyBrain("codex"), "ollama": SpyBrain("ollama")}
    assistant = Assistant(Settings(), providers, capability_policy=CapabilityPolicy(frozenset()))
    assert assistant.ask("abra calculadora").status == "capability_denied"
    assert all(
        not provider.ask_calls and provider.health_calls == 0 for provider in providers.values()
    )
