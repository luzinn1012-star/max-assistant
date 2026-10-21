import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.intent import Intent
from core.permissions import RiskLevel
from skills.apps import AppsSkill, AppSpec, load_apps
from skills.base import SkillError
from skills.folders import FoldersSkill
from skills.system import SystemSkill, format_status
from skills.volume import VolumeSkill
from config import ROOT
from tests.phase2_doubles import FakeAudio, FakeWindows


class AppsSkillTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeWindows()
        self.skill = AppsSkill(self.backend, load_apps(ROOT / "apps.json"))

    def test_open_uses_registered_target(self):
        intent = Intent("open_app", .99, {"app": "spotify"})
        reply = self.skill.execute(intent, self.skill.prepare(intent))
        self.assertIn(("launch", "spotify"), self.backend.calls)
        self.assertTrue(reply.success)
        self.assertTrue(reply.data["verified"])

    def test_unknown_app_fails_validation(self):
        with self.assertRaises(SkillError):
            self.skill.prepare(Intent("open_app", .99, {"app": "misterio"}))
        self.assertEqual(self.backend.calls, [])

    def test_already_open_does_not_launch(self):
        self.backend.running.add("discord")
        intent = Intent("open_app", .99, {"app": "discord"})
        result = self.skill.execute(intent, self.skill.prepare(intent))
        self.assertIn(("focus", 101), self.backend.calls)
        self.assertFalse(any(call[0] == "launch" for call in self.backend.calls))
        self.assertEqual(result.data["state"], "already_running")

    def test_focus_denied_is_reported(self):
        self.backend.running.add("discord")
        self.backend.focus_allowed = False
        intent = Intent("open_app", .99, {"app": "discord"})
        result = self.skill.execute(intent, self.skill.prepare(intent))
        self.assertIn("não permitiu", result.text)
        self.assertFalse(result.data["focused"])

    def test_launch_request_is_not_claimed_as_verified(self):
        self.backend.launch_verified = False
        intent = Intent("open_app", .99, {"app": "spotify"})
        result = self.skill.execute(intent, self.skill.prepare(intent))
        self.assertEqual(result.status, "launch_requested")
        self.assertFalse(result.data["verified"])
        self.assertIn("Solicitei", result.text)

    def test_close_risk_is_confirm(self):
        self.assertEqual(self.skill.risk_for(Intent("close_app")), RiskLevel.CONFIRM)
        self.assertEqual(self.skill.risk_for(Intent("open_app")), RiskLevel.SAFE)

    def test_explorer_is_protected(self):
        with self.assertRaises(SkillError) as caught:
            self.skill.prepare(Intent("close_app", .99, {"app": "explorer"}))
        self.assertEqual(caught.exception.code, "protected_app")

    def test_prepare_close_does_not_close(self):
        self.backend.running.add("notepad")
        prepared = self.skill.prepare(Intent("close_app", .99, {"app": "notepad"}))
        self.assertEqual(prepared["windows"], self.backend.snapshot)
        self.assertFalse(any(call[0] == "close" for call in self.backend.calls))

    def test_catalog_rejects_malformed_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "apps.json"
            for data in ({}, ["invalid"], [{"id": "bad-id"}]):
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.subTest(data=data), self.assertRaises(ValueError):
                    load_apps(path)

    def test_catalog_can_add_application_and_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "apps.json"
            entry = {"id": "editor", "label": "Editor", "aliases": ["meu editor"],
                     "process_names": ["editor.exe"], "executables": ["%LOCALAPPDATA%/Editor/editor.exe"]}
            path.write_text(json.dumps([entry]), encoding="utf-8")
            skill = AppsSkill(self.backend, load_apps(path))
            self.assertEqual(skill.index["meu editor"], "editor")


class VolumeTests(unittest.TestCase):
    def setUp(self):
        self.audio = FakeAudio()
        self.skill = VolumeSkill(lambda: self.audio)

    def execute(self, **slots):
        intent = Intent("set_volume", .99, slots)
        return self.skill.execute(intent, self.skill.prepare(intent))

    def test_clamp_zero(self):
        self.execute(value=-5)
        self.assertEqual(self.audio.volume, 0)

    def test_clamp_hundred(self):
        self.execute(value=150)
        self.assertEqual(self.audio.volume, 100)

    def test_increment(self):
        self.execute(delta=10)
        self.assertEqual(self.audio.volume, 60)

    def test_decrement(self):
        self.execute(delta=-10)
        self.assertEqual(self.audio.volume, 40)

    def test_decimal(self):
        self.execute(value=32.5)
        self.assertEqual(self.audio.volume, 32.5)

    def test_invalid_and_nonfinite_values(self):
        for value in (True, "30", float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(SkillError):
                self.skill.prepare(Intent("set_volume", .99, {"value": value}))
        self.assertEqual(self.audio.calls, [])

    def test_mute_and_unmute(self):
        for intent, expected in (("mute_volume", True), ("unmute_volume", False)):
            self.skill.execute(Intent(intent), {})
            self.assertEqual(self.audio.muted, expected)

    def test_setting_volume_preserves_mute(self):
        self.audio.muted = True
        reply = self.execute(value=30)
        self.assertTrue(self.audio.muted)
        self.assertIn("continua no mudo", reply.text)

    def test_unapplied_volume_is_not_reported_as_success(self):
        with patch.object(self.audio, "set_volume"):
            with self.assertRaises(SkillError):
                self.execute(value=30)

    def test_unapplied_mute_is_not_reported_as_success(self):
        with patch.object(self.audio, "set_mute"):
            with self.assertRaises(SkillError):
                self.skill.execute(Intent("mute_volume"), {})


class FolderAndStatusTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeWindows()

    def test_folder_path_is_provided_dynamically(self):
        with tempfile.TemporaryDirectory() as directory:
            self.backend.folder_path = Path(directory)
            skill = FoldersSkill(self.backend)
            intent = Intent("open_folder", .99, {"folder": "downloads"})
            result = skill.execute(intent, skill.prepare(intent))
            self.assertEqual(result.data["path"], directory)
            self.assertIn(("open_path", Path(directory)), self.backend.calls)

    def test_unknown_folder_is_rejected(self):
        with self.assertRaises(SkillError):
            FoldersSkill(self.backend).prepare(Intent("open_folder", .99, {"folder": "arbitrary"}))

    def test_missing_folder_does_not_launch(self):
        self.backend.folder_path = Path("folder-that-does-not-exist-7bb8")
        skill = FoldersSkill(self.backend)
        with self.assertRaises(SkillError):
            skill.execute(Intent("open_folder"), {"folder": "downloads"})
        self.assertFalse(any(call[0] == "open_path" for call in self.backend.calls))

    def test_status_format_is_short_and_localized(self):
        text = format_status(self.backend.system_status())
        self.assertEqual(text, "CPU 18%, RAM 9,2 de 16,0 GiB, disco X: com 120 GiB livres.")

    def test_processes_format(self):
        text = format_status(self.backend.system_status(), "processes")
        self.assertIn("teste.exe", text)

    def test_uptime(self):
        self.assertIn("2 horas", format_status(self.backend.system_status(), "uptime"))

    def test_gpu_unavailable_is_explicit(self):
        self.assertIn("indisponível", format_status(self.backend.system_status(), "gpu"))
