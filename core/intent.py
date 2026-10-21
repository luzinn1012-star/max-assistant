from dataclasses import dataclass, field
import re
from typing import Callable


@dataclass(frozen=True)
class Intent:
    intent: str = "unknown"
    confidence: float = 0.0
    slots: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    pattern: str
    resolve: Callable[[re.Match], Intent]
