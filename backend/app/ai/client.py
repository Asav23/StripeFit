"""OpenRouter wrapper. The only place in the app that talks to an AI provider.

call_json() guarantees one of two outcomes: a validated Pydantic object, or an AIError
that routers turn into a friendly message. It never returns unvalidated model output.
"""

import base64
import io
import json
import logging
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from PIL import Image, ImageOps
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.ai import mocks
from app.config import settings
from app.db import engine
from app.models import AICall

log = logging.getLogger("stripefit.ai")
T = TypeVar("T", bound=BaseModel)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
TRANSIENT_ERRORS = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)
BACKOFF_SECONDS = 1.5
MAX_IMAGE_PX = 1024


class AIError(Exception):
    """An AI task failed. `kind` is one of: not_configured, unavailable, invalid_output."""

    def __init__(self, task: str, kind: str, detail: str = "") -> None:
        super().__init__(f"{task}: {kind} {detail}".strip())
        self.task = task
        self.kind = kind
        self.detail = detail

    @property
    def user_message(self) -> str:
        if self.kind == "not_configured":
            return "AI isn't set up yet (no OpenRouter key). Turn on mock mode or add a key."
        if self.kind == "invalid_output":
            return "The AI gave an answer we couldn't trust, so we didn't use it."
        return "The AI service is busy or unreachable right now."


# --------------------------------------------------------------------------- helpers


def image_part(source: Path | bytes) -> dict[str, Any]:
    """Resize to max 1024px and return an OpenAI-style image_url content part."""
    img = Image.open(source if isinstance(source, Path) else io.BytesIO(source))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}


def extract_json(text: str | None) -> Any:
    """Parse the first JSON object in a model reply (tolerates code fences and chatter)."""
    if not text:
        raise ValueError("empty reply")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned[cleaned.find("\n") + 1 :] if "\n" in cleaned else cleaned
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        if start == -1:
            raise ValueError("no JSON object found in reply")
        obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
        return obj


def _short_errors(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:8])
    return str(exc)[:300]


def _log_call(task: str, model: str, started: float, *, success: bool, error: str | None = None,
              prompt_tokens: int | None = None, completion_tokens: int | None = None,
              cost: float | None = None) -> int:
    row = AICall(
        task=task,
        model=model,
        latency_ms=int((time.perf_counter() - started) * 1000),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost=cost,
        success=success,
        error=error,
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id  # type: ignore[return-value]


def _mark_invalid(call_id: int, error: str) -> None:
    with Session(engine) as session:
        row = session.get(AICall, call_id)
        if row:
            row.success = False
            row.error = f"invalid output: {error}"[:500]
            session.add(row)
            session.commit()


@lru_cache
def _client() -> OpenAI:
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        timeout=settings.AI_TIMEOUT_SECONDS,
        max_retries=0,  # we do our own single retry so every attempt is logged
        default_headers={"HTTP-Referer": "http://localhost", "X-Title": settings.OPENROUTER_APP_NAME},
    )


# --------------------------------------------------------------------------- main entry point


def call_json(
    task: str,
    model: str,
    fallbacks: list[str],
    messages: list[dict[str, Any]],
    schema: type[T],
    *,
    mock_input: Any = None,
    max_tokens: int = 1200,
    temperature: float = 0.2,
) -> T:
    """Run an AI task and return validated output, or raise AIError.

    mock_input: structured context used only by mock mode (e.g. the outfit candidates),
    so mocks can return realistic, valid-looking output with zero network calls.
    """
    if settings.USE_MOCK_AI:
        return _mock_call(task, schema, mock_input)
    if not settings.OPENROUTER_API_KEY:
        raise AIError(task, "not_configured")
    if not model:
        raise AIError(task, "not_configured", "no model configured for this task")

    conversation = list(messages)
    last_error = ""
    for _ in range(2):  # first try + one retry with the validation errors appended
        raw, call_id = _request(task, model, fallbacks, conversation, max_tokens, temperature)
        try:
            return schema.model_validate(extract_json(raw))
        except (ValueError, ValidationError) as exc:
            last_error = _short_errors(exc)
            _mark_invalid(call_id, last_error)
            log.warning("AI %s returned invalid output: %s", task, last_error)
            conversation = conversation + [
                {"role": "assistant", "content": raw or ""},
                {
                    "role": "user",
                    "content": f"Your reply was not valid: {last_error}. "
                    "Reply again with ONLY the corrected JSON object, no other text.",
                },
            ]
    raise AIError(task, "invalid_output", last_error)


REASONING_HEADROOM_TOKENS = 3000  # extra room when a model is allowed to think before answering


def _reasoning() -> dict[str, Any]:
    """OpenRouter's unified reasoning switch (ignored by models that don't reason). See config.AI_REASONING."""
    mode = settings.AI_REASONING.strip().lower()
    if mode == "off":
        return {"reasoning": {"enabled": False}}
    if mode in ("minimal", "low", "medium", "high"):
        return {"reasoning": {"effort": mode}}
    return {}


def _request(task: str, model: str, fallbacks: list[str], conversation: list[dict[str, Any]],
             max_tokens: int, temperature: float) -> tuple[str | None, int]:
    """One HTTP call with a single short backoff retry on 429 / 5xx / timeout."""
    if settings.AI_REASONING.strip().lower() != "off":
        max_tokens += REASONING_HEADROOM_TOKENS
    for attempt in range(2):
        started = time.perf_counter()
        try:
            response = _client().chat.completions.create(
                model=model,
                messages=conversation,  # type: ignore[arg-type]
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"models": [model, *fallbacks], "usage": {"include": True}, **_reasoning()},
            )
        except AuthenticationError as exc:
            _log_call(task, model, started, success=False, error=f"auth: {exc.status_code}")
            raise AIError(task, "not_configured", "OpenRouter rejected the API key") from exc
        except TRANSIENT_ERRORS as exc:
            _log_call(task, model, started, success=False, error=type(exc).__name__)
            if attempt == 0:
                time.sleep(BACKOFF_SECONDS)
                continue
            raise AIError(task, "unavailable", type(exc).__name__) from exc
        except APIStatusError as exc:
            _log_call(task, model, started, success=False, error=f"HTTP {exc.status_code}")
            raise AIError(task, "unavailable", f"HTTP {exc.status_code}") from exc

        if not response.choices:  # OpenRouter can return 200 with an error body
            _log_call(task, model, started, success=False, error="no choices in response")
            if attempt == 0:
                time.sleep(BACKOFF_SECONDS)
                continue
            raise AIError(task, "unavailable", "empty response")

        usage = response.usage
        extra = (usage.model_extra or {}) if usage else {}
        call_id = _log_call(
            task,
            response.model or model,
            started,
            success=True,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            cost=extra.get("cost"),
        )
        return response.choices[0].message.content, call_id
    raise AIError(task, "unavailable")  # pragma: no cover - loop always returns or raises


def _mock_call(task: str, schema: type[T], mock_input: Any) -> T:
    started = time.perf_counter()
    time.sleep(mocks.MOCK_LATENCY_SECONDS)  # so loading states are visible in the UI
    try:
        data = mocks.load(task, mock_input)
        result = schema.model_validate(data)
    except mocks.MockFailure as exc:
        _log_call(task, "mock", started, success=False, error=str(exc))
        raise AIError(task, "unavailable", "mock failure (forced)") from exc
    except ValidationError as exc:
        _log_call(task, "mock", started, success=False, error=_short_errors(exc))
        raise AIError(task, "invalid_output", _short_errors(exc)) from exc
    _log_call(task, "mock", started, success=True, prompt_tokens=0, completion_tokens=0, cost=0.0)
    return result
