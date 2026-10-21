"""Confirmations bound to an action, snapshot and current session."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from core.intent import IntentResult

if TYPE_CHECKING:
    from skills.base import Skill


class RiskLevel(StrEnum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    DANGEROUS = "DANGEROUS"


@dataclass
class PendingAction:
    skill: Skill
    intent: IntentResult
    prepared: dict[str, Any]
    deadline: float


class Permissions:
    YES = {"sim", "confirmo", "confirmar", "pode fechar"}
    NO = {"nao", "cancelar", "cancela", "nao feche"}

    def __init__(self, ttl: float) -> None:
        self.ttl = ttl
        self.pending: PendingAction | None = None

    def request(self, skill: Skill, intent: IntentResult, prepared: dict[str, Any]) -> None:
        self.pending = PendingAction(skill, intent, prepared, time.monotonic() + self.ttl)

    def consume(self, text: str) -> tuple[str, PendingAction | None]:
        pending = self.pending
        self.pending = None
        if text in self.NO:
            return "cancelled", None
        if text in self.YES:
            if pending is None:
                return "absent", None
            if time.monotonic() > pending.deadline:
                return "expired", None
            return "confirmed", pending
        return "new", None
