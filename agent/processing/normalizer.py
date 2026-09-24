"""Shared normalization helpers.

``clean_html_content`` is an exact port of ``cleanHtmlContent`` in
``src/utils/htmlCleaner.js``. Keep the two in sync: the Greenhouse parity
check (scripts/greenhouse-parity.mjs) compares their output.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Optional

from ..models.job import Job

# Same entities, same order as htmlCleaner.js. Order matters: "&amp;" is
# decoded first, so Greenhouse's escaped HTML ("&amp;lt;") becomes real tags.
_ENTITIES = (
    ("&amp;", "&"),
    ("&lt;", "<"),
    ("&gt;", ">"),
    ("&quot;", '"'),
    ("&#39;", "'"),
    ("&#x27;", "'"),
    ("&nbsp;", " "),
    ("&ndash;", "-"),
    ("&mdash;", "-"),
    ("&rsquo;", "'"),
    ("&lsquo;", "'"),
    ("&rdquo;", '"'),
    ("&ldquo;", '"'),
)

# Characters JavaScript's String.prototype.trim() removes.
_JS_WHITESPACE = (
    "\t\n\v\f\r          "
    "        　﻿"
)


def _from_char_code(code: int) -> str:
    """JS String.fromCharCode: truncates to 16 bits. Lone surrogates can't be
    written as UTF-8, so they become U+FFFD."""
    code &= 0xFFFF
    if 0xD800 <= code <= 0xDFFF:
        return "�"
    return chr(code)


def clean_html_content(html: Optional[str]) -> str:
    if not html:
        return ""

    content = html
    for entity, char in _ENTITIES:
        content = content.replace(entity, char)

    content = re.sub(r"</p>", "\n\n", content, flags=re.I)
    content = re.sub(r"<br\s*/?>", "\n", content, flags=re.I)
    content = re.sub(r"</div>", "\n", content, flags=re.I)
    content = re.sub(r"</li>", "\n", content, flags=re.I)
    content = re.sub(r"<li[^>]*>", "• ", content, flags=re.I)
    content = re.sub(r"</h[1-6]>", "\n\n", content, flags=re.I)
    content = re.sub(r"<h[1-6][^>]*>", "\n", content, flags=re.I)
    content = re.sub(r"<[^>]+>", "", content)

    content = re.sub(r"\n{3,}", "\n\n", content)
    content = re.sub(r"[ \t]+", " ", content)
    content = content.strip(_JS_WHITESPACE)

    content = re.sub(r"&#(\d+);", lambda m: _from_char_code(int(m.group(1))), content)
    content = re.sub(
        r"&#x([0-9a-f]+);", lambda m: _from_char_code(int(m.group(1), 16)), content, flags=re.I
    )
    return content


def text_or_none(value: Any) -> Optional[str]:
    """Non-empty strings pass through unchanged; anything else becomes None.

    Values are deliberately not trimmed: the existing Greenhouse flow keeps
    titles/locations verbatim, and parity depends on that.
    """
    if not isinstance(value, str) or value == "":
        return None
    return value


def epoch_ms_to_iso(value: Any) -> Optional[str]:
    """Convert epoch milliseconds (Lever) to ISO-8601 UTC. Invalid -> None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp for sorting. Unparseable -> None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_job(job: Job) -> Job:
    """Provider-independent cleanup applied after adapters.

    Turns empty strings into None and de-duplicates matched keywords.
    Never invents or rewrites values.
    """
    seen: set[str] = set()
    keywords = []
    for kw in job.matched_keywords:
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)

    return replace(
        job,
        title=text_or_none(job.title),
        location=text_or_none(job.location),
        description=job.description or None,
        apply_url=text_or_none(job.apply_url),
        source_url=text_or_none(job.source_url),
        matched_keywords=keywords,
    )


def normalize_jobs(jobs: list[Job]) -> list[Job]:
    return [normalize_job(job) for job in jobs]
