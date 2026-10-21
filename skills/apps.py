from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from core.intent import Intent, Rule
from core.permissions import RiskLevel
from skills.base import Skill, SkillError, SkillResult
from skills.registry import alias_index


@dataclass(frozen=True)
class AppSpec:
    id: str
    label: str
    aliases: list[str]
    process_names: list[str]
    uri: str = ""
    executables: list[str] = field(default_factory=list)
    arguments: list[str] = field(default_factory=list)
    allow_close: bool = False


def load_apps(path: Path):
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            raise ValueError()
        result = {}
        for entry in raw:
            spec = AppSpec(**entry)
            if not re.fullmatch(r"[a-z][a-z0-9_]*", spec.id) or spec.id in result:
                raise ValueError()
            if not isinstance(spec.label, str) or not spec.label or type(spec.allow_close) is not bool:
                raise ValueError()
            for values in (spec.aliases, spec.process_names, spec.executables, spec.arguments):
                if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                    raise ValueError()
            if not isinstance(spec.uri, str) or any("/" in name or "\\" in name for name in spec.process_names):
                raise ValueError()
            result[spec.id] = spec
        return result
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError("Cadastro de aplicativos inválido em apps.json.") from None


class AppsSkill(Skill):
    name = "apps"
    description = "Abre aplicativos cadastrados; pede confirmação para fechar janelas normalmente."
    intents = ("open_app", "close_app")
    requires_confirmation = {"open_app": False, "close_app": True}

    def __init__(self, backend, apps):
        self.backend = backend
        self.apps = apps
        self.aliases = {key: spec.aliases for key, spec in apps.items()}
        self.index = alias_index(self.aliases)
        self.rules = (
            Rule(r"(?:abre|abra|abrir)(?: o| a)? (?P<app>.+)", lambda m: self._match(m, "open_app")),
            Rule(r"(?:fecha|feche|fechar)(?: o| a)? (?P<app>.+)", lambda m: self._match(m, "close_app")),
        )

    def _match(self, match, intent):
        app = self.index.get(match["app"])
        return Intent(intent, .99, {"app": app}) if app else Intent(intent, .25)

    def risk_for_name(self, name):
        return RiskLevel.CONFIRM if name == "close_app" else RiskLevel.SAFE

    def risk_for(self, intent):
        return self.risk_for_name(intent.intent)

    def validate(self, intent):
        super().validate(intent)
        if intent.slots.get("app") not in self.apps:
            raise SkillError("unknown_app", "Esse aplicativo não está cadastrado.")

    def prepare(self, intent):
        super().prepare(intent)
        spec = self.apps[intent.slots["app"]]
        prepared = dict(intent.slots)
        if intent.intent == "close_app":
            prepared["windows"] = self.backend.prepare_close(spec)
        return prepared

    def confirmation_prompt(self, intent):
        return f"Quer que eu feche {self.apps[intent.slots['app']].label}?"

    def execute(self, intent, prepared):
        spec = self.apps[prepared["app"]]
        if intent.intent == "close_app":
            count = self.backend.request_close(spec, prepared["windows"])
            return SkillResult(f"Solicitei o fechamento de {spec.label}. Um aviso de salvamento ou a bandeja pode manter o app aberto.",
                               status="close_requested", data={"windows_notified": count})
        windows = self.backend.windows(spec)
        if windows:
            focused = self.backend.focus(windows[0])
            text = f"{spec.label} já estava aberto."
            text += " Trouxe a janela para frente." if focused else " O Windows não permitiu mudar o foco."
            return SkillResult(text, data={"app": spec.id, "state": "already_running", "focused": focused, "verified": True})
        method = self.backend.launch(spec)
        state = self.backend.observe_launch(spec)
        text = f"{spec.label} está em execução." if state["verified"] else f"Solicitei a abertura de {spec.label}."
        return SkillResult(text, status=state["state"], data={"app": spec.id, "method": method, **state})
