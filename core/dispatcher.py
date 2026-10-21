import time
from dataclasses import dataclass

from core.capabilities import CapabilityPolicy
from core.errors import ConfirmationRequired, PermissionDenied
from core.intent import Intent
from core.normalizer import normalize
from core.permissions import Permissions
from core.router import Router
from skills.base import SkillError, SkillResult


@dataclass
class Dispatch:
    normalized: str
    intent: Intent
    timings: dict
    result: SkillResult | None = None
    skill: str | None = None
    risk: str | None = None
    confirmation: bool = False


class Dispatcher:
    def __init__(self, settings, registry, capability_policy=None):
        self.capability_policy = (
            capability_policy if capability_policy is not None else CapabilityPolicy()
        )
        self.settings = settings
        self.registry = registry
        self.router = Router(registry)
        self.permissions = Permissions(settings.confirmation_timeout)

    def dispatch(self, text):
        start = time.perf_counter()
        normalized = normalize(text)
        norm_ms = (time.perf_counter() - start) * 1000
        route_start = time.perf_counter()
        state, pending = self.permissions.consume(normalized)
        intent = pending.intent if pending else self.router.route(normalized)
        output = Dispatch(
            normalized,
            intent,
            {
                "normalization_ms": norm_ms,
                "routing_ms": (time.perf_counter() - route_start) * 1000,
                "skill_ms": 0.0,
            },
        )
        if state in {"cancelled", "absent", "expired"}:
            message = {
                "cancelled": "Ação cancelada.",
                "absent": "Não há ação aguardando confirmação.",
                "expired": "A confirmação expirou. Peça a ação novamente.",
            }[state]
            output.result = SkillResult(message, status=state)
            output.skill = "permissions"
            output.risk = "SAFE"
            return output
        if intent.confidence < self.settings.router_threshold or intent.intent == "unknown":
            return output
        skill = pending.skill if pending else self.registry.get(intent.intent)
        if skill is None:
            return output
        output.skill = skill.name
        output.risk = str(skill.risk_for(intent))
        skill_start = time.perf_counter()
        try:
            skill.validate(intent)
            if output.risk == "DANGEROUS":
                raise PermissionDenied(
                    "dangerous_not_implemented", "Essa ação não está disponível nesta fase."
                )
            self.capability_policy.require(skill.capabilities_for(intent))
            prepared = pending.prepared if pending else skill.prepare(intent)
            if output.risk == "CONFIRM" and state != "confirmed":
                self.permissions.request(skill, intent, prepared)
                raise ConfirmationRequired(
                    "confirmation_required", skill.confirmation_prompt(intent)
                )
            else:
                output.result = skill.execute(intent, prepared)
        except ConfirmationRequired as exc:
            output.result = SkillResult(str(exc), status=exc.code)
            output.confirmation = True
        except SkillError as exc:
            output.result = SkillResult(str(exc), False, exc.code, error=exc.code)
        except (OSError, RuntimeError, ValueError) as exc:
            output.result = SkillResult(
                "Não consegui concluir a ação local.",
                False,
                type(exc).__name__,
                error=type(exc).__name__,
            )
        finally:
            output.timings["skill_ms"] = (time.perf_counter() - skill_start) * 1000
        return output
