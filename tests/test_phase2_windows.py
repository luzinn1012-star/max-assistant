import ctypes as C
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import psutil

from automation.audio import AudioEndpoint, GUID, check
from automation.windows import WindowsBackend
from brain.ollama_provider import OllamaProvider
from config import Settings
from core.intent import Intent
from skills.apps import AppSpec
from skills.base import SkillError


class WindowsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.backend = WindowsBackend(launch_timeout=.01)
        self.spec = AppSpec("editor", "Editor", ["editor"], ["editor.exe"], "editor:", [], [], True)

    def test_uri_has_priority(self):
        with patch.object(self.backend, "protocol_exists", return_value=True), patch.object(self.backend, "shell_open") as opening:
            self.assertEqual(self.backend.launch(self.spec), "uri")
        opening.assert_called_once_with("editor:")

    def test_executable_is_used_when_protocol_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "editor.exe"
            executable.touch()
            spec = AppSpec("editor", "Editor", [], ["editor.exe"], "editor:", [str(executable)], ["--test"])
            with patch.object(self.backend, "protocol_exists", return_value=False), patch.object(self.backend, "shell_open") as opening:
                self.assertEqual(self.backend.launch(spec), "executable")
            opening.assert_called_once_with(executable, ["--test"])

    def test_failed_uri_uses_known_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "editor.exe"
            executable.touch()
            spec = AppSpec("editor", "Editor", [], ["editor.exe"], "editor:", [str(executable)])
            with patch.object(self.backend, "protocol_exists", return_value=True), patch.object(
                self.backend, "shell_open", side_effect=[SkillError("failed", "Falhou."), None]
            ) as opening:
                self.assertEqual(self.backend.launch(spec), "executable")
            self.assertEqual(opening.call_count, 2)

    def test_missing_application_is_error(self):
        with patch.object(self.backend, "protocol_exists", return_value=False):
            with self.assertRaises(SkillError) as caught:
                self.backend.launch(self.spec)
        self.assertEqual(caught.exception.code, "app_not_installed")

    def test_unverified_launch_is_not_success_claim(self):
        with patch.object(self.backend, "processes", return_value={}):
            result = self.backend.observe_launch(self.spec)
        self.assertFalse(result["verified"])
        self.assertEqual(result["state"], "launch_requested")

    def test_observed_process_verifies_launch(self):
        with patch.object(self.backend, "processes", return_value={42: {}}):
            result = self.backend.observe_launch(self.spec)
        self.assertTrue(result["verified"])

    def test_protected_names_are_denied_even_if_catalog_allows(self):
        for name in ("explorer.exe", "lsass.exe", "svchost.exe", "services.exe"):
            spec = AppSpec("protected", "Protected", [], [name], allow_close=True)
            with self.subTest(name=name), self.assertRaises(SkillError):
                self.backend.prepare_close_policy(spec)

    def test_services_are_protected(self):
        snapshot = [{"hwnd": 101, "pid": 200, "created": 300.0}]
        with patch.object(self.backend, "windows", return_value=snapshot), patch.object(
            self.backend, "_service_pids", return_value={200}
        ):
            with self.assertRaises(SkillError) as caught:
                self.backend.prepare_close(self.spec)
        self.assertEqual(caught.exception.code, "service_protected")

    def test_failed_service_inspection_fails_closed(self):
        with patch("automation.windows.psutil.win_service_iter", side_effect=psutil.AccessDenied()):
            with self.assertRaises(SkillError) as caught:
                self.backend._service_pids()
        self.assertEqual(caught.exception.code, "service_check_denied")

    def test_changed_process_identity_blocks_close(self):
        self.backend._user32 = MagicMock()
        old = [{"hwnd": 101, "pid": 200, "created": 300.0}]
        new = [{"hwnd": 101, "pid": 200, "created": 999.0}]
        with patch.object(self.backend, "windows", return_value=new), patch.object(self.backend, "_service_pids", return_value=set()):
            with self.assertRaises(SkillError) as caught:
                self.backend.request_close(self.spec, old)
        self.assertEqual(caught.exception.code, "target_changed")
        self.backend._user32.PostMessageW.assert_not_called()

    def test_close_posts_normal_window_close_only(self):
        self.backend._user32 = MagicMock()
        self.backend._user32.PostMessageW.return_value = True
        snapshot = [{"hwnd": 101, "pid": 200, "created": 300.0}]
        with patch.object(self.backend, "windows", return_value=snapshot), patch.object(
            self.backend, "_service_pids", return_value=set()
        ), patch("automation.windows.psutil.Process") as process:
            self.assertEqual(self.backend.request_close(self.spec, snapshot), 1)
        self.backend._user32.PostMessageW.assert_called_once_with(101, 0x0010, 0, 0)
        process.assert_not_called()

    def test_close_rechecks_service_ownership_after_confirmation(self):
        self.backend._user32 = MagicMock()
        snapshot = [{"hwnd": 101, "pid": 200, "created": 300.0}]
        with patch.object(self.backend, "windows", return_value=snapshot), patch.object(self.backend, "_service_pids", return_value={200}):
            with self.assertRaises(SkillError):
                self.backend.request_close(self.spec, snapshot)
        self.backend._user32.PostMessageW.assert_not_called()

    def test_windows_refusing_close_is_error(self):
        self.backend._user32 = MagicMock()
        self.backend._user32.PostMessageW.return_value = False
        snapshot = [{"hwnd": 101, "pid": 200, "created": 300.0}]
        with patch.object(self.backend, "windows", return_value=snapshot), patch.object(self.backend, "_service_pids", return_value=set()):
            with self.assertRaises(SkillError) as caught:
                self.backend.request_close(self.spec, snapshot)
        self.assertEqual(caught.exception.code, "close_denied")

    def test_known_folder_uses_system_api_and_frees_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            buffer = C.create_unicode_buffer(directory)
            shell, ole = MagicMock(), MagicMock()
            def get_folder(guid, flags, token, output):
                C.cast(output, C.POINTER(C.c_void_p))[0] = C.cast(buffer, C.c_void_p)
                return 0
            shell.SHGetKnownFolderPath.side_effect = get_folder
            with patch("automation.windows.C.WinDLL", side_effect=[shell, ole]):
                path = self.backend.known_folder("downloads")
            self.assertEqual(path, Path(directory))
            shell.SHGetKnownFolderPath.assert_called_once()
            ole.CoTaskMemFree.assert_called_once()

    def test_system_measurement_and_drive_are_dynamic(self):
        memory = MagicMock(total=16 * 2**30, available=6 * 2**30)
        disk = MagicMock(free=120 * 2**30, total=500 * 2**30)
        with patch("automation.windows.psutil.process_iter", return_value=[]), patch(
            "automation.windows.psutil.cpu_percent", side_effect=[0, 18]
        ), patch("automation.windows.psutil.virtual_memory", return_value=memory), patch(
            "automation.windows.psutil.disk_usage", return_value=disk
        ) as usage, patch("automation.windows.psutil.boot_time", return_value=100), patch(
            "automation.windows.time.time", return_value=7300
        ), patch("automation.windows.time.sleep"), patch.dict("os.environ", {"SystemDrive": "Z:"}):
            state = self.backend.system_status()
        self.assertEqual(state["cpu_percent"], 18)
        self.assertEqual(state["ram_used_gib"], 10)
        self.assertEqual(state["drive"], "Z:")
        self.assertEqual(state["uptime_seconds"], 7200)
        usage.assert_called_once_with("Z:\\")


