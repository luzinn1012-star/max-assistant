from core.intent import Intent, Rule
from skills.base import Skill, SkillResult


def format_status(data, section="summary"):
    def decimal(value):
        return f"{value:.1f}".replace(".", ",")
    summary = (f"CPU {data['cpu_percent']:.0f}%, RAM {decimal(data['ram_used_gib'])} de "
               f"{decimal(data['ram_total_gib'])} GiB, disco {data['drive']} com "
               f"{data['disk_free_gib']:.0f} GiB livres.")
    if section == "processes":
        names = ", ".join(f"{p['name']} ({p['cpu_percent']:.0f}% CPU)" for p in data["top_processes"])
        return "Principais processos: " + (names or "nenhum disponível") + "."
    if section == "uptime":
        hours = data["uptime_seconds"] // 3600
        return f"Computador ligado há {hours} horas."
    if section == "gpu":
        return "Uso de GPU indisponível nesta fase; não vou estimar uma medição."
    return summary


class SystemSkill(Skill):
    name = "system"
    description = "Consulta CPU, RAM, disco, processos e tempo ligado."
    intents = ("system_status",)
    aliases = {"system_status": ["como está o pc", "status do sistema"]}

    def __init__(self, backend):
        self.backend = backend
        self.rules = (
            Rule(r"(?:como esta (?:o|meu) (?:pc|computador)|status(?: do (?:sistema|pc|computador))?)", lambda m: Intent("system_status", .99, {"section": "summary"})),
            Rule(r"(?:quanta ram (?:estou usando|esta em uso)|qual (?:e )?o uso (?:da|de) (?:cpu|ram)|uso (?:da|de) (?:cpu|ram)|quanto espaco (?:livre )?(?:no|tem no) disco)", lambda m: Intent("system_status", .99, {"section": "summary"})),
            Rule(r"(?:processos|principais processos|quais (?:sao )?os processos principais)", lambda m: Intent("system_status", .99, {"section": "processes"})),
            Rule(r"(?:uptime|ha quanto tempo (?:o )?(?:pc|computador) esta ligado)", lambda m: Intent("system_status", .99, {"section": "uptime"})),
            Rule(r"(?:uso da gpu|qual o uso da gpu)", lambda m: Intent("system_status", .99, {"section": "gpu"})),
        )

    def execute(self, intent, prepared):
        data = self.backend.system_status()
        return SkillResult(format_status(data, prepared.get("section", "summary")), data=data)
