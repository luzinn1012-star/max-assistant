from typing import Any

from core.capabilities import Capability
from core.normalizer import normalize
from skills.base import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self.skills: list[Skill] = []
        self._intents: dict[str, Skill] = {}
        self.revision = 0

    def register(self, skill: Skill) -> None:
        for values in skill.required_capabilities.values():
            for value in values:
                Capability(value)
        for intent in skill.intents:
            if intent in self._intents:
                raise ValueError(f"Intent já registrada: {intent}")
        self.skills.append(skill)
        for intent in skill.intents:
            self._intents[intent] = skill
        self.revision += 1

    def get(self, intent: str) -> Skill | None:
        return self._intents.get(intent)

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "intents": list(skill.intents),
                "aliases": skill.aliases,
                "risk_level": {name: str(skill.risk_for_name(name)) for name in skill.intents}
                if hasattr(skill, "risk_for_name")
                else str(skill.risk_level),
                "capabilities": {
                    name: sorted(skill.required_capabilities.get(name, ()))
                    for name in skill.intents
                },
                "requires_confirmation": skill.requires_confirmation,
            }
            for skill in self.skills
        ]


def alias_index(groups: dict[str, list[str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for canonical, aliases in groups.items():
        for alias in [canonical, *aliases]:
            normalized = normalize(alias)
            if normalized in result and result[normalized] != canonical:
                raise ValueError(f"Alias ambíguo: {normalized}")
            result[normalized] = canonical
    return result
