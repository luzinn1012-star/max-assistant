"""FASE 2.1: validação nativa opt-in. Nenhuma skill ou recurso novo é implementado."""

from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

from automation.audio import AudioEndpoint
from automation.windows import WindowsBackend
from config import ROOT
from skills.apps import load_apps

REPORT = ROOT / "real-windows-validation.json"
COMMANDS = [
    ("calculator", "Max, abra a Calculadora.", "open_app", "apps"),
    ("discord", "Max, abra o Discord.", "open_app", "apps"),
    ("spotify", "Max, abra o Spotify.", "open_app", "apps"),
    ("downloads", "Max, abra Downloads.", "open_folder", "folders"),
    ("volume", "Max, volume 30.", "set_volume", "volume"),
    ("mute", "Max, mute.", "mute_volume", "volume"),
    ("unmute", "Max, unmute.", "unmute_volume", "volume"),
    ("system", "Max, como está o PC?", "system_status", "system"),
]


def timestamp():
    return datetime.now(UTC).isoformat()


def persist(report):
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def environment():
    result = os.environ.copy()
    result["PYTHONUTF8"] = "1"
    result["PYTHONIOENCODING"] = "utf-8"
    return result


def launcher_command(text=None, config=None):
    launcher = str(ROOT / "run-max.cmd")
    executable = os.environ.get("COMSPEC", "cmd.exe")
    tail = ""
    if text is not None:
        if any(char in text for char in '"&|<>^%\r\n'):
            raise ValueError("Texto de validação contém metacaractere de shell.")
        tail = f' --ask "{text}" --json'
    if config is not None:
        tail += f' --config "{config}"'
    return f'"{executable}" /d /s /c ""{launcher}"{tail}"'


def launch_normal():
    process = subprocess.Popen(
        launcher_command(),
        cwd=ROOT,
        env=environment(),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        shell=False,
    )
    time.sleep(0.8)
    children = (
        psutil.Process(process.pid).children(recursive=True) if process.poll() is None else []
    )
    return {
        "method": "run-max.cmd in a normal visible Windows console",
        "launcher_pid": process.pid,
        "alive": process.poll() is None,
        "python_children": [
            child.pid for child in children if child.name().lower().startswith("python")
        ],
    }


