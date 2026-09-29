"""Session cookies. The browser holds the Supabase tokens only as HttpOnly cookies.

The React app and the API share one origin (``<host>/`` and ``<host>/api/*`` on
Vercel; the Vite dev proxy locally), so the cookies are first-party:

| Cookie        | Holds                  | Path        | Max-Age                          |
|---------------|------------------------|-------------|----------------------------------|
| ``jr_access`` | Supabase access token  | ``/api``    | token lifetime (``expires_in``)  |
| ``jr_refresh``| Supabase refresh token | ``/api/auth`` | ``AUTH_REFRESH_COOKIE_MAX_AGE`` (30 days) |

- ``HttpOnly``: JavaScript (and any XSS) cannot read either token.
- ``Secure``: on Vercel (production and every Preview are HTTPS) and whenever the
  request arrived over HTTPS. Plain-HTTP local development (``http://localhost``)
  gets non-Secure cookies so Safari still stores them. ``AUTH_COOKIE_SECURE=1|0`` overrides.
- ``SameSite=Lax``: same-origin requests always send the cookies; cross-site
  POST/fetch requests never do (CSRF protection). ``Strict`` would buy nothing
  here and would drop the session when arriving from an email link.
- No ``Domain``: host-only cookies. Each Preview URL keeps its own session and
  a session never leaks to other ``*.vercel.app`` deployments.
- The refresh token is scoped to ``/api/auth`` so it is sent only to the auth
  endpoints, never to Jobs/Resume AI requests.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Request, Response

from ..config import on_vercel

ACCESS_COOKIE = "jr_access"
REFRESH_COOKIE = "jr_refresh"
ACCESS_PATH = "/api"
REFRESH_PATH = "/api/auth"
SAMESITE = "lax"
DEFAULT_ACCESS_MAX_AGE = 3600
DEFAULT_REFRESH_MAX_AGE = 30 * 24 * 3600


def _refresh_max_age() -> int:
    try:
        value = int(os.environ.get("AUTH_REFRESH_COOKIE_MAX_AGE", DEFAULT_REFRESH_MAX_AGE))
        return value if value > 0 else DEFAULT_REFRESH_MAX_AGE
    except ValueError:
        return DEFAULT_REFRESH_MAX_AGE


def cookie_secure(request: Request) -> bool:
    override = os.environ.get("AUTH_COOKIE_SECURE", "").strip().lower()
    if override in ("1", "true", "yes"):
        return True
    if override in ("0", "false", "no"):
        return False
    if on_vercel():
        return True
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return (forwarded or request.url.scheme) == "https"


def set_session_cookies(response: Response, request: Request, *, access_token: str, refresh_token: Optional[str],
                        expires_in: Optional[int]) -> None:
    secure = cookie_secure(request)
    try:
        access_max_age = int(expires_in) if expires_in else DEFAULT_ACCESS_MAX_AGE
    except (TypeError, ValueError):
        access_max_age = DEFAULT_ACCESS_MAX_AGE
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=max(60, access_max_age), path=ACCESS_PATH,
                        httponly=True, secure=secure, samesite=SAMESITE)
    if refresh_token:
        response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=_refresh_max_age(), path=REFRESH_PATH,
                            httponly=True, secure=secure, samesite=SAMESITE)


def clear_session_cookies(response: Response, request: Request, *, keep_refresh: bool = False) -> None:
    """``keep_refresh``: only the access token is known to be dead. Outside /api/auth the
    request never carries the refresh cookie, so it must survive for POST /api/auth/refresh."""
    secure = cookie_secure(request)
    response.delete_cookie(ACCESS_COOKIE, path=ACCESS_PATH, httponly=True, secure=secure, samesite=SAMESITE)
    if not keep_refresh:
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, httponly=True, secure=secure, samesite=SAMESITE)


def read_tokens(request: Request) -> tuple[Optional[str], Optional[str]]:
    return request.cookies.get(ACCESS_COOKIE) or None, request.cookies.get(REFRESH_COOKIE) or None
