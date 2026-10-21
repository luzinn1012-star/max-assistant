"""APIs Win32 com argumentos tipados e execução somente de alvos cadastrados."""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import time

import psutil

from automation.audio import GUID
from skills.base import SkillError

PROTECTED = {"explorer.exe", "system", "registry", "smss.exe", "csrss.exe", "wininit.exe",
             "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
             "sihost.exe", "taskhostw.exe", "fontdrvhost.exe", "securityhealthservice.exe"}

KNOWN_FOLDERS = {
    "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "downloads": "374DE290-123F-4565-9164-39C4925E467B",
    "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "pictures": "33E28130-4E1E-4676-835A-98395C3BC3BB",
    "videos": "18989B1D-99B5-455B-841C-AB7C74E4DDFC",
    "music": "4BD8D571-6D19-48D3-BE97-422220080E43",
}


class WindowsBackend:
    def __init__(self, launch_timeout=2.0):
        self.launch_timeout = launch_timeout
        self._user32 = None

    def _require_windows(self):
        if os.name != "nt":
            raise SkillError("windows_required", "Esta skill requer Windows.")

    @property
    def user32(self):
        self._require_windows()
        if self._user32 is None:
            api = C.WinDLL("user32", use_last_error=True)
            callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
            api.EnumWindows.argtypes = [callback, W.LPARAM]
            api.EnumWindows.restype = W.BOOL
            api.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
            api.GetWindowThreadProcessId.restype = W.DWORD
            api.GetWindowTextLengthW.argtypes = [W.HWND]
            api.GetWindowTextLengthW.restype = C.c_int
            api.IsWindowVisible.argtypes = [W.HWND]
            api.IsWindowVisible.restype = W.BOOL
            api.IsWindow.argtypes = [W.HWND]
            api.IsWindow.restype = W.BOOL
            api.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
            api.GetClassNameW.restype = C.c_int
            api.ShowWindowAsync.argtypes = [W.HWND, C.c_int]
            api.ShowWindowAsync.restype = W.BOOL
            api.SetForegroundWindow.argtypes = [W.HWND]
            api.SetForegroundWindow.restype = W.BOOL
            api.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
            api.PostMessageW.restype = W.BOOL
            self._callback_type = callback
            self._user32 = api
        return self._user32

    def processes(self, spec):
        names = {name.casefold() for name in spec.process_names}
        result = {}
        for process in psutil.process_iter(["pid", "name", "create_time"]):
            try:
                if (process.info["name"] or "").casefold() in names:
                    result[process.pid] = process.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return result

    def windows(self, spec):
        processes = self.processes(spec)
        if not processes:
            return []
        api = self.user32
        result = []
        @self._callback_type
        def visit(hwnd, unused):
            pid = W.DWORD()
            api.GetWindowThreadProcessId(hwnd, C.byref(pid))
            if pid.value not in processes or api.GetWindowTextLengthW(hwnd) == 0:
                return True
            cls = C.create_unicode_buffer(256)
            api.GetClassNameW(hwnd, cls, 256)
            # Nunca trate o desktop/taskbar como uma janela de app.
            if cls.value in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}:
                return True
            result.append({"hwnd": int(hwnd), "pid": pid.value,
                           "created": processes[pid.value]["create_time"],
                           "visible": bool(api.IsWindowVisible(hwnd))})
            return True
        api.EnumWindows(visit, 0)
        return sorted(result, key=lambda item: not item["visible"])

    def focus(self, window):
        api = self.user32
        if not api.IsWindow(window["hwnd"]):
            return False
        api.ShowWindowAsync(window["hwnd"], 9)  # SW_RESTORE
        return bool(api.SetForegroundWindow(window["hwnd"]))

    def protocol_exists(self, uri):
        self._require_windows()
        import winreg
        protocol = uri.split(":", 1)[0]
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, protocol):
                return True
        except OSError:
            return False

    def shell_open(self, target, arguments=None):
        self._require_windows()
        shell = C.WinDLL("shell32", use_last_error=True)
        shell.ShellExecuteW.argtypes = [W.HWND, W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, C.c_int]
        shell.ShellExecuteW.restype = C.c_void_p
        parameters = subprocess.list2cmdline(arguments) if arguments else None
        status = shell.ShellExecuteW(None, "open", str(target), parameters, None, 1)
        if not status or status <= 32:
            raise SkillError("launch_failed", "O Windows não conseguiu abrir o aplicativo ou pasta.")

    def launch(self, spec):
        if spec.uri and self.protocol_exists(spec.uri):
            try:
                self.shell_open(spec.uri)
                return "uri"
            except SkillError:
                pass
        for candidate in spec.executables:
            executable = Path(os.path.expandvars(candidate))
            if executable.is_file() and executable.suffix.lower() in {".exe", ".lnk"}:
                self.shell_open(executable, spec.arguments)
                return "shortcut" if executable.suffix.lower() == ".lnk" else "executable"
        raise SkillError("app_not_installed", "Não encontrei esse aplicativo instalado. Confira o cadastro em apps.json.")

    def observe_launch(self, spec):
        if not spec.process_names:
            return {"state": "launch_requested", "verified": False}
        deadline = time.monotonic() + self.launch_timeout
        while True:
            if self.processes(spec):
                return {"state": "running", "verified": True}
            if time.monotonic() >= deadline:
                return {"state": "launch_requested", "verified": False}
            time.sleep(.05)

    def prepare_close(self, spec):
        if not spec.allow_close or not spec.process_names or any(name.casefold() in PROTECTED for name in spec.process_names):
            raise SkillError("protected_app", "Não fecho esse aplicativo como processo comum.")
        windows = self.windows(spec)
        self._guard_service_windows(windows)
        if not windows:
            raise SkillError("no_window", "Não encontrei uma janela desse aplicativo para fechar normalmente.")
        return windows

    def request_close(self, spec, windows):
        # Revalida processo, criação e HWND após a confirmação; não aceita PIDs livres.
        self.prepare_close_policy(spec)
        observed = self.windows(spec)
        self._guard_service_windows(observed)
        current = {(item["hwnd"], item["pid"], item["created"]) for item in observed}
        targets = [item for item in windows if (item["hwnd"], item["pid"], item["created"]) in current]
        if not targets:
            raise SkillError("target_changed", "A janela mudou ou já foi fechada. Peça a ação novamente.")
        sent = 0
        for item in targets:
            if self.user32.PostMessageW(item["hwnd"], 0x0010, 0, 0):  # WM_CLOSE; nunca kill
                sent += 1
        if not sent:
            raise SkillError("close_denied", "O Windows não aceitou o pedido de fechamento.")
        return sent

    def prepare_close_policy(self, spec):
        if not spec.allow_close or not spec.process_names or any(name.casefold() in PROTECTED for name in spec.process_names):
            raise SkillError("protected_app", "Esse processo está protegido contra fechamento.")

    def _service_pids(self):
        try:
            return {pid for service in psutil.win_service_iter() if (pid := service.pid())}
        except (psutil.Error, OSError):
            raise SkillError("service_check_denied", "Não consegui verificar os serviços do Windows; o fechamento foi bloqueado.") from None

    def _guard_service_windows(self, windows):
        if not windows:
            return
        service_pids = self._service_pids()
        if any(item["pid"] in service_pids for item in windows):
            raise SkillError("service_protected", "Não encerro janelas pertencentes a serviços do Windows.")

    def known_folder(self, folder):
        self._require_windows()
        if folder not in KNOWN_FOLDERS:
            raise SkillError("unknown_folder", "Essa pasta não está cadastrada.")
        shell = C.WinDLL("shell32")
        ole = C.WinDLL("ole32")
        shell.SHGetKnownFolderPath.argtypes = [C.POINTER(GUID), W.DWORD, W.HANDLE, C.POINTER(C.c_void_p)]
        shell.SHGetKnownFolderPath.restype = C.c_long
        ole.CoTaskMemFree.argtypes = [C.c_void_p]
        pointer = C.c_void_p()
        identifier = GUID.parse(KNOWN_FOLDERS[folder])
        try:
            hr = shell.SHGetKnownFolderPath(C.byref(identifier), 0, None, C.byref(pointer))
            if hr < 0 or not pointer:
                raise SkillError("folder_lookup_failed", "O Windows não informou o caminho dessa pasta.")
            return Path(C.wstring_at(pointer))
        finally:
            if pointer:
                ole.CoTaskMemFree(pointer)

    def open_path(self, path):
        self.shell_open(path)

    def system_status(self):
        self._require_windows()
        sampled = []
        psutil.cpu_percent(None)
        for process in psutil.process_iter(["pid", "name"]):
            try:
                if process.pid:
                    process.cpu_percent(None)
                    sampled.append(process)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(.12)
        cpu = psutil.cpu_percent(None)
        processes = []
        for process in sampled:
            try:
                processes.append({"pid": process.pid, "name": process.name(),
                                  "cpu_percent": round(process.cpu_percent(None) / (psutil.cpu_count() or 1), 1),
                                  "ram_mib": round(process.memory_info().rss / 2**20, 1)})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        memory = psutil.virtual_memory()
        drive = os.environ.get("SystemDrive", Path(os.environ.get("SystemRoot", "C:\\Windows")).anchor).rstrip("\\/") + "\\"
        disk = psutil.disk_usage(drive)
        return {
            "cpu_percent": cpu, "ram_used_gib": (memory.total - memory.available) / 2**30,
            "ram_total_gib": memory.total / 2**30, "disk_free_gib": disk.free / 2**30,
            "disk_total_gib": disk.total / 2**30, "drive": drive.rstrip("\\"),
            "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
            "top_processes": sorted(processes, key=lambda p: (p["cpu_percent"], p["ram_mib"]), reverse=True)[:3],
            "gpu": None, "gpu_reason": "Sem medição portátil confiável nesta fase.",
        }
