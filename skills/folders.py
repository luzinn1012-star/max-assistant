from core.intent import Intent, Rule
from skills.base import Skill, SkillError, SkillResult
from skills.registry import alias_index

FOLDER_ALIASES = {
    "desktop": ["área de trabalho", "area de trabalho"],
    "downloads": ["download"],
    "documents": ["documentos", "documents"],
    "pictures": ["imagens", "fotos", "pictures"],
    "videos": ["vídeos", "videos"],
    "music": ["músicas", "musicas", "music", "música", "musica"],
}


class FoldersSkill(Skill):
    name = "folders"
    description = "Abre pastas conhecidas do usuário, inclusive redirecionadas."
    intents = ("open_folder",)
    aliases = FOLDER_ALIASES

    def __init__(self, backend):
        self.backend = backend
        self.index = alias_index(self.aliases)
        self.rules = (
            Rule(r"(?:abre|abra|abrir)(?: a)? pasta (?P<folder>.+)", self._explicit),
            Rule(r"(?:abre|abra|abrir)(?: os| as| o| a)? (?P<folder>.+)", self._implicit),
        )

    def _explicit(self, match):
        target = self.index.get(match["folder"])
        return Intent("open_folder", .99, {"folder": target}) if target else Intent("open_folder", .3)

    def _implicit(self, match):
        target = self.index.get(match["folder"])
        # "abre música/music" é alias explícito de aplicativo; "pasta music" é pasta.
        if match["folder"] in {"musica", "music"}:
            return Intent()
        return Intent("open_folder", .99, {"folder": target}) if target else Intent()

    def validate(self, intent):
        super().validate(intent)
        if intent.slots.get("folder") not in self.aliases:
            raise SkillError("unknown_folder", "Essa pasta não está cadastrada.")

    def execute(self, intent, prepared):
        path = self.backend.known_folder(prepared["folder"])
        if not path.is_dir():
            raise SkillError("folder_missing", "A pasta cadastrada pelo Windows não existe.")
        self.backend.open_path(path)
        return SkillResult("Solicitei a abertura da pasta.", status="launch_requested",
                           data={"folder": prepared["folder"], "path": str(path)})
