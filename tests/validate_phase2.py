"""Validação da fase 2. Controle do Windows nunca é executado por este script."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
from pathlib import Path
import statistics
import sys
import time
import unittest

from brain.codex_provider import CodexProvider
from brain.ollama_provider import OllamaProvider
from brain.provider import ProviderError
from config import ROOT, Settings, load_settings
from core.assistant import Assistant
from skills.bootstrap import build_registry
from tests.phase2_doubles import FakeAudio, FakeWindows, SpyBrain

BASELINE = ("tests.test_assistant", "tests.test_codex", "tests.test_config", "tests.test_ollama")


def run_tests(suite):
    stream = io.StringIO()
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    return {
        "count": result.testsRun, "passed": result.wasSuccessful(),
        "failures": [test.id() for test, detail in result.failures],
        "errors": [test.id() for test, detail in result.errors],
        "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "duration_seconds": time.perf_counter() - started,
    }


def fake_assistant(settings=None):
    settings = settings or Settings()
    backend, audio = FakeWindows(), FakeAudio()
    providers = {"codex": SpyBrain("codex"), "ollama": SpyBrain("ollama")}
    assistant = Assistant(settings, providers, build_registry(settings, backend, lambda: audio))
    return assistant, backend, providers


def measure(assistant, text):
    started = time.perf_counter()
    try:
        reply = assistant.ask(text)
        return {"input": text, "wall_seconds": time.perf_counter() - started, **asdict(reply)}
    except ProviderError as exc:
        return {"input": text, "route": "brain", "success": False,
                "status": exc.code, "provider": exc.provider, "message": str(exc),
                "wall_seconds": time.perf_counter() - started}


def local_validation(samples):
    assistant, backend, providers = fake_assistant()
    checks = []
    for text in ("Max, abra o Spotify.", "Max, abra o Discord.", "Max, abra Downloads.",
                 "Max, volume 30.", "Max, mute.", "Max, tira do mudo.", "Max, como está o PC?", "ajuda"):
        check = measure(assistant, text)
        check["execution"] = "test_double"
        checks.append(check)
    wall = []
    stages = []
    first = None
    for index in range(samples):
        backend.running.discard("calculator")
        check = measure(assistant, "Max, abra a calculadora.")
        if first is None:
            first = check
        wall.append(check["wall_seconds"] * 1000)
        stages.append(check["timings"])
    counts = {name: {"ask": len(provider.ask_calls), "health_check": provider.health_calls}
              for name, provider in providers.items()}
    benchmark = {
        "input": "Max, abra a calculadora.", "route": "local", "provider": "local",
        "execution": "test_double", "windows_launch_verified": False,
        "samples": samples, "median_ms": statistics.median(wall),
        "p95_ms": sorted(wall)[min(len(wall) - 1, int(len(wall) * .95))],
        "first_request_ms": first["wall_seconds"] * 1000,
        "stage_medians_ms": {name: statistics.median(row[name] for row in stages)
                             for name in stages[0]},
        "note": "Mede normalização, router, permissões e skill com backend simulado; não mede o tempo real de abertura do Windows.",
    }
    no_llm = all(row["ask"] == 0 and row["health_check"] == 0 for row in counts.values())
    return checks, benchmark, {"passed": no_llm, "provider_calls": counts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-brains", action="store_true", help="Executa inferência real nos providers, sem API paga.")
    parser.add_argument("--read-only-system", action="store_true", help="Consulta CPU/RAM/disco reais, sem alterar o Windows.")
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=ROOT / "phase2-validation.json")
    args = parser.parse_args(argv)
    if args.samples < 1:
        parser.error("--samples deve ser positivo.")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Mantém testes e benchmark independentes do logging configurado pelo terminal.
    logger = logging.getLogger("max")
    old_handlers, old_level, old_propagate = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = [logging.NullHandler()]
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        loader = unittest.TestLoader()
        phase1 = run_tests(loader.loadTestsFromNames(BASELINE))
        phase2 = run_tests(loader.discover(str(ROOT / "tests"), pattern="test_phase2_*.py", top_level_dir=str(ROOT)))
        passed = phase1["passed"] and phase2["passed"]
        print(json.dumps({"phase1_regressions": phase1, "phase2_unit_tests": phase2}, ensure_ascii=False), flush=True)
        checks, local_benchmark, no_llm = local_validation(args.samples)
        registry = build_registry(Settings(), FakeWindows(), lambda: FakeAudio())
        report = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "phase_2",
            "implementation_status": "integrated" if passed else "unit_failures",
            "unit_tests": {"count": phase1["count"] + phase2["count"], "passed": passed,
                           "phase1_regressions": phase1, "phase2": phase2},
            "phase1_test_files_sha256": {
                name.replace(".", "/") + ".py": hashlib.sha256(
                    (ROOT / (name.replace(".", "/") + ".py")).read_bytes()).hexdigest()
                for name in BASELINE
            },
            "intents": sorted([*registry._intents, "unknown"]),
            "skills": registry.describe(),
            "local_acceptance_test_doubles": checks,
            "local_no_llm_proof": no_llm,
            "benchmark": {"local": local_benchmark},
            "brain_health": None,
            "live_brain_checks": {"executed": False, "passed": None},
            "windows_actions": {
                "executed": False, "acceptance_complete": False,
                "reason": "Controle real de aplicativos, pastas, foco, fechamento e volume reservado a validação fora do sandbox.",
                "pending": ["open_app e foco de janela", "close_app e aviso de conteúdo não salvo",
                            "open_folder", "set_volume", "mute_volume", "unmute_volume"],
            },
        }
        if args.read_only_system and passed:
            providers = {"codex": SpyBrain("codex"), "ollama": SpyBrain("ollama")}
            assistant = Assistant(Settings(), providers)
            check = measure(assistant, "Max, como está o PC?")
            check["execution"] = "real_read_only_windows"
            report["system_status_real"] = check
            print(json.dumps({"system_status_real": check}, ensure_ascii=False), flush=True)
        if args.live_brains and passed:
            settings = load_settings()
            def build(selection):
                configured = replace(settings, provider=selection)
                return Assistant(configured, {"codex": CodexProvider(configured), "ollama": OllamaProvider(configured)})
            primary = build("codex")
            report["brain_health"] = [asdict(item) for item in primary.status()]
            question = "Explique o que é uma API em uma frase."
            codex = measure(primary, question)
            codex["execution"] = "real_provider"
            report["benchmark"]["codex"] = codex
            print(json.dumps({"benchmark_codex": codex}, ensure_ascii=False), flush=True)
            local = build("ollama")
            ollama = measure(local, question)
            ollama["execution"] = "real_provider"
            report["benchmark"]["ollama"] = ollama
            print(json.dumps({"benchmark_ollama": ollama}, ensure_ascii=False), flush=True)
            relativity = measure(primary, "Max, explique relatividade.")
            relativity["execution"] = "real_codex_conversation"
            # Falha sintética do principal; a resposta de fallback é gerada pelo Ollama real.
            fallback_settings = replace(settings, provider="auto")
            fallback_assistant = Assistant(fallback_settings, {
                "codex": SpyBrain("codex", fail=True), "ollama": OllamaProvider(fallback_settings)})
            fallback = measure(fallback_assistant, question)
            fallback["execution"] = "simulated_codex_timeout_real_ollama"
            live_ok = all(item.get("success") for item in (codex, ollama, relativity, fallback))
            live_ok = live_ok and codex.get("provider") == "codex" and ollama.get("provider") == "ollama"
            live_ok = live_ok and relativity.get("provider") == "codex" and fallback.get("fallback_used", False)
            report["live_brain_checks"] = {"executed": True, "passed": live_ok,
                                            "relativity": relativity, "fallback": fallback}
            print(json.dumps({"live_brain_checks": report["live_brain_checks"]}, ensure_ascii=False), flush=True)
        report["software_checks_passed"] = passed and no_llm["passed"] and all(item["success"] for item in checks)
        report["fully_validated_on_windows"] = False
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"report": str(args.output), "unit_tests": report["unit_tests"]["count"],
                          "software_checks_passed": report["software_checks_passed"],
                          "windows_actions_pending": True}, ensure_ascii=False), flush=True)
        return 0 if report["software_checks_passed"] else 1
    finally:
        logger.handlers = old_handlers
        logger.setLevel(old_level)
        logger.propagate = old_propagate


if __name__ == "__main__":
    raise SystemExit(main())
