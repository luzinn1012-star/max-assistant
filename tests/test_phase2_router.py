from dataclasses import replace
import unittest

from config import Settings
from core.intent import Intent, Rule
from core.normalizer import normalize
from core.router import Router
from skills.bootstrap import build_registry
from skills.help import HelpSkill
from skills.registry import SkillRegistry, alias_index
from tests.phase2_doubles import FakeAudio, FakeWindows


class NormalizerTests(unittest.TestCase):
    def test_accents(self):
        self.assertEqual(normalize("CONFIGURAÇÕES ÁUDIO"), "configuracoes audio")

    def test_punctuation_and_spaces(self):
        self.assertEqual(normalize("  Max,  abre o Spotify!  "), "abre o spotify")

    def test_optional_prefixes(self):
        for text in ("Max abra Spotify", "Ei Max, abra Spotify", "Olá Max! abra Spotify", "Max por favor abra Spotify"):
            with self.subTest(text=text):
                self.assertEqual(normalize(text), "abra spotify")

    def test_politeness_at_end(self):
        self.assertEqual(normalize("Max, abre o Spotify por favor."), "abre o spotify")

    def test_preserves_volume_parameters(self):
        self.assertEqual(normalize("Max, volume -30,5%."), "volume -30.5%")

    def test_does_not_strip_name_inside_word_or_sentence(self):
        self.assertEqual(normalize("maximum"), "maximum")
        self.assertEqual(normalize("diga max"), "diga max")

    def test_preserves_command_separator_and_quoted_data(self):
        self.assertIn(";", normalize("abre spotify; fecha discord"))
        self.assertIn('"', normalize('explique "abra spotify"'))


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_registry(Settings(), FakeWindows(), lambda: FakeAudio())
        self.router = Router(self.registry)

    def route(self, text):
        return self.router.route(normalize(text))

    def test_open_spotify(self):
        intent = self.route("Max, abra o Spotify.")
        self.assertEqual(intent.intent, "open_app")
        self.assertEqual(intent.slots, {"app": "spotify"})
        self.assertGreater(intent.confidence, .8)

    def test_open_discord(self):
        self.assertEqual(self.route("abrir discord").slots, {"app": "discord"})

    def test_close_app(self):
        self.assertEqual(self.route("fecha o spotify").intent, "close_app")

    def test_downloads(self):
        self.assertEqual(self.route("abre downloads").slots, {"folder": "downloads"})

    def test_volume_thirty(self):
        self.assertEqual(self.route("volume 30").slots, {"value": 30.0})

    def test_volume_hundred(self):
        self.assertEqual(self.route("volume 100").slots, {"value": 100.0})

    def test_volume_percent_and_polite_form(self):
        self.assertEqual(self.route("coloca o volume em 60%").slots, {"value": 60.0})

    def test_invalid_volume_is_local_validation(self):
        intent = self.route("volume alto")
        self.assertEqual(intent.intent, "set_volume")
        self.assertEqual(intent.slots, {"invalid": True})

    def test_mute(self):
        for text in ("mute", "muta o pc", "mute o computador"):
            with self.subTest(text=text):
                self.assertEqual(self.route(text).intent, "mute_volume")

    def test_unmute(self):
        for text in ("unmute", "tira do mudo"):
            with self.subTest(text=text):
                self.assertEqual(self.route(text).intent, "unmute_volume")

    def test_status(self):
        for text in ("como está o pc?", "quanta ram estou usando?", "qual o uso da cpu?"):
            with self.subTest(text=text):
                self.assertEqual(self.route(text).intent, "system_status")

    def test_help(self):
        self.assertEqual(self.route("ajuda").intent, "help")

    def test_unknown_conversation(self):
        self.assertEqual(self.route("Max, explique relatividade.").intent, "unknown")

    def test_unknown_app_does_not_invent_slot(self):
        intent = self.route("abra aplicativo misterioso")
        self.assertLess(intent.confidence, .8)
        self.assertEqual(intent.slots, {})

    def test_generic_music_is_not_an_action(self):
        self.assertEqual(self.route("música").intent, "unknown")
        self.assertEqual(self.route("abra música").slots, {"app": "spotify"})
        self.assertEqual(self.route("abra pasta Music").slots, {"folder": "music"})

    def test_no_partial_or_negative_commands(self):
        for text in ("não abra spotify", "abra spotify e discord", "explique como abrir spotify", "abra spotify; fecha discord"):
            with self.subTest(text=text):
                self.assertLess(self.route(text).confidence, .8)

    def test_registered_app_aliases(self):
        expected = {"disc": "discord", "calc": "calculator", "bloco de notas": "notepad",
                    "explorador de arquivos": "explorer", "configurações": "settings", "navegador": "browser"}
        for alias, app in expected.items():
            with self.subTest(alias=alias):
                self.assertEqual(self.route("abra " + alias).slots, {"app": app})

    def test_all_folder_names(self):
        for alias, folder in {"Desktop": "desktop", "área de trabalho": "desktop", "Documents": "documents",
                              "documentos": "documents", "Pictures": "pictures", "imagens": "pictures",
                              "vídeos": "videos", "Videos": "videos", "músicas": "music"}.items():
            with self.subTest(alias=alias):
                self.assertEqual(self.route("abra " + alias).slots, {"folder": folder})

    def test_conflicting_rules_do_not_choose_an_arbitrary_action(self):
        from skills.base import Skill, SkillResult
        class ConflictingSkill(Skill):
            name = "conflict"
            description = "Teste"
            intents = ("other_intent",)
            rules = (Rule("abra spotify", lambda m: Intent("other_intent", .99)),)
            def execute(self, intent, prepared):
                return SkillResult("Nunca chamado.")
        self.registry.register(ConflictingSkill())
        self.assertEqual(self.route("abra spotify").intent, "unknown")

    def test_registry_rejects_duplicate_intent(self):
        with self.assertRaises(ValueError):
            self.registry.register(HelpSkill())

    def test_registry_metadata(self):
        descriptions = {item["name"]: item for item in self.registry.describe()}
        self.assertEqual(set(descriptions), {"apps", "volume", "folders", "system", "help"})
        self.assertEqual(descriptions["apps"]["risk_level"]["close_app"], "CONFIRM")

    def test_registry_rejects_alias_collision(self):
        with self.assertRaises(ValueError):
            alias_index({"first": ["teste"], "second": ["tésté"]})

    def test_router_recognizes_skill_registered_later(self):
        registry = SkillRegistry()
        router = Router(registry)
        registry.register(HelpSkill())
        self.assertEqual(router.route("ajuda").intent, "help")
