"""Provider-independent AI interface (shared by Resume AI and, later, job matching).

Ports resume-tailor/server/aiProvider.js (retry policy) and
extractJsonObject.js (robust JSON extraction).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional

log = logging.getLogger("backend.ai")

Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": str}


class AIError(Exception):
    def __init__(self, message: str, *, status: Optional[int] = None, retryable: bool = True):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class AIProvider(ABC):
    """One chat-completion call. Implementations never log or expose keys."""

    name: str = "provider"
    label: str = "AI provider"

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    async def complete(self, messages: list[Message], *, temperature: float = 0.1, timeout: float = 60.0) -> str:
        """Return the assistant message text or raise AIError."""


MIN_ATTEMPT_SECONDS = 5.0


async def complete_with_retry(
    provider: AIProvider,
    messages: list[Message],
    *,
    attempts: int = 3,
    per_attempt_timeout: Optional[float] = None,
    total_budget: Optional[float] = None,
    temperature: float = 0.1,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Retry transient failures (timeouts, 429, 5xx, empty replies), not 4xx.

    All attempts (and the back-off between them) share ``total_budget`` so a
    slow provider can't outlive a serverless function's execution window; each
    attempt gets ``min(per_attempt_timeout, time left)``. Defaults come from
    ``config.ai_timeouts()``.
    """
    if per_attempt_timeout is None or total_budget is None:
        from ..config import ai_timeouts

        default_attempt, default_budget = ai_timeouts()
        per_attempt_timeout = per_attempt_timeout or default_attempt
        total_budget = total_budget or default_budget

    deadline = clock() + total_budget
    last: Optional[AIError] = None
    for attempt in range(1, attempts + 1):
        remaining = deadline - clock()
        if remaining < MIN_ATTEMPT_SECONDS:
            break
        try:
            return await provider.complete(messages, temperature=temperature, timeout=min(per_attempt_timeout, remaining))
        except AIError as error:
            last = error
            log.warning("[ai] %s attempt %d/%d failed: %s", provider.name, attempt, attempts, error)
            if not error.retryable or attempt == attempts:
                raise
            backoff = min(2.0 * attempt, 5.0)
            if deadline - clock() - backoff < MIN_ATTEMPT_SECONDS:
                break
            await sleep(backoff)
    raise last or AIError(f"{provider.label} did not respond within the {round(total_budget)}s time budget.")


def extract_json_object(raw: Any) -> Any:
    """Port of extractJsonObject.js: tolerate <think> blocks, code fences, prose."""
    text = str(raw).strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
    text = re.sub(r"^```(json)?", "", text, flags=re.I)
    text = re.sub(r"```$", "", text).strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in the AI response. Response started with: {str(raw)[:300]}")
    candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except ValueError as error:
        raise ValueError(
            f"The AI response looked like JSON but failed to parse ({error}). Response started with: {candidate[:300]}"
        ) from None
