"""Configuração simples do MAX; nenhuma credencial é necessária."""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    provider: str = "auto"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    codex_model: str = ""
    codex_timeout: float = 30.0
    ollama_timeout: float = 90.0
    health_timeout: float = 5.0
    retry_cooldown: float = 60.0
    history_turns: int = 6
    context_chars: int = 12000
    max_input_chars: int = 6000
    ollama_context_tokens: int = 4096
    ollama_max_tokens: int = 768
    ollama_keep_alive: str = "10m"
    router_threshold: float = 0.80
    volume_step: int = 10
    confirmation_timeout: float = 30.0
    launch_verify_timeout: float = 2.0

    def __post_init__(self) -> None:
        if (type(self.router_threshold) not in (int, float) or not math.isfinite(self.router_threshold)
                or not 0 < self.router_threshold <= 1):
            raise ConfigError("router_threshold deve estar entre zero (exclusivo) e um.")
        if type(self.volume_step) is not int or not 1 <= self.volume_step <= 100:
            raise ConfigError("volume_step deve ser um inteiro entre 1 e 100.")
        if not isinstance(self.provider, str) or self.provider not in {"auto", "codex", "ollama"}:
            raise ConfigError("Provider deve ser auto, codex ou ollama.")
        for name in ("ollama_url", "ollama_model", "codex_model", "ollama_keep_alive"):
            if not isinstance(getattr(self, name), str):
                raise ConfigError(f"{name} deve ser texto.")
        if not self.ollama_model.strip():
            raise ConfigError("Informe o modelo local.")
        try:
            url = urlsplit(self.ollama_url)
            port = url.port
        except ValueError as exc:
            raise ConfigError("Endereço do Ollama inválido.") from exc
        if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
                or url.username or url.password or url.query or url.fragment
                or url.path not in {"", "/"} or port == 0):
            raise ConfigError("O Ollama deve usar HTTP local, sem credenciais ou caminho.")
        for name in ("codex_timeout", "ollama_timeout", "health_timeout", "retry_cooldown", "confirmation_timeout", "launch_verify_timeout"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ConfigError(f"{name} deve ser um número positivo e finito.")
        for name in ("history_turns", "context_chars", "max_input_chars",
                     "ollama_context_tokens", "ollama_max_tokens"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ConfigError(f"{name} deve ser um inteiro positivo.")
        if self.max_input_chars > self.context_chars:
            raise ConfigError("max_input_chars não pode ultrapassar context_chars.")


def load_settings(path: Path | None = None) -> Settings:
    if path is not None and not path.is_file():
        raise ConfigError("O arquivo de configuração informado não existe.")
    path = path or ROOT / "config.json"
    values = {}
    if path.exists():
        try:
            values = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise ConfigError("Não foi possível ler o JSON de configuração.") from exc
        if not isinstance(values, dict):
            raise ConfigError("A configuração deve ser um objeto JSON.")
        unknown = values.keys() - {field.name for field in fields(Settings)}
        if unknown:
            raise ConfigError("Há campos desconhecidos na configuração.")
    # .env não é carregado. Somente estas variáveis opcionais são reconhecidas.
    for key, name in {"MAX_PROVIDER": "provider", "MAX_OLLAMA_URL": "ollama_url",
                      "MAX_OLLAMA_MODEL": "ollama_model", "MAX_CODEX_MODEL": "codex_model"}.items():
        if key in os.environ:
            values[name] = os.environ[key]
    return Settings(**values)