class AudioAdapterTests(unittest.TestCase):
    def test_guid_layout_is_sixteen_bytes(self):
        self.assertEqual(C.sizeof(GUID), 16)
        self.assertEqual(GUID.parse("5CDF2C82-841E-4546-9722-0CF74078229A").Data1, 0x5CDF2C82)

    def test_hresult_failure_is_reported(self):
        with self.assertRaises(SkillError):
            check(-1)
        check(0)

    def test_volume_and_mute_use_endpoint_api_methods(self):
        device = AudioEndpoint()
        device.endpoint = C.c_void_p(1)
        with patch("automation.audio.call") as invoke:
            device.set_volume(30)
            device.set_mute(True)
        self.assertEqual(invoke.call_args_list[0].args[1], 7)
        self.assertAlmostEqual(invoke.call_args_list[0].args[3].value, .3, places=6)
        self.assertEqual(invoke.call_args_list[1].args[1], 14)
        self.assertEqual(invoke.call_args_list[1].args[3], 1)

    def test_state_reads_volume_and_mute_via_api(self):
        device = AudioEndpoint()
        device.endpoint = C.c_void_p(1)
        def invoke(pointer, index, types, output):
            if index == 9:
                C.cast(output, C.POINTER(C.c_float))[0] = .3
            elif index == 15:
                C.cast(output, C.POINTER(C.c_int))[0] = 1
        with patch("automation.audio.call", side_effect=invoke):
            self.assertEqual(device.state(), {"volume": 30.0, "muted": True})

    def test_http_error_response_is_closed(self):
        body = io.BytesIO(b"SECRET_TEST")
        error = HTTPError("http://127.0.0.1", 503, "test", {}, body)
        provider = OllamaProvider(Settings())
        with patch.object(provider.http, "open", side_effect=error):
            self.assertFalse(provider.health_check().ok)
        self.assertTrue(body.closed)
