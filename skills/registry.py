from core.normalizer import normalize


class SkillRegistry:
    def __init__(self):
        self.skills = []
        self._intents = {}
        self.revision = 0

    def register(self, skill):
        for intent in skill.intents:
            if intent in self._intents:
                raise ValueError(f"Intent já registrada: {intent}")
        self.skills.append(skill)
        for intent in skill.intents:
            self._intents[intent] = skill
        self.revision += 1

    def get(self, intent):
        return self._intents.get(intent)

    def describe(self):
        return [{"name": skill.name, "description": skill.description, "intents": list(skill.intents),
                 "aliases": skill.aliases,
                 "risk_level": {name: str(skill.risk_for_name(name)) for name in skill.intents}
                    if hasattr(skill, "risk_for_name") else str(skill.risk_level),
                 "requires_confirmation": skill.requires_confirmation} for skill in self.skills]


def alias_index(groups):
    result = {}
    for canonical, aliases in groups.items():
        for alias in [canonical, *aliases]:
            normalized = normalize(alias)
            if normalized in result and result[normalized] != canonical:
                raise ValueError(f"Alias ambíguo: {normalized}")
            result[normalized] = canonical
    return result
