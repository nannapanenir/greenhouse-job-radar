"""Adapter contract, HTTP/fixture transports and per-company error isolation.

An adapter only (1) fetches one company's board and (2) maps each raw
posting to a ``Job``. Filtering, dedup and sorting happen in
``agent/processing`` and are shared by every provider.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..models.job import Job

log = logging.getLogger("agent")

USER_AGENT = "JobRadarAgent/1.0 (+https://github.com/nannapanenir/greenhouse-job-radar)"


class FetchError(Exception):
    """A board could not be fetched. The message is safe to show in the UI."""


class HttpError(FetchError):
    def __init__(self, status: int, reason: str):
        # Same wording as the existing frontend: `HTTP ${status}: ${statusText}`
        super().__init__(f"HTTP {status}: {reason}")
        self.status = status


@dataclass(frozen=True)
class Company:
    name: str
    key: str  # board token / site name
    enabled: bool = True


class HttpTransport:
    """GETs JSON with the standard library (no runtime dependencies)."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def get_json(self, url: str, *, source: str, company_key: str) -> Any:
        request = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            raise HttpError(error.code, error.reason or "Error") from None
        except (socket.timeout, TimeoutError):
            raise FetchError("request timeout") from None
        except urllib.error.URLError as error:
            reason = error.reason
            if isinstance(reason, (socket.timeout, TimeoutError)):
                raise FetchError("request timeout") from None
            raise FetchError(f"network error: {reason}") from None
        try:
            return json.loads(body)
        except ValueError:
            raise FetchError("invalid JSON response") from None


class FixtureTransport:
    """Serves saved responses from ``<root>/<source>/<company_key>.json``.

    A missing file behaves like an HTTP 404, so failure handling can be
    tested offline.
    """

    def __init__(self, root: Path):
        self.root = Path(root)

    def get_json(self, url: str, *, source: str, company_key: str) -> Any:
        path = self.root / source / f"{company_key}.json"
        if not path.is_file():
            raise HttpError(404, "Not Found")
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)


class RecordingTransport:
    """Wraps another transport and saves every successful response as a
    fixture (``<root>/<source>/<company_key>.json``) for offline replay."""

    def __init__(self, inner, root: Path):
        self.inner = inner
        self.root = Path(root)

    def get_json(self, url: str, *, source: str, company_key: str) -> Any:
        payload = self.inner.get_json(url, source=source, company_key=company_key)
        path = self.root / source / f"{company_key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return payload


@dataclass
class CompanyResult:
    source: str
    company: Company
    jobs: list[Job] = field(default_factory=list)
    jobs_fetched: int = 0      # raw postings returned by the provider
    jobs_skipped: int = 0      # postings that could not be mapped / unlisted
    jobs_kept: int = 0         # after universal filters (set by the pipeline)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class JobAdapter:
    """Base class. Subclasses set ``source`` and implement the two hooks."""

    source: str = ""

    def __init__(self, transport):
        self.transport = transport

    def board_url(self, company: Company) -> str:
        raise NotImplementedError

    def extract_postings(self, payload: Any) -> list[dict]:
        """Return the list of raw postings from the provider response."""
        raise NotImplementedError

    def map_job(self, raw: dict, company: Company) -> Optional[Job]:
        """Map one raw posting to a Job, or None to skip it (e.g. unlisted)."""
        raise NotImplementedError

    def collect(self, company: Company) -> CompanyResult:
        """Fetch + map one company. Never raises: failures are recorded."""
        result = CompanyResult(source=self.source, company=company)
        try:
            payload = self.transport.get_json(
                self.board_url(company), source=self.source, company_key=company.key
            )
            postings = self.extract_postings(payload)
        except FetchError as error:
            result.error = str(error)
            log.warning("%s/%s: FAILED - %s", self.source, company.key, result.error)
            return result
        except Exception as error:  # unexpected shape etc. - never crash the run
            result.error = f"unexpected error: {type(error).__name__}"
            log.warning("%s/%s: FAILED - %s (%s)", self.source, company.key, result.error, error)
            return result

        result.jobs_fetched = len(postings)
        for raw in postings:
            try:
                job = self.map_job(raw, company) if isinstance(raw, dict) else None
            except Exception as error:
                job = None
                log.warning("%s/%s: skipped malformed posting (%s)", self.source, company.key, error)
            if job is None:
                result.jobs_skipped += 1
            else:
                result.jobs.append(job)

        log.info("%s/%s: %d postings", self.source, company.key, result.jobs_fetched)
        return result


def collect_all(tasks: list[tuple[JobAdapter, Company]], max_workers: int = 8) -> list[CompanyResult]:
    """Run ``adapter.collect(company)`` concurrently; results keep task order."""
    if not tasks:
        return []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(lambda task: task[0].collect(task[1]), tasks))
