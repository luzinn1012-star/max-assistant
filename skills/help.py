from core.intent import Intent, Rule
from skills.base import Skill, SkillResult


class HelpSkill(Skill):
    name = "help"
    description = "Mostra comandos locais disponíveis."
    intents = ("help",)
    aliases = {"help": ["ajuda", "help", "comandos"]}
    rules = (Rule(r"(?:ajuda|help|comandos|o que voce pode fazer)", lambda m: Intent("help", 1.0)),)

    def execute(self, intent, prepared):
        return SkillResult("Posso abrir aplicativos e pastas, ajustar volume, ativar ou tirar o mudo e consultar o PC. "
                           "Exemplos: abra Spotify; abra Downloads; volume 30; como está o PC. "
                           "Para fechar um aplicativo, peço confirmação. Para conversar, escreva normalmente.")
