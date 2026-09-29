"""Supabase Auth (GoTrue) REST client. The only module that knows Supabase.

Uses the public Auth API with the project's *publishable* key, exactly like a
Supabase client library would, but server-side and stateless (no session kept
in memory between requests: every call gets the user's tokens explicitly, which
is what a serverless, multi-user backend needs). The secret/service-role key is
never used and is rejected if configured by mistake.

Environment:
    SUPABASE_URL               https://<project-ref>.supabase.co
    SUPABASE_PUBLISHABLE_KEY   sb_publishable_... (or the legacy anon JWT)
    SUPABASE_TIMEOUT_SECONDS   optional, default 10
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

log = logging.getLogger("backend.auth")


class AuthConfigError(Exception):
    """Supabase is not (correctly) configured. Message is for server logs only."""


class SupabaseError(Exception):
    """Supabase rejected a request. ``code`` is Supabase's error code (safe to map, never shown raw)."""

    def __init__(self, status: int, code: str, message: str = "", *, reasons: tuple[str, ...] = ()):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code
        self.message = message  # provider text: used for mapping only, never returned to the browser
        self.reasons = reasons


class SupabaseUnavailable(Exception):
    """Timeout, network error or 5xx from Supabase."""


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    publishable_key: str
    timeout: float = 10.0


def _is_secret_key(key: str) -> bool:
    if key.startswith("sb_secret_"):
        return True
    parts = key.split(".")
    if len(parts) == 3:  # legacy JWT keys: refuse service_role
        try:
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
            return payload.get("role") == "service_role"
        except (ValueError, UnicodeDecodeError):
            return False
    return False


def load_config() -> SupabaseConfig:
    """Read and validate the configuration. Raises AuthConfigError (never includes key values)."""
    url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
    missing = [name for name, value in (("SUPABASE_URL", url), ("SUPABASE_PUBLISHABLE_KEY", key)) if not value]
    if missing:
        raise AuthConfigError(f"missing {', '.join(missing)}")
    parsed = urlparse(url)
    local = parsed.hostname in ("localhost", "127.0.0.1")
    if parsed.scheme not in ("https", "http") or not parsed.hostname or (parsed.scheme == "http" and not local):
        raise AuthConfigError("SUPABASE_URL must be an https:// URL")
    if _is_secret_key(key):
        raise AuthConfigError("SUPABASE_PUBLISHABLE_KEY holds a secret/service-role key; use the publishable key")
    try:
        timeout = float(os.environ.get("SUPABASE_TIMEOUT_SECONDS") or 10)
    except ValueError:
        timeout = 10.0
    return SupabaseConfig(url=url, publishable_key=key, timeout=max(1.0, timeout))


def _error_from(response: httpx.Response) -> SupabaseError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    code = str(body.get("error_code") or body.get("error") or "").strip() or f"http_{response.status_code}"
    message = str(body.get("msg") or body.get("message") or body.get("error_description") or "")
    weak = body.get("weak_password")
    reasons = tuple(str(r) for r in weak.get("reasons", [])) if isinstance(weak, dict) else ()
    return SupabaseError(response.status_code, code, message, reasons=reasons)


class SupabaseAuthClient:
    """Thin async wrapper over the Supabase Auth endpoints Job Radar needs."""

    def __init__(self, config: SupabaseConfig, *, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.config = config
        self.transport = transport

    async def _request(self, method: str, path: str, *, json_body: Any = None, params: Optional[dict] = None,
                       access_token: Optional[str] = None) -> Any:
        headers = {"apikey": self.config.publishable_key, "Accept": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            async with httpx.AsyncClient(base_url=f"{self.config.url}/auth/v1", timeout=self.config.timeout,
                                         transport=self.transport) as client:
                response = await client.request(method, path, json=json_body, params=params, headers=headers)
        except httpx.HTTPError as error:
            log.warning("Supabase Auth %s %s: %s", method, path, type(error).__name__)
            raise SupabaseUnavailable() from None
        if response.status_code >= 500:
            log.warning("Supabase Auth %s %s: HTTP %d", method, path, response.status_code)
            raise SupabaseUnavailable()
        if response.status_code >= 400:
            error = _error_from(response)
            log.info("Supabase Auth %s %s: HTTP %d (%s)", method, path, error.status, error.code)
            raise error
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise SupabaseUnavailable() from None

    async def sign_up(self, email: str, password: str, name: str, *, redirect_to: Optional[str] = None) -> dict:
        params = {"redirect_to": redirect_to} if redirect_to else None
        return await self._request("POST", "/signup", params=params,
                                   json_body={"email": email, "password": password, "data": {"name": name}})

    async def sign_in_with_password(self, email: str, password: str) -> dict:
        return await self._request("POST", "/token", params={"grant_type": "password"},
                                   json_body={"email": email, "password": password})

    async def refresh_session(self, refresh_token: str) -> dict:
        return await self._request("POST", "/token", params={"grant_type": "refresh_token"},
                                   json_body={"refresh_token": refresh_token})

    async def get_user(self, access_token: str) -> dict:
        return await self._request("GET", "/user", access_token=access_token)

    async def sign_out(self, access_token: str) -> None:
        # scope=local: ends this session only (other devices stay signed in).
        await self._request("POST", "/logout", params={"scope": "local"}, access_token=access_token)

    async def recover(self, email: str, *, redirect_to: Optional[str] = None) -> None:
        """Password-reset email. Wired up for the future /api/auth/forgot-password (not routed yet)."""
        params = {"redirect_to": redirect_to} if redirect_to else None
        await self._request("POST", "/recover", params=params, json_body={"email": email})