def invoke(text, config=None):
    started = time.perf_counter()
    process = subprocess.run(
        launcher_command(text, config),
        cwd=ROOT,
        env=environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=170,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    result = {
        "input": text,
        "exit_code": process.returncode,
        "wall_seconds": time.perf_counter() - started,
        "timestamp_utc": timestamp(),
    }
    try:
        reply = json.loads(process.stdout)
        if not isinstance(reply, dict):
            raise ValueError()
        result.update(reply)
    except ValueError:
        result.update(
            success=False,
            status="invalid_launcher_output",
            llm_used=None,
            technical_error={
                "code": "invalid_launcher_output",
                "stderr_excerpt": process.stderr[-1500:],
            },
        )
    return result


def audio_state():
    with AudioEndpoint() as device:
        return device.state()


def observe_app(backend, spec, timeout=12):
    deadline = time.monotonic() + timeout
    while True:
        windows = backend.windows(spec)
        processes = backend.processes(spec)
        visible = [window for window in windows if window.get("visible")]
        if visible or time.monotonic() >= deadline:
            return {
                "verified": bool(visible),
                "running": bool(processes),
                "visible_windows": visible,
                "process_ids": sorted(processes),
            }
        time.sleep(0.15)


def observe_downloads(target):
    # Shell.Application é lido somente para verificar o caminho da janela já aberta.
    script = r"""
$ErrorActionPreference = 'Stop'
$target = [IO.Path]::GetFullPath($env:MAX_VALIDATION_DOWNLOADS).TrimEnd('\')
$shell = New-Object -ComObject Shell.Application
$matches = @()
foreach ($window in $shell.Windows()) {
    try {
        if ([IO.Path]::GetFileName($window.FullName) -ine 'explorer.exe') { continue }
        $uri = [Uri]$window.LocationURL
        if ($uri.IsFile -and [IO.Path]::GetFullPath($uri.LocalPath).TrimEnd('\') -ieq $target) {
            $matches += [long]$window.HWND
        }
    } catch {}
}
@{ verified = ($matches.Count -gt 0); matching_window_handles = $matches } | ConvertTo-Json -Compress
"""
    env = environment()
    env["MAX_VALIDATION_DOWNLOADS"] = str(target)
    deadline = time.monotonic() + 10
    while True:
        process = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=12,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if process.returncode == 0:
            data = json.loads(process.stdout)
            data["dynamic_target"] = str(target)
            if data["verified"] or time.monotonic() >= deadline:
                return data
        elif time.monotonic() >= deadline:
            return {
                "verified": False,
                "technical_error": "explorer_com_inspection_failed",
                "dynamic_target": str(target),
            }
        time.sleep(0.2)


def observe_system(reply):
    data = reply.get("data", {})
    memory = psutil.virtual_memory()
    drive = (
        os.environ.get("SystemDrive", Path(os.environ["SystemRoot"]).anchor).rstrip("\\/") + "\\"
    )
    disk = shutil.disk_usage(drive)
    kernel = C.WinDLL("kernel32")
    kernel.GetTickCount64.argtypes = []
    kernel.GetTickCount64.restype = C.c_ulonglong
    uptime = kernel.GetTickCount64() / 1000
    checks = {
        "cpu_valid": isinstance(data.get("cpu_percent"), (int, float))
        and 0 <= data["cpu_percent"] <= 100,
        "ram_total_matches": abs(data.get("ram_total_gib", 0) - memory.total / 2**30) < 0.01,
        "ram_used_plausible": 0 <= data.get("ram_used_gib", -1) <= memory.total / 2**30,
        "drive_matches": data.get("drive", "").casefold() == drive.rstrip("\\").casefold(),
        "disk_total_matches": abs(data.get("disk_total_gib", 0) - disk.total / 2**30) < 0.01,
        "disk_free_matches": abs(data.get("disk_free_gib", 0) - disk.free / 2**30) < 1,
        "uptime_matches": abs(data.get("uptime_seconds", -100) - uptime) < 15,
    }
    return {
        "verified": all(checks.values()),
        "checks": checks,
        "independent_uptime_seconds": round(uptime, 1),
        "independent_ram_used_gib": (memory.total - memory.available) / 2**30,
    }


def verify_local(backend, apps, command_id, reply):
    if command_id in {"calculator", "discord", "spotify"}:
        return observe_app(backend, apps[command_id])
    if command_id == "downloads":
        target = backend.known_folder("downloads")
        return observe_downloads(target)
    if command_id in {"volume", "mute", "unmute"}:
        observed = audio_state()  # Nova sessão COM, independente do comando.
        verified = (
            (abs(observed["volume"] - 30) <= 0.5)
            if command_id == "volume"
            else observed["muted"] == (command_id == "mute")
        )
        return {"verified": verified, "independent_endpoint_state": observed}
    if command_id == "system":
        return observe_system(reply)
    return {"verified": False}


def ensure_ollama():
    from urllib.request import urlopen

    try:
        with urlopen("http://127.0.0.1:11434/api/version", timeout=2):
            return {"already_running": True}
    except OSError:
        executable = shutil.which("ollama")
        if not executable:
            return {"available": False, "technical_error": "ollama_not_installed"}
        process = subprocess.Popen(
            [executable, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for _attempt in range(30):
            time.sleep(0.2)
            try:
                with urlopen("http://127.0.0.1:11434/api/version", timeout=1):
                    return {"started_for_validation": True, "pid": process.pid}
            except OSError:
                pass
        return {"available": False, "technical_error": "ollama_server_unreachable"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Autoriza os testes nativos reais já solicitados pelo usuário.",
    )
    parser.add_argument("--only", choices=[row[0] for row in COMMANDS] + ["brains"])
    parser.add_argument("--skip-normal-launch", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Use --execute apenas em um ambiente com autorização para ações reais.")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if os.name != "nt":
        parser.error("Esta validação requer Windows real.")

    previous = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else None
    report = (
        previous
        if args.only and previous
        else {
            "phase": "2.1",
            "started_utc": timestamp(),
            "execution": "real_windows_no_mocks",
            "launch": None,
            "commands": [],
            "brain_checks": {},
            "corrections": [],
            "scope": "existing skills only; no voice, new skills, Spotify API or gaming mode",
        }
    )
    backend, apps = WindowsBackend(), load_apps(ROOT / "apps.json")
    config_hash = hashlib.sha256((ROOT / "config.json").read_bytes()).hexdigest()
    if not args.skip_normal_launch:
        report["launch"] = launch_normal()
        persist(report)
        print(json.dumps({"launch": report["launch"]}, ensure_ascii=False), flush=True)
    before_audio = audio_state()
    report.setdefault("initial_audio_state", before_audio)
    selected = [item for item in COMMANDS if not args.only or item[0] == args.only]
    try:
        for command_id, text, expected_intent, expected_skill in selected:
            try:
                reply = invoke(text)
                observation = verify_local(backend, apps, command_id, reply)
                row = {"command_id": command_id, **reply, "os_observation": observation}
                row["validated_success"] = (
                    reply.get("success", reply.get("ok", False))
                    and reply.get("intent") == expected_intent
                    and reply.get("skill") == expected_skill
                    and reply.get("route") == "local"
                    and reply.get("provider") == "local"
                    and reply.get("llm_used") is False
                    and observation.get("verified") is True
                )
                if not row["validated_success"]:
                    row.setdefault(
                        "technical_error", {"code": reply.get("status", "os_verification_failed")}
                    )
            except Exception as exc:
                row = {
                    "command_id": command_id,
                    "input": text,
                    "validated_success": False,
                    "technical_error": {"type": type(exc).__name__, "message": str(exc)},
                }
            old = [item for item in report["commands"] if item["command_id"] == command_id]
            if old:
                report.setdefault("previous_attempts", []).extend(old)
            report["commands"] = [
                item for item in report["commands"] if item["command_id"] != command_id
            ] + [row]
            persist(report)
            print(json.dumps({"command": row}, ensure_ascii=False), flush=True)
    finally:
        # Restaura o estado anterior usando as mesmas skills, sem atalhar o MAX.
        restoration = []
        for text in (
            f"Max, volume {before_audio['volume']:g}.",
            "Max, mute." if before_audio["muted"] else "Max, unmute.",
        ):
            restoration.append(invoke(text))
        final_audio = audio_state()
        report["audio_restoration"] = {
            "target": before_audio,
            "observed": final_audio,
            "verified": abs(final_audio["volume"] - before_audio["volume"]) <= 0.5
            and final_audio["muted"] == before_audio["muted"],
            "commands": restoration,
        }
        persist(report)

    if not args.only or args.only == "brains":
        report["ollama_runtime"] = ensure_ollama()
        identity = invoke("Qual é o seu nome?")
        identity["validated_success"] = (
            identity.get("text") == "Meu nome é Max." and identity.get("provider") == "codex"
        )
        report["brain_checks"]["codex_identity"] = identity
        print(json.dumps({"codex_identity": identity}, ensure_ascii=False), flush=True)
        data = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        data.update(provider="auto", codex_model="max-validation-intentionally-invalid-model")
        temp = ROOT / "data" / "real-windows-fallback-config.json"
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        try:
            fallback = invoke("Qual é o seu nome?", temp)
        finally:
            temp.unlink(missing_ok=True)
        fallback["induced_failure"] = (
            "unsupported model in temporary validation-only config; no process kill"
        )
        fallback["validated_success"] = (
            fallback.get("text") == "Meu nome é Max."
            and fallback.get("provider") == "ollama"
            and fallback.get("fallback_used") is True
            and any("codex" in notice for notice in fallback.get("notices", []))
        )
        report["brain_checks"]["real_codex_failure_ollama_fallback"] = fallback
        print(json.dumps({"fallback": fallback}, ensure_ascii=False), flush=True)

    report["base_config_unchanged"] = (
        config_hash == hashlib.sha256((ROOT / "config.json").read_bytes()).hexdigest()
    )
    local = report["commands"]
    elapsed = [item["elapsed_seconds"] for item in local if "elapsed_seconds" in item]
    wall = [item["wall_seconds"] for item in local if "wall_seconds" in item]
    report["summary"] = {
        "local_commands": len(local),
        "local_successes": sum(bool(item["validated_success"]) for item in local),
        "local_failures": [item["command_id"] for item in local if not item["validated_success"]],
        "any_local_llm_used": any(item.get("llm_used") is True for item in local),
        "mean_engine_seconds": statistics.mean(elapsed) if elapsed else None,
        "mean_launcher_wall_seconds": statistics.mean(wall) if wall else None,
        "codex_primary_verified": report["brain_checks"]
        .get("codex_identity", {})
        .get("validated_success", False),
        "ollama_fallback_verified": report["brain_checks"]
        .get("real_codex_failure_ollama_fallback", {})
        .get("validated_success", False),
    }
    report["finished_utc"] = timestamp()
    report["real_validation_passed"] = (
        len(local) == 8
        and all(item["validated_success"] for item in local)
        and all(item.get("validated_success") for item in report["brain_checks"].values())
        and len(report["brain_checks"]) == 2
        and report["audio_restoration"]["verified"]
        and report["base_config_unchanged"]
    )
    persist(report)
    print(
        json.dumps(
            {"summary": report["summary"], "passed": report["real_validation_passed"]},
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if report["real_validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
