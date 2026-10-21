"""Doubles sem chamadas a Win32, áudio real, shell ou rede."""
from pathlib import Path
from brain.provider import Answer, BrainProvider, Health, ProviderError
from skills.base import SkillError
from automation.windows import WindowsBackend


class SpyBrain(BrainProvider):
    def __init__(self, name, *, fail=False):
        self.name = name
        self.fail = fail
        self.ask_calls = []
        self.health_calls = 0

    def health_check(self):
        self.health_calls += 1
        return Health(self.name, True, "double")

    def ask(self, messages):
        self.ask_calls.append(list(messages))
        if self.fail:
            raise ProviderError(self.name, "timeout", "Timeout de teste.")
        return Answer("Resposta do cérebro de teste.", self.name, "double")


class FakeAudio:
    def __init__(self, volume=50.0, muted=False):
        self.volume = volume
        self.muted = muted
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def state(self):
        return {"volume": float(self.volume), "muted": self.muted}

    def set_volume(self, value):
        self.volume = value
        self.calls.append(("volume", value))

    def set_mute(self, value):
        self.muted = value
        self.calls.append(("mute", value))


class FakeWindows:
    def __init__(self):
        self.running = set()
        self.calls = []
        self.focus_allowed = True
        self.launch_verified = True
        self.folder_path = Path(__file__).resolve().parent
        self.snapshot = [{"hwnd": 101, "pid": 200, "created": 300.0, "visible": True}]

    def windows(self, spec):
        self.calls.append(("windows", spec.id))
        return [dict(item) for item in self.snapshot] if spec.id in self.running else []

    def focus(self, window):
        self.calls.append(("focus", window["hwnd"]))
        return self.focus_allowed

    def launch(self, spec):
        self.calls.append(("launch", spec.id))
        self.running.add(spec.id)
        return "uri" if spec.uri else "executable"

    def observe_launch(self, spec):
        return {"state": "running" if self.launch_verified else "launch_requested", "verified": self.launch_verified}

    def prepare_close(self, spec):
        WindowsBackend.prepare_close_policy(self, spec)
        windows = self.windows(spec)
        if not windows:
            raise SkillError("no_window", "Nenhuma janela de teste.")
        return windows

    def request_close(self, spec, windows):
        WindowsBackend.prepare_close_policy(self, spec)
        if windows != self.snapshot:
            raise SkillError("target_changed", "A janela mudou.")
        self.calls.append(("close", spec.id))
        self.running.discard(spec.id)
        return len(windows)

    def known_folder(self, folder):
        self.calls.append(("known_folder", folder))
        return self.folder_path

    def open_path(self, path):
        self.calls.append(("open_path", path))

    def system_status(self):
        self.calls.append(("system_status",))
        return {
            "cpu_percent": 18.0, "ram_used_gib": 9.2, "ram_total_gib": 16.0,
            "disk_free_gib": 120.0, "disk_total_gib": 500.0, "drive": "X:",
            "uptime_seconds": 7200, "top_processes": [{"name": "teste.exe", "cpu_percent": 5.0, "ram_mib": 100}],
            "gpu": None, "gpu_reason": "double",
        }
