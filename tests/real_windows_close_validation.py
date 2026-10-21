"""Exercita a confirmação real do MAX apenas em uma Calculadora de teste."""

import json
import queue
import subprocess
import threading
import time

from automation.windows import WindowsBackend
from config import ROOT
from skills.apps import load_apps
from tests.real_windows_validation import (
    REPORT,
    environment,
    launcher_command,
    observe_app,
    persist,
)


def main():
    backend = WindowsBackend()
    spec = load_apps(ROOT / "apps.json")["calculator"]
    events = queue.Queue()
    process = subprocess.Popen(
        launcher_command(),
        cwd=ROOT,
        env=environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
        shell=False,
    )

    def reader():
        while True:
            char = process.stdout.read(1)
            if not char:
                events.put(None)
                return
            events.put(char)

    threading.Thread(target=reader, daemon=True).start()

    def prompt():
        end = time.monotonic() + 25
        text = ""
        while time.monotonic() < end:
            try:
                char = events.get(timeout=0.2)
            except queue.Empty:
                if process.poll() is not None:
                    raise RuntimeError("MAX encerrou antes da confirmação.") from None
                continue
            if char is None:
                raise RuntimeError("Saída do MAX foi encerrada.")
            text += char
            if text.endswith("Você: "):
                return text
        raise TimeoutError("O terminal não retornou ao prompt.")

    def send(text):
        process.stdin.write(text + "\n")
        process.stdin.flush()
        return prompt()

    result = {
        "execution": "real_windows_interactive_launcher",
        "app": "calculator",
        "confirmation_source": "explicit automated test input authorized by validation task",
        "force_kill_used": False,
        "transcript": [],
    }
    try:
        result["startup"] = prompt()
        result["transcript"].append(
            {"input": "Max, abra a Calculadora.", "output": send("Max, abra a Calculadora.")}
        )
        observed = observe_app(backend, spec)
        if not observed["verified"]:
            raise RuntimeError("Calculadora de teste sem janela visível.")
        before = backend.windows(spec)
        log = ROOT / "logs" / "max.log"
        offset = log.stat().st_size
        question = send("Max, feche a Calculadora.")
        result["transcript"].append({"input": "Max, feche a Calculadora.", "output": question})
        result["confirmation_prompt_observed"] = "Quer que eu feche Calculadora?" in question
        visible_before_confirm = [window for window in backend.windows(spec) if window["visible"]]
        result["still_open_before_confirmation"] = bool(visible_before_confirm)
        if not result["confirmation_prompt_observed"] or not visible_before_confirm:
            raise RuntimeError("O fluxo real não preservou a confirmação de fechamento.")
        response = send("sim")
        result["transcript"].append({"input": "sim", "output": response})
        deadline = time.monotonic() + 10
        original = {window["hwnd"] for window in before if window["visible"]}
        while time.monotonic() < deadline:
            if not any(
                window["visible"] and window["hwnd"] in original for window in backend.windows(spec)
            ):
                break
            time.sleep(0.1)
        after = backend.windows(spec)
        result["normal_close_verified"] = not any(
            window["visible"] and window["hwnd"] in original for window in after
        )
        records = []
        for line in log.read_bytes()[offset:].decode("utf-8", errors="replace").splitlines():
            if "event=dispatch " in line:
                record = json.loads(line.split("event=dispatch ", 1)[1])
                if (
                    record.get("intent") == "close_app"
                    and record.get("parameters", {}).get("app") == "calculator"
                ):
                    records.append(record)
        result["dispatch_records"] = records
        result["llm_used"] = any(row.get("llm_used") for row in records)
        result["passed"] = (
            result["normal_close_verified"]
            and not result["llm_used"]
            and any(row["status"] == "confirmation_required" for row in records)
            and any(row["status"] == "close_requested" for row in records)
        )
    except Exception as exc:
        result["passed"] = False
        result["technical_error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if process.poll() is None:
            process.stdin.write("/sair\n")
            process.stdin.flush()
            process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                result["terminal_shutdown_pending"] = True
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        report["close_confirmation_real"] = result
        persist(report)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
