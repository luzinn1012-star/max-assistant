from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from core.permissions import RiskLevel


class SkillError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SkillResult:
    text: str
    success: bool = True
    status: str = "completed"
    data: dict = field(default_factory=dict)


class Skill(ABC):
    name: str
    description: str
    intents: tuple[str, ...]
    aliases: dict = {}
    rules: tuple = ()
    risk_level = RiskLevel.SAFE
    requires_confirmation = False

    def can_handle(self, intent):
        return intent.intent in self.intents

    def validate(self, intent):
        if not self.can_handle(intent):
            raise SkillError("unsupported_intent", "Esta skill não reconhece esse comando.")

    def risk_for(self, intent):
        if self.risk_level != RiskLevel.SAFE:
            return self.risk_level
        required = self.requires_confirmation
        if isinstance(required, dict):
            required = required.get(intent.intent, False)
        return RiskLevel.CONFIRM if required else RiskLevel.SAFE

    def prepare(self, intent):
        self.validate(intent)
        return dict(intent.slots)

    def confirmation_prompt(self, intent):
        return "Confirma esta ação?"

    def health_check(self):
        return {"ok": True, "skill": self.name}

    @abstractmethod
    def execute(self, intent, prepared):
        raise NotImplementedError
