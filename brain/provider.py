"""Contrato comum; falhas só carregam códigos e mensagens seguros para exibir."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Sequence

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Health:
    provider: str
    ok: bool
    detail: str
    code: str = "ok"


@dataclass(frozen=True)
class Answer:
    text: str
    provider: str
    model: str


class ProviderError(RuntimeError):
    def __init__(self, provider: str, code: str, message: str):
        super().__init__(message)
        self.provider = provider
        self.code = code


class BrainProvider(ABC):
    name: str

    @abstractmethod
    def health_check(self) -> Health:
        """Checagem local/leve; disponibilidade não garante inferência."""
        raise NotImplementedError

    def available(self) -> bool:
        return self.health_check().ok

    @abstractmethod
    def ask(self, messages: Sequence[Message]) -> Answer:
        raise NotImplementedError
