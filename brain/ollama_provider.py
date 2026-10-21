"""API HTTP oficial do Ollama; sem SDK e sem envio a servidores externos."""

from __future__ import annotations

import json
import socket
from collections.abc import Sequence
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from brain.prompts import SYSTEM_PROMPT
from brain.provider import Answer, BrainProvider, Health, Message, ProviderError
from config import Settings


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaProvider(BrainProvider):
    name = "ollama"

    def __init__(self, settings: Settings):
        self.settings = settings
        # Proxies do sistema não devem receber conversas destinadas ao localhost.
        self.http = build_opener(ProxyHandler({}), NoRedirect())

    def _request(self, endpoint: str, payload: dict | None = None, *, timeout: float) -> dict:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.settings.ollama_url.rstrip("/") + endpoint,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with self.http.open(request, timeout=timeout) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ProviderError(
                    self.name, "response_too_large", "O Ollama enviou uma resposta grande demais."
                )
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("expected object")
            if data.get("error"):
                raise ProviderError(
                    self.name, "server_error", "O Ollama informou um erro ao processar o pedido."
                )
            return data
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise ProviderError(
                self.name, f"http_{status}", f"O Ollama respondeu com erro HTTP {status}."
            ) from None
        except TimeoutError:
            raise ProviderError(
                self.name, "timeout", "O Ollama excedeu o tempo de resposta."
            ) from None
        except URLError as exc:
            code = (
                "timeout"
                if isinstance(exc.reason, (TimeoutError, socket.timeout))
                else "unreachable"
            )
            raise ProviderError(
                self.name, code, "Não consegui conectar ao Ollama local. Inicie ollama serve."
            ) from None
        except (ValueError, UnicodeError):
            raise ProviderError(
                self.name, "invalid_response", "O Ollama enviou uma resposta inválida."
            ) from None
        except (OSError, HTTPException):
            raise ProviderError(
                self.name, "connection_error", "A conexão com o Ollama foi interrompida."
            ) from None

    def health_check(self) -> Health:
        try:
            data = self._request("/api/tags", timeout=self.settings.health_timeout)
            models = data.get("models", [])
            if not isinstance(models, list):
                raise ProviderError(self.name, "invalid_response", "Lista de modelos inválida.")
            names = {
                entry.get("name")
                for entry in models
                if isinstance(entry, dict) and isinstance(entry.get("name"), str)
            }
            target = self.settings.ollama_model
            if target in names or (":" not in target and target + ":latest" in names):
                return Health(
                    self.name, True, f"Servidor local disponível; modelo {target} instalado."
                )
            return Health(
                self.name,
                False,
                f"Modelo {target} ausente. Instale-o com ollama pull {target}.",
                "model_missing",
            )
        except ProviderError as exc:
            return Health(self.name, False, str(exc), exc.code)

    def ask(self, messages: Sequence[Message]) -> Answer:
        prepared = [{"role": message.role, "content": message.content} for message in messages]
        if self.settings.ollama_model.split(":")[0].lower() == "qwen3" and prepared:
            prepared[-1]["content"] += "\n/no_think"
        payload = {
            "model": self.settings.ollama_model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + prepared,
            "stream": False,
            "think": False,
            "keep_alive": self.settings.ollama_keep_alive,
            "options": {
                "temperature": 0.2,
                "num_ctx": self.settings.ollama_context_tokens,
                "num_predict": self.settings.ollama_max_tokens,
            },
        }
        data = self._request("/api/chat", payload, timeout=self.settings.ollama_timeout)
        message = data.get("message")
        if not isinstance(message, dict):
            raise ProviderError(
                self.name, "invalid_response", "O Ollama não retornou uma mensagem válida."
            )
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError(
                self.name, "empty_response", "O Ollama retornou uma resposta vazia."
            )
        if message.get("tool_calls"):
            raise ProviderError(
                self.name,
                "unexpected_tool",
                "O modelo tentou usar uma ferramenta indisponível nesta fase.",
            )
        if data.get("done") is not True:
            raise ProviderError(
                self.name, "incomplete_response", "O Ollama não concluiu a resposta."
            )
        if data.get("done_reason") == "length":
            raise ProviderError(
                self.name,
                "output_limit",
                "A resposta atingiu o limite local. Divida a pergunta ou aumente ollama_max_tokens.",
            )
        # Alguns templates locais começam com <think> mesmo com think=false.
        # Nunca exiba o canal interno, inclusive quando só vem a tag de fechamento.
        if "</think>" in text:
            text = text.rsplit("</think>", 1)[1].strip()
        if "<think>" in text or not text.strip():
            raise ProviderError(
                self.name,
                "missing_final_answer",
                "O modelo local não retornou uma resposta final utilizável.",
            )
        model = data.get("model")
        return Answer(
            text.strip(), self.name, model if isinstance(model, str) else self.settings.ollama_model
        )
