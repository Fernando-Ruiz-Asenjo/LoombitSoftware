"""
LLM client con soporte de roles y function calling (tool use).
Compatible con cualquier endpoint OpenAI-like: LM Studio, Ollama, llama.cpp...
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import time

import httpx

from .config import AppSettings, get_settings

# ── ALG-0.2 · reintento ante errores TRANSITORIOS del LLM ─────────────────────
# Un hipo de red / saturación (timeout, conexión, 429, 5xx) NO debe tumbar el run. Un 400
# (contexto/esquema) es DETERMINISTA → no se reintenta (lo arregla ALG-0.1). Ver
# docs/ALGORITMO_CEREBRO.md (ALG-0.2). El backoff base lo baja a 0 el test.
_REINTENTABLES = frozenset({429, 500, 502, 503, 504})
_MAX_INTENTOS = 3
_BACKOFF_BASE = 0.5  # segundos


def _post_con_reintento(client: Any, url: str, payload: dict[str, Any]) -> Any:
    """POST con reintento+backoff SOLO ante fallos transitorios. Devuelve la respuesta (ok,
    no reintentable, o la del último intento). Relanza la excepción de red si se agota."""
    for intento in range(1, _MAX_INTENTOS + 1):
        try:
            resp = client.post(url, json=payload)
        except (httpx.TimeoutException, httpx.TransportError):
            if intento >= _MAX_INTENTOS:
                raise
            time.sleep(_BACKOFF_BASE * 2 ** (intento - 1))
            continue
        if resp.status_code in _REINTENTABLES and intento < _MAX_INTENTOS:
            time.sleep(_BACKOFF_BASE * 2 ** (intento - 1))
            continue
        return resp
    raise RuntimeError("inalcanzable")  # pragma: no cover


@dataclass
class ToolCall:
    id: str
    tool_name: str
    arguments: dict[str, Any]

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "ToolCall":
        fn = raw.get("function", {})
        raw_args = fn.get("arguments", "{}")
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            args = {"_raw": raw_args}
        return cls(
            id=str(raw.get("id", "")),
            tool_name=str(fn.get("name", "")),
            arguments=args if isinstance(args, dict) else {"_raw": args},
        )


@dataclass
class ChatResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @classmethod
    def from_api(cls, response: dict[str, Any]) -> "ChatResponse":
        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})
        finish_reason = str(choice.get("finish_reason", "stop"))
        content = str(msg.get("content") or "")
        raw_calls = msg.get("tool_calls") or []
        tool_calls = [ToolCall.from_api(tc) for tc in raw_calls if isinstance(tc, dict)]
        return cls(
            content=content, tool_calls=tool_calls, finish_reason=finish_reason, raw=response
        )

    def to_message(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.tool_name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in self.tool_calls
            ]
        return msg


class LLMClient:
    def __init__(
        self,
        settings: AppSettings | None = None,
        client: httpx.Client | None = None,
        role: str = "default",
    ) -> None:
        self.settings = settings or get_settings()
        self.role = role
        if client is not None:
            self.client = client
        else:
            self.client = httpx.Client(timeout=self.settings.llm_request_timeout_seconds)

    @property
    def provider(self) -> str:
        return self._role_str("provider", self.settings.llm_provider)

    @property
    def base_url(self) -> str:
        return self._role_str("base_url", self.settings.llm_base_url)

    @property
    def model_name(self) -> str:
        return self._role_str("model_name", self.settings.llm_model_name)

    def config_snapshot(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model_name,
        }

    def health(self) -> dict[str, Any]:
        snapshot = self.config_snapshot()
        if self.provider == "disabled":
            return {"status": "disabled", "error": None, **snapshot}
        try:
            response = self.client.get(self._url("/models"))
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"status": "unreachable", "error": str(exc), **snapshot}
        return {"status": "ok", "error": None, "models": data.get("data", data), **snapshot}

    def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> ChatResponse:
        if self.provider == "disabled":
            raise RuntimeError("LLM provider is disabled")
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": (
                temperature if temperature is not None else self.settings.llm_temperature
            ),
            "max_tokens": max_tokens if max_tokens is not None else self.settings.llm_max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        response = _post_con_reintento(self.client, self._url("/chat/completions"), payload)
        response.raise_for_status()
        return ChatResponse.from_api(response.json())

    def chat_raw(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens).raw

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Vectoriza textos con el modelo de embeddings local (RAG). Mismo endpoint OpenAI-like.
        Devuelve un vector por texto, en el mismo orden."""
        if self.provider == "disabled":
            raise RuntimeError("LLM provider is disabled")
        payload = {"model": model or self.settings.llm_embeddings_model_name, "input": texts}
        response = self.client.post(self._url("/embeddings"), json=payload)
        response.raise_for_status()
        data = response.json().get("data", [])
        return [list(item.get("embedding", [])) for item in data]

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _role_str(self, key: str, fallback: str) -> str:
        if self.role == "default":
            return str(fallback).strip()
        value = getattr(self.settings, f"llm_{self.role}_{key}", "")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return str(fallback).strip()


def tool_result_message(tool_call_id: str, content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}
