"""LLM port + Gemini adapter (google-genai).

The ``LLMClient`` protocol is the only seam the agent nodes see; tests inject a
fake implementing it. ``GeminiLLM`` is the single place ``google-genai`` is
imported for generation. Every call records token usage into the request's
:class:`BudgetLedger` so cost/limits stay attributable.
"""

import time
from collections.abc import Iterator
from typing import Protocol, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app import observability
from app.agent import budget
from app.agent.errors import NodeOutputError
from app.agent.state import BudgetLedger
from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

# Node model_role → concrete model name (resolved via config).
Role = str  # "control" | "synth"


def _model_for(role: Role) -> str:
    return settings.model_synth if role == "synth" else settings.model_control


class LLMClient(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        ledger: BudgetLedger,
        system: str | None = None,
        role: Role = "control",
        temperature: float = 0.0,
        prompt_id: str = "",
    ) -> str: ...

    def generate_stream(
        self,
        prompt: str,
        *,
        ledger: BudgetLedger,
        system: str | None = None,
        role: Role = "synth",
        temperature: float = 0.3,
        prompt_id: str = "",
    ) -> Iterator[str]: ...

    def generate_json(
        self,
        prompt: str,
        schema: type[T],
        *,
        ledger: BudgetLedger,
        system: str | None = None,
        role: Role = "control",
        temperature: float = 0.0,
        prompt_id: str = "",
    ) -> T: ...


class GeminiLLM:
    """google-genai adapter implementing :class:`LLMClient`."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini.")
        self._client = genai.Client(api_key=api_key)

    @staticmethod
    def _record(
        ledger: BudgetLedger,
        response: object,
        *,
        role: Role,
        prompt_id: str,
        temperature: float,
        latency_ms: int,
    ) -> None:
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        budget.record_llm(ledger, prompt_tokens, output_tokens)
        observability.record_generation(
            model=_model_for(role),
            prompt_id=prompt_id,
            input_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            temperature=temperature,
        )

    def generate(
        self,
        prompt: str,
        *,
        ledger: BudgetLedger,
        system: str | None = None,
        role: Role = "control",
        temperature: float = 0.0,
        prompt_id: str = "",
    ) -> str:
        started = time.monotonic()
        response = self._client.models.generate_content(
            model=_model_for(role),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system, temperature=temperature, max_output_tokens=1200
            ),
        )
        self._record(
            ledger,
            response,
            role=role,
            prompt_id=prompt_id,
            temperature=temperature,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return getattr(response, "text", "") or ""

    def generate_stream(
        self,
        prompt: str,
        *,
        ledger: BudgetLedger,
        system: str | None = None,
        role: Role = "synth",
        temperature: float = 0.3,
        prompt_id: str = "",
    ) -> Iterator[str]:
        started = time.monotonic()
        stream = self._client.models.generate_content_stream(
            model=_model_for(role),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system, temperature=temperature, max_output_tokens=1600
            ),
        )
        last = None
        for chunk in stream:
            last = chunk
            text = getattr(chunk, "text", "") or ""
            if text:
                yield text
        # Token usage on streams is only reliable on the final chunk.
        if last is not None:
            self._record(
                ledger,
                last,
                role=role,
                prompt_id=prompt_id,
                temperature=temperature,
                latency_ms=int((time.monotonic() - started) * 1000),
            )

    def generate_json(
        self,
        prompt: str,
        schema: type[T],
        *,
        ledger: BudgetLedger,
        system: str | None = None,
        role: Role = "control",
        temperature: float = 0.0,
        prompt_id: str = "",
    ) -> T:
        def _call(extra: str) -> T:
            started = time.monotonic()
            response = self._client.models.generate_content(
                model=_model_for(role),
                contents=prompt + extra,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                    max_output_tokens=1600,
                ),
            )
            self._record(
                ledger,
                response,
                role=role,
                prompt_id=prompt_id,
                temperature=temperature,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, schema):
                return parsed
            return schema.model_validate_json(getattr(response, "text", "") or "")

        try:
            return _call("")
        except Exception:
            # One retry with an explicit instruction before giving up.
            try:
                return _call("\n\nReturn ONLY valid JSON matching the schema.")
            except Exception as exc:  # noqa: BLE001 — surfaced as a control-data error
                raise NodeOutputError(f"{prompt_id or 'llm'}: invalid JSON output") from exc
