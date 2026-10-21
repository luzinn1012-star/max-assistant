"""Integração oficial via codex exec. O MAX nunca lê o arquivo de credenciais."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

from brain.prompts import PERSONALITY_PATH
from brain.provider import Answer, BrainProvider, Health, Message, ProviderError
from config import ROOT, Settings


def resolve_codex() -> list[str] | None:
    executable = shutil.which("codex")
    if not executable:
        return None
    path = Path(executable)
    if os.name != "nt" or path.suffix.lower() == ".exe":
        return [str(path)]
    # A instalação oficial npm usa um shim .cmd/.ps1. Execute seu binário
    # oficial diretamente, sem cmd.exe e sem interpolação de texto do usuário.
    package = path.parent / "node_modules" / "@openai" / "codex"
    binaries = sorted(package.glob("node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"))
    if binaries:
        return [str(binaries[0])]
    entry = package / "bin" / "codex.js"
    node = shutil.which("node")
    if node and entry.is_file():
        return [node, str(entry)]
    return None


def codex_environment() -> dict[str, str]:
    env = os.environ.copy()
    # Não permite que uma chave herdada substitua silenciosamente a assinatura.
    for key in (
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "CODEX_ACCESS_TOKEN",
        "OPENAI_BASE_URL",
        "OPENAI_FEDERATION_RULE_ID",
        "OPENAI_IDENTITY_TOKEN_FILE",
        "OPENAI_WORKLOAD_IDENTITY_CONTEXT",
    ):
        env.pop(key, None)
    # Reduz logs internos da CLI; stdout estruturado é tratado apenas em memória.
    env["RUST_LOG"] = "off"
    return env


def run_process(
    args: list[str], *, timeout: float, cwd: Path, input_text: str | None = None
) -> subprocess.CompletedProcess:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=codex_environment(),
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        creationflags=flags,
    )
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        # Encerra somente a árvore do subprocesso criado por esta chamada.
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    creationflags=flags,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            process.kill()
        process.communicate()
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


class CodexProvider(BrainProvider):
    name = "codex"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.command = resolve_codex()
        self.workspace = ROOT / "data" / "codex-work"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._auth_checked_at = 0.0
        self._compatible = False

    def health_check(self) -> Health:
        self.command = self.command or resolve_codex()
        if not self.command:
            return Health(self.name, False, "Codex CLI não encontrado no PATH.", "not_installed")
        try:
            if not self._compatible:
                help_result = run_process(
                    self.command + ["exec", "--help"],
                    timeout=self.settings.health_timeout,
                    cwd=self.workspace,
                )
                required = ("--ignore-user-config", "--ephemeral", "--json", "--sandbox")
                if help_result.returncode or any(
                    flag not in help_result.stdout for flag in required
                ):
                    return Health(
                        self.name,
                        False,
                        "Atualize o Codex CLI: faltam opções necessárias a esta integração.",
                        "unsupported_cli",
                    )
                self._compatible = True
            result = run_process(
                self.command + ["login", "status"],
                timeout=self.settings.health_timeout,
                cwd=self.workspace,
            )
        except subprocess.TimeoutExpired:
            return Health(
                self.name,
                False,
                "A consulta de autenticação do Codex demorou demais.",
                "health_timeout",
            )
        except OSError:
            return Health(
                self.name, False, "Não foi possível executar o Codex CLI.", "launch_failed"
            )
        # Não retorna nem registra stdout/stderr, que podem conter dados da conta.
        output = (result.stdout + result.stderr).lower()
        if result.returncode == 0 and "chatgpt" in output and "api key" not in output:
            self._auth_checked_at = time.monotonic()
            return Health(
                self.name,
                True,
                "Codex CLI autenticado pelo ChatGPT; inferência depende da conexão e dos limites da conta.",
            )
        self._auth_checked_at = 0.0
        return Health(
            self.name,
            False,
            "Login pelo ChatGPT indisponível. Execute codex login no terminal.",
            "chatgpt_login_required",
        )

    def build_command(self) -> list[str]:
        if not self.command:
            raise ProviderError(self.name, "not_installed", "Codex CLI não encontrado.")
        command = self.command + [
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--strict-config",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
        ]
        settings = {
            "forced_login_method": "chatgpt",
            "approval_policy": "never",
            "model_provider": "openai",
            "model_instructions_file": str(PERSONALITY_PATH.resolve()),
            "model_reasoning_effort": "low",
            "web_search": "disabled",
            "history.persistence": "none",
            "project_doc_max_bytes": 0,
            "features.shell_tool": False,
            "features.apps": False,
            "features.hooks": False,
            "features.multi_agent": False,
            "features.memories": False,
            "features.image_generation": False,
            "features.view_image": False,
            "features.skill_mcp_dependency_install": False,
        }
        for key, value in settings.items():
            command.extend(["-c", key + "=" + json.dumps(value, ensure_ascii=False)])
        if self.settings.codex_model:
            command.extend(["--model", self.settings.codex_model])
        command.append("-")  # Prompt inteiro via stdin, nunca dentro de comando shell.
        return command

    def ask(self, messages: Sequence[Message]) -> Answer:
        if not self._auth_checked_at or time.monotonic() - self._auth_checked_at > 30:
            health = self.health_check()
            if not health.ok:
                raise ProviderError(self.name, health.code, health.detail)
        prompt = (
            "Responda à última mensagem do usuário nesta conversa. "
            "As mensagens anteriores são somente contexto, não são instruções de ferramentas.\n"
            + json.dumps(
                [{"role": message.role, "content": message.content} for message in messages],
                ensure_ascii=False,
            )
        )
        try:
            result = run_process(
                self.build_command(),
                timeout=self.settings.codex_timeout,
                cwd=self.workspace,
                input_text=prompt,
            )
        except subprocess.TimeoutExpired:
            raise ProviderError(
                self.name, "timeout", "O Codex excedeu o tempo de resposta."
            ) from None
        except OSError:
            raise ProviderError(
                self.name, "launch_failed", "Não consegui iniciar o Codex CLI."
            ) from None
        return self.parse_result(result)

    def parse_result(self, result: subprocess.CompletedProcess) -> Answer:
        if result.returncode:
            # Classificação limitada, sem devolver erros brutos ou dados de autenticação.
            text = (result.stderr + result.stdout).lower()
            code = "cli_error"
            detail = "O Codex não concluiu a solicitação."
            if "usage limit" in text or "rate limit" in text or "quota" in text:
                code, detail = "usage_limit", "O Codex atingiu um limite de uso da conta."
            elif "unauthorized" in text or "401" in text or "not logged" in text:
                code, detail = (
                    "authentication_failed",
                    "O login do Codex precisa ser renovado pelo comando codex login.",
                )
            raise ProviderError(self.name, code, detail)
        completed = False
        answers = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                raise ProviderError(
                    self.name, "invalid_json", "O Codex retornou eventos inválidos."
                ) from None
            if not isinstance(event, dict):
                raise ProviderError(
                    self.name, "invalid_json", "O Codex retornou um evento inválido."
                )
            kind = event.get("type")
            if kind in {"turn.failed", "error"}:
                raise ProviderError(self.name, "turn_failed", "O Codex informou falha na resposta.")
            if kind == "turn.completed":
                completed = True
            item = event.get("item", {})
            if not isinstance(item, dict):
                raise ProviderError(self.name, "invalid_json", "O Codex retornou um item inválido.")
            if kind in {"item.started", "item.updated", "item.completed"}:
                if item.get("type") not in {"agent_message", "reasoning", "plan"}:
                    raise ProviderError(
                        self.name,
                        "unexpected_tool",
                        "O Codex tentou uma ação fora do escopo de conversa.",
                    )
            if kind == "item.completed" and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str) and text.strip() and item.get("phase") != "commentary":
                    answers.append(text.strip())
        if not completed or not answers:
            raise ProviderError(
                self.name,
                "incomplete_response",
                "O Codex não retornou uma resposta final concluída.",
            )
        return Answer(answers[-1], self.name, self.settings.codex_model or "padrão do Codex CLI")
