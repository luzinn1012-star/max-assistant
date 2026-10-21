from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.capabilities import Capability
from core.errors import InvalidParameter
from core.errors import SkillExecutionError as SkillError
from core.intent import IntentResult, Rule
from core.permissions import RiskLevel


@dataclass(frozen=True)
class SkillResult:
    text: str
    success: bool = True
    status: str = "completed"
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.text, str)
            or type(self.success) is not bool
            or not isinstance(self.status, str)
            or not self.status
            or not isinstance(self.data, dict)
            or (self.error is not None and not isinstance(self.error, str))
        ):
            raise InvalidParameter("invalid_skill_result", "Resultado de skill inválido.")
        object.__setattr__(self, "data", dict(self.data))


class Skill(ABC):
    name: str
    description: str
    intents: tuple[str, ...]
    aliases: dict[str, list[str]] = {}
    rules: tuple[Rule, ...] = ()
    risk_level = RiskLevel.SAFE
    requires_confirmation: bool | dict[str, bool] = False
    required_capabilities: dict[str, frozenset[Capability]] = {}

    def can_handle(self, intent: IntentResult) -> bool:
        return intent.intent in self.intents

    def validate(self, intent: IntentResult) -> None:
        if not self.can_handle(intent):
            raise SkillError("unsupported_intent", "Esta skill não reconhece esse comando.")

    def capabilities_for(self, intent: IntentResult) -> frozenset[Capability]:
        return self.required_capabilities.get(intent.intent, frozenset())

    def risk_for(self, intent: IntentResult) -> RiskLevel:
        if self.risk_level != RiskLevel.SAFE:
            return self.risk_level
        required = self.requires_confirmation
        if isinstance(required, dict):
            required = required.get(intent.intent, False)
        return RiskLevel.CONFIRM if required else RiskLevel.SAFE

    def prepare(self, intent: IntentResult) -> dict[str, Any]:
        self.validate(intent)
        return dict(intent.slots)

    def confirmation_prompt(self, intent: IntentResult) -> str:
        return "Confirma esta ação?"

    def health_check(self) -> dict[str, Any]:
        return {"ok": True, "skill": self.name}

    @abstractmethod
    def execute(self, intent: IntentResult, prepared: dict[str, Any]) -> SkillResult:
        raise NotImplementedError
