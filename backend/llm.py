from __future__ import annotations

import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLMError(RuntimeError):
    """Raised when model calls fail."""


class LLMUnavailableError(LLMError):
    """Raised when model access is not configured."""


def _build_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


client = _build_client()


def is_llm_configured() -> bool:
    return client is not None


def call_llm(
    messages: list[dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    response_format: dict[str, Any] | None = None,
) -> str:
    """Call the OpenAI API and return response content."""
    if client is None:
        raise LLMUnavailableError("OPENAI_API_KEY is not configured")

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if content is None:
        raise LLMError("Model returned empty content")
    return content


def call_llm_json(
    messages: list[dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    max_attempts: int = 2,
) -> dict[str, Any]:
    """Call the model and parse a JSON object response with light retries."""
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            content = call_llm(
                messages,
                model=model,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return json.loads(content)
        except (json.JSONDecodeError, LLMError, LLMUnavailableError, Exception) as exc:  # noqa: BLE001
            last_error = exc
            if attempt < max_attempts:
                time.sleep(0.4 * attempt)
                continue

    raise LLMError(f"Failed to produce JSON response: {last_error}")
