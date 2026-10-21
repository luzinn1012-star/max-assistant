"""MAX: terminal da fase dois. Inicie com .venv\\Scripts\\python.exe main.py."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from brain.codex_provider import CodexProvider
from brain.ollama_provider import OllamaProvider
from brain.provider import ProviderError
from config import ROOT, ConfigError, load_settings
from core.assistant import Assistant, Reply
from core.logging_setup import setup_logging


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="MAX: assistente pessoal em português do Brasil, fase dois."
    )
    result.add_argument("--ask", metavar="TEXTO", help="Faz uma pergunta e encerra.")
    result.add_argument(
        "--provider",
        choices=("auto", "codex", "ollama"),
        help="auto usa Codex com fallback; os demais isolam um provider.",
    )
    result.add_argument(
        "--health",
        action="store_true",
        help="Verifica CLI, login e modelo local, sem gerar resposta.",
    )
    result.add_argument(
        "--json", action="store_true", help="Saída estruturada para --ask ou --health."
    )
    result.add_argument("--config", type=Path, help="Caminho de configuração JSON.")
    return result


def display(reply: Reply, structured: bool = False) -> None:
    if structured:
        print(json.dumps({"ok": reply.success, **asdict(reply)}, ensure_ascii=False))
        return
    for notice in reply.notices:
        print(f"Aviso: {notice}", file=sys.stderr)
    print(f"Max: {reply.text}")
    fallback = " | fallback" if reply.fallback_used else ""
    print(f"[{reply.provider} | {reply.elapsed_seconds:.2f}s{fallback}]")


def show_status(assistant: Assistant, structured: bool = False) -> bool:
    statuses = assistant.status()
    if structured:
        print(
            json.dumps(
                {
                    "active_provider": assistant.active_provider,
                    "selection": assistant.settings.provider,
                    "providers": [asdict(status) for status in statuses],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"Seleção: {assistant.settings.provider}. Último provider usado: {assistant.active_provider or 'nenhum'}."
        )
        for status in statuses:
            print(
                f"{status.provider}: {'disponível' if status.ok else 'indisponível'}; {status.detail}"
            )
    if assistant.settings.provider == "auto":
        return any(status.ok for status in statuses)
    return any(status.ok and status.provider == assistant.settings.provider for status in statuses)


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 12):  # noqa: UP036 - friendly error before invoking unsupported Python
        print("O MAX requer Python 3.12 ou superior.", file=sys.stderr)
        return 2
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    arg_parser = parser()
    args = arg_parser.parse_args(argv)
    if args.json and args.ask is None and not args.health:
        arg_parser.error("--json requer --ask ou --health.")
    try:
        settings = load_settings(args.config)
        if args.provider:
            settings = replace(settings, provider=args.provider)
        setup_logging(ROOT / "logs")
        assistant = Assistant(
            settings, {"codex": CodexProvider(settings), "ollama": OllamaProvider(settings)}
        )
        if args.health:
            return 0 if show_status(assistant, args.json) else 1
        if args.ask is not None:
            reply = assistant.ask(args.ask)
            display(reply, args.json)
            return 0 if reply.success else 1
        print("MAX | Comandos locais e conversa | Português do Brasil")
        print("Digite ajuda para comandos locais. /status, /limpar, /tentar, /sair.")
        while True:
            try:
                text = input("Você: ").strip()
                if not text:
                    continue
                command = text.casefold()
                if command in {"/sair", "/exit"}:
                    print("Max: Até mais.")
                    return 0
                if command == "/status":
                    show_status(assistant)
                elif command == "/limpar":
                    assistant.reset()
                    print("Max: Limpei o contexto desta conversa.")
                elif command == "/tentar":
                    assistant.retry()
                    print("Max: A próxima mensagem verificará os providers novamente.")
                else:
                    display(assistant.ask(text))
            except (EOFError, KeyboardInterrupt):
                print("\nMax: Até mais.")
                return 0
            except (ProviderError, ValueError) as exc:
                print(f"Max: {exc}", file=sys.stderr)
    except (ConfigError, ProviderError, ValueError) as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": getattr(exc, "code", "configuration_or_input"),
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(f"MAX: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("MAX: Operação cancelada.", file=sys.stderr)
        return 130
    except OSError:
        print(
            "MAX: Não consegui acessar os arquivos locais do projeto. Verifique as permissões.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
