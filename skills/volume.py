from automation.contracts import AudioFactory
from core.capabilities import Capability
from core.errors import InvalidParameter
from core.intent import Intent, Rule
from skills.base import Skill, SkillError, SkillResult


def clamp(value):
    return max(0.0, min(100.0, float(value)))


class VolumeSkill(Skill):
    name = "volume"
    description = "Volume e mute do dispositivo de saída padrão do Windows."
    intents = ("set_volume", "mute_volume", "unmute_volume")
    aliases = {"mute_volume": ["mute", "muta o pc"], "unmute_volume": ["unmute", "tira do mudo"]}

    required_capabilities = {
        name: frozenset({Capability.AUDIO_READ, Capability.AUDIO_WRITE})
        for name in ("set_volume", "mute_volume", "unmute_volume")
    }

    def __init__(self, audio: AudioFactory, step: int = 10) -> None:
        self.audio = audio
        self.step = step
        number = r"(?P<value>[+-]?\d+(?:\.\d+)?)"
        self.rules = (
            Rule(
                r"(?:(?:coloca|coloque|ajusta|ajuste|define|defina) (?:o )?)?volume(?: (?:em|para))? "
                + number
                + r"\s*%?",
                lambda m: Intent("set_volume", 0.99, {"value": float(m["value"])}),
            ),
            Rule(
                r"(aumenta|aumente|sobe|suba)(?: o)? volume",
                lambda m: Intent("set_volume", 0.99, {"delta": self.step}),
            ),
            Rule(
                r"(diminui|diminua|abaixa|abaixe)(?: o)? volume",
                lambda m: Intent("set_volume", 0.99, {"delta": -self.step}),
            ),
            Rule(
                r"(?:mute|muta|mute o|muta o)(?: (?:pc|computador|som|audio))?",
                lambda m: Intent("mute_volume", 0.99),
            ),
            Rule(
                r"(?:unmute|tira do mudo|tire do mudo|desmuta(?: o (?:pc|computador))?)",
                lambda m: Intent("unmute_volume", 0.99),
            ),
            Rule(
                r"(?:volume|(?:coloca|coloque|ajusta|ajuste) (?:o )?volume)(?: .*)?",
                lambda m: Intent("set_volume", 0.90, {"invalid": True}),
            ),
        )

    def validate(self, intent):
        super().validate(intent)
        import math

        slots = intent.slots
        if intent.intent == "set_volume":
            keys = set(slots)
            if keys not in ({"value"}, {"delta"}) or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in slots.values()
            ):
                raise InvalidParameter(
                    "invalid_volume", "Informe um volume numérico, por exemplo: volume 30."
                )

    def execute(self, intent, prepared):
        # A leitura e a alteração usam o mesmo endpoint COM.
        with self.audio() as device:
            if intent.intent == "set_volume":
                target = prepared.get("value")
                if target is None:
                    target = device.state()["volume"] + prepared["delta"]
                device.set_volume(clamp(target))
            else:
                device.set_mute(intent.intent == "mute_volume")
            state = device.state()
            if intent.intent == "set_volume" and abs(state["volume"] - clamp(target)) > 1.0:
                raise SkillError(
                    "volume_not_applied", "O dispositivo não confirmou a alteração do volume."
                )
            if intent.intent != "set_volume" and state["muted"] != (intent.intent == "mute_volume"):
                raise SkillError(
                    "mute_not_applied", "O dispositivo não confirmou a alteração do mudo."
                )
        if intent.intent == "set_volume":
            suffix = " O áudio continua no mudo." if state["muted"] else ""
            text = f"Volume em {state['volume']:g}%." + suffix
        else:
            text = "Áudio no mudo." if state["muted"] else "Áudio fora do mudo."
        return SkillResult(text, data=state)
