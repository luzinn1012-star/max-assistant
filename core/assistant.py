"""Roteamento local e providers com fallback; texto do LLM nunca vira comando."""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from brain.provider import BrainProvider, Health, ProviderError
from config import Settings
from core.capabilities import Capability, CapabilityPolicy
from core.context import Conversation
from core.dispatcher import Dispatcher
from core.errors import InvalidParameter, PermissionDenied, ProviderUnavailable
from core.observability import RequestIdFilter, current_request_id, request_scope
from skills.base import SkillResult
from skills.bootstrap import build_registry
from skills.registry import SkillRegistry

logger = logging.getLogger("max")
logger.addFilter(RequestIdFilter())


@dataclass(frozen=True)
class Reply:
    text: str
    provider: str
    model: str
    elapsed_seconds: float
    fallback_used: bool
    notices: tuple[str, ...]
    route: str = "brain"
    intent: str = "unknown"
    confidence: float = 0.0
    skill: str | None = None
    risk_level: str | None = None
    llm_used: bool = True
    success: bool = True
    pending_confirmation: bool = False
    status: str = "completed"
    timings: dict = field(default_factory=dict)
    data: dict = field(default_factory=dict)
    request_id: str = field(default_factory=current_request_id)
    error: str | None = None


class Assistant:
    def __init__(
        self,
        settings: Settings,
        providers: Mapping[str, BrainProvider],
        registry: SkillRegistry | None = None,
        *,
        capability_policy: CapabilityPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.providers = providers
        self.local = Dispatcher(
            settings,
            registry if registry is not None else build_registry(settings),
            capability_policy,
        )
        self.context = Conversation(settings.history_turns, settings.context_chars)
        self.active_provider: str | None = None
        self._cooldown_until: dict[str, float] = {}
        self._health: dict[str, tuple[float, Health]] = {}

    def _check(self, name: str) -> Health:
        cached = self._health.get(name)
        if cached and time.monotonic() - cached[0] < 30:
            return cached[1]
        health = self.providers[name].health_check()
        self._health[name] = (time.monotonic(), health)
        return health

    def status(self) -> list[Health]:
        if Capability.NETWORK_REQUEST not in self.local.capability_policy.allowed:
            return [
                Health(name, False, "Consulta sem permissão nesta sessão.", "capability_denied")
                for name in self.providers
            ]
        # Diagnósticos independentes podem rodar juntos.
        with ThreadPoolExecutor(max_workers=len(self.providers)) as pool:
            statuses = list(
                pool.map(lambda provider: provider.health_check(), self.providers.values())
            )
        for health in statuses:
            self._health[health.provider] = (time.monotonic(), health)
        return statuses

    def reset(self) -> None:
        self.context.clear()
        self.local.permissions.pending = None

    def retry(self) -> None:
        self._cooldown_until.clear()
        self._health.clear()

    def ask(self, text: str) -> Reply:
        with request_scope():
            return self._ask(text)

    def _ask(self, text: str) -> Reply:
        text = text.strip()
        if not text:
            raise InvalidParameter("empty_input", "Digite uma mensagem.")
        if len(text) > self.settings.max_input_chars:
            raise InvalidParameter(
                "input_too_long",
                f"A mensagem ultrapassou o limite de {self.settings.max_input_chars} caracteres.",
            )
        started = time.perf_counter()
        decision = self.local.dispatch(text)
        if decision.result is None:
            try:
                self.local.capability_policy.require({Capability.NETWORK_REQUEST})
            except PermissionDenied as exc:
                decision.result = SkillResult(str(exc), False, exc.code, error=exc.code)
                decision.skill = "permissions"
                decision.risk = "SAFE"
        if decision.result is not None:
            result = decision.result
            elapsed = time.perf_counter() - started
            reply = Reply(
                result.text,
                "local",
                "",
                elapsed,
                False,
                (),
                route="local",
                intent=decision.intent.intent,
                confidence=decision.intent.confidence,
                skill=decision.skill,
                risk_level=decision.risk,
                llm_used=False,
                success=result.success,
                pending_confirmation=decision.confirmation,
                status=result.status,
                timings={**decision.timings, "total_ms": elapsed * 1000},
                data=result.data,
                error=result.error,
            )
            self._audit(decision, reply)
            return reply
        order = (
            ["codex", "ollama"] if self.settings.provider == "auto" else [self.settings.provider]
        )
        messages = self.context.for_request(text)
        notices = []
        for name in order:
            if time.monotonic() < self._cooldown_until.get(name, 0):
                notices.append(f"{name}: aguardando nova tentativa após falha anterior.")
                continue
            attempt_started = time.perf_counter()
            try:
                health = self._check(name)
                if not health.ok:
                    raise ProviderUnavailable(name, health.code, health.detail)
                answer = self.providers[name].ask(messages)
                if not answer.text.strip():
                    raise ProviderError(
                        name, "empty_response", "O provider retornou uma resposta vazia."
                    )
            except ProviderError as exc:
                self._cooldown_until[name] = time.monotonic() + self.settings.retry_cooldown
                self._health.pop(name, None)
                logger.warning(
                    "event=provider_attempt command=conversation skill=none provider=%s success=false duration_ms=%.1f error=%s",
                    name,
                    (time.perf_counter() - attempt_started) * 1000,
                    exc.code,
                )
                notices.append(f"{name}: {exc}")
                continue
            self.active_provider = name
            self.context.commit(text, answer.text)
            elapsed = time.perf_counter() - started
            logger.info(
                "event=response command=conversation skill=none provider=%s success=true duration_ms=%.1f input_chars=%d",
                name,
                elapsed * 1000,
                len(text),
            )
            reply = Reply(
                answer.text,
                name,
                answer.model,
                elapsed,
                self.settings.provider == "auto" and name != "codex",
                tuple(notices),
                intent=decision.intent.intent,
                confidence=decision.intent.confidence,
                timings={**decision.timings, "total_ms": elapsed * 1000},
            )
            self._audit(decision, reply)
            return reply
        self.active_provider = None
        elapsed = time.perf_counter() - started
        logger.error(
            "event=response command=conversation skill=none success=false duration_ms=%.1f error=all_unavailable",
            elapsed * 1000,
        )
        self._audit(
            decision,
            Reply(
                "",
                "none",
                "",
                elapsed,
                False,
                tuple(notices),
                success=False,
                status="all_unavailable",
                error="all_unavailable",
                intent=decision.intent.intent,
                confidence=decision.intent.confidence,
                timings={**decision.timings, "total_ms": elapsed * 1000},
            ),
        )
        raise ProviderUnavailable(
            "all", "all_unavailable", "Nenhum provider respondeu. " + " ".join(notices)
        )

    def _audit(self, decision, reply):
        safe_slots = {
            key: value
            for key, value in decision.intent.slots.items()
            if key in {"app", "folder", "section", "value", "delta"}
            and (not isinstance(value, float) or math.isfinite(value))
        }
        # Conversa e parâmetros inválidos não entram nos logs.
        safe_input = (
            reply.route == "local"
            and reply.success
            and (
                safe_slots
                or decision.intent.intent in {"help", "mute_volume", "unmute_volume"}
                or decision.normalized in self.local.permissions.YES | self.local.permissions.NO
            )
        )
        normalized = decision.normalized if safe_input else "[omitted]"
        logger.info(
            "event=dispatch %s",
            json.dumps(
                {
                    "normalized_input": normalized,
                    "intent": reply.intent,
                    "confidence": reply.confidence,
                    "skill": reply.skill,
                    "parameters": safe_slots,
                    "risk_level": reply.risk_level,
                    "request_id": reply.request_id,
                    "provider": reply.provider,
                    "llm_used": reply.llm_used,
                    "fallback": reply.fallback_used,
                    "error": reply.error,
                    "duration_ms": reply.elapsed_seconds * 1000,
                    "success": reply.success,
                    "status": reply.status,
                    **reply.timings,
                },
                ensure_ascii=False,
                allow_nan=False,
            ),
        )
