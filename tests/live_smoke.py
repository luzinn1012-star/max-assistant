"""Teste opt-in com providers reais: python -m tests.live_smoke."""

import json
import platform
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime

from brain.codex_provider import CodexProvider
from brain.ollama_provider import OllamaProvider
from config import ROOT, Settings
from core.assistant import Assistant
from core.logging_setup import setup_logging


def build(settings):
    return Assistant(
        settings, {"codex": CodexProvider(settings), "ollama": OllamaProvider(settings)}
    )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    setup_logging(ROOT / "logs")
    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "scope": "phase_1_text_only",
        "checks": [],
    }
    primary = build(Settings())
    report["health"] = [asdict(item) for item in primary.status()]

    def record(name, reply, **expectations):
        check = {"check": name, **asdict(reply), **expectations}
        report["checks"].append(check)
        print(json.dumps(check, ensure_ascii=False), flush=True)
        return reply

    reply = record("identity_auto", primary.ask("Qual é o seu nome?"))
    assert reply.text == "Meu nome é Max.", "Resposta de identidade inesperada."
    assert reply.provider == "codex", "O provider principal não respondeu."

    local = build(Settings(provider="ollama"))
    reply = record("identity_local", local.ask("Qual é o seu nome?"))
    assert reply.text == "Meu nome é Max.", "Resposta local de identidade inesperada."
    assert reply.provider == "ollama"

    # Timeout deliberadamente minúsculo, apenas nesta instância de teste.
    # O Codex real é iniciado e cancelado; o fallback usa o Ollama real.
    fallback = build(replace(Settings(), codex_timeout=0.001))
    reply = record(
        "fallback_after_real_cli_timeout",
        fallback.ask("Qual é o seu nome?"),
        induced_failure="codex_timeout_0.001_seconds",
    )
    assert reply.provider == "ollama" and reply.fallback_used
    assert reply.text == "Meu nome é Max."

    record(
        "context_setup",
        primary.ask("A palavra desta conversa de teste é jacarandá. Responda apenas: Entendido."),
    )
    reply = record(
        "context_recall", primary.ask("Qual foi a palavra de teste? Responda apenas com ela.")
    )
    assert "jacarandá" in reply.text.casefold(), "O contexto da conversa não foi preservado."

    report["passed"] = True
    target = ROOT / "phase1-validation.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Teste integrado aprovado; relatório salvo.", flush=True)


if __name__ == "__main__":
    main()
