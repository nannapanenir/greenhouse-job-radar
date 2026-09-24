"""JavaScript-compatible helpers so ported logic behaves exactly like the
Node reference (trim, Number(), Math.round)."""

from __future__ import annotations

import math
from typing import Any

JS_WHITESPACE = (
    "\t\n\v\f\r          "
    "        　﻿"
)


def js_trim(value: str) -> str:
    return value.strip(JS_WHITESPACE)


def js_str(value: Any) -> str:
    """``typeof v === 'string' ? v.trim() : ''``"""
    return js_trim(value) if isinstance(value, str) else ""


def js_number(value: Any) -> float:
    """``Number(value)`` (NaN for unconvertible values)."""
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = js_trim(value)
        if text == "":
            return 0.0
        try:
            if text.lower().startswith(("0x", "-0x", "+0x")):
                return float(int(text, 16))
            return float(text)
        except ValueError:
            return math.nan
    if isinstance(value, list):
        if not value:
            return 0.0
        if len(value) == 1:
            return js_number(value[0])
    return math.nan


def js_round(value: float) -> int:
    """``Math.round``: halves round up (towards +infinity)."""
    return int(math.floor(value + 0.5))


def clamp_pct(value: Any) -> int:
    """``Math.max(0, Math.min(100, Math.round(Number(n) || 0)))``"""
    number = js_number(value)
    if math.isnan(number) or number == 0:
        number = 0.0
    if math.isinf(number):
        return 100 if number > 0 else 0
    return max(0, min(100, js_round(number)))


def finite_number(value: Any) -> float | int:
    """``Number.isFinite(Number(v)) ? Number(v) : 0`` (ints stay ints)."""
    number = js_number(value)
    if math.isnan(number) or math.isinf(number):
        return 0
    return int(number) if number.is_integer() else number
