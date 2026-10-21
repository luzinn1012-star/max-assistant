"""Common contracts; credentials never belong to provider results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from core.errors import InvalidParameter
from core.errors import ProviderError as ProviderError

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
class ProviderResult:
    text: str
    provider: str
    model: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) for value in (self.text, self.provider, self.model)):
            raise InvalidParameter("invalid_provider_result", "Resposta de provider inválida.")


Answer = ProviderResult


class BrainProvider(ABC):
    name: str

    @abstractmethod
    def health_check(self) -> Health:
        raise NotImplementedError

    def available(self) -> bool:
        return self.health_check().ok

    @abstractmethod
    def ask(self, messages: Sequence[Message]) -> ProviderResult:
        raise NotImplementedError
