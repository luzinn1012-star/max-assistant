"""Regras vêm das skills registradas. Nenhum provider é consultado aqui."""
import re
from core.intent import Intent


class Router:
    def __init__(self, registry):
        self.registry = registry
        self._revision = -1
        self.rules = []

    def route(self, normalized: str) -> Intent:
        if self._revision != self.registry.revision:
            self.rules = [(re.compile(rule.pattern), rule.resolve) for skill in self.registry.skills for rule in skill.rules]
            self._revision = self.registry.revision
        candidates = []
        for pattern, resolve in self.rules:
            match = pattern.fullmatch(normalized)
            if match:
                candidates.append(resolve(match))
        if not candidates:
            return Intent()
        winner = max(candidates, key=lambda item: item.confidence)
        tied = [item for item in candidates if item.confidence == winner.confidence]
        if any(item.intent != winner.intent or item.slots != winner.slots for item in tied):
            return Intent()  # Regras igualmente fortes e contraditórias são ambíguas.
        return winner
