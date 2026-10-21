import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.errors import InvalidParameter


@dataclass(frozen=True)
class IntentResult:
    intent: str = "unknown"
    confidence: float = 0.0
    slots: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.intent, str) or not self.intent:
            raise InvalidParameter("invalid_intent", "Intent inválida.")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
        ):
            raise InvalidParameter("invalid_confidence", "Confiança inválida.")
        if not isinstance(self.slots, dict) or any(not isinstance(key, str) for key in self.slots):
            raise InvalidParameter("invalid_slots", "Parâmetros inválidos.")
        object.__setattr__(self, "slots", dict(self.slots))


# Compatibility for phase 1/2 extensions.
Intent = IntentResult


@dataclass(frozen=True)
class Rule:
    pattern: str
    resolve: Callable[[re.Match[str]], IntentResult]
