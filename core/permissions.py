"""Confirmações ligadas a uma ação e a um snapshot, válidas apenas na sessão."""
from dataclasses import dataclass
from enum import StrEnum
import time


class RiskLevel(StrEnum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    DANGEROUS = "DANGEROUS"


@dataclass
class PendingAction:
    skill: object
    intent: object
    prepared: dict
    deadline: float


class Permissions:
    YES = {"sim", "confirmo", "confirmar", "pode fechar"}
    NO = {"nao", "cancelar", "cancela", "nao feche"}

    def __init__(self, ttl: float):
        self.ttl = ttl
        self.pending = None

    def request(self, skill, intent, prepared):
        self.pending = PendingAction(skill, intent, prepared, time.monotonic() + self.ttl)

    def consume(self, text):
        pending = self.pending
        self.pending = None  # Outra mensagem também invalida a confirmação antiga.
        if text in self.NO:
            return "cancelled", None
        if text in self.YES:
            if pending is None:
                return "absent", None
            if time.monotonic() > pending.deadline:
                return "expired", None
            return "confirmed", pending
        return "new", None
