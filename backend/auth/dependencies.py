"""Reusable FastAPI auth dependencies. Other modules use only these (never Supabase):

    from backend.auth.dependencies import require_authenticated_user
    @router.post("/something")
    async def handler(user: AuthUser = Depends(require_authenticated_user)): ...

Outside ``/api/auth`` the browser sends only the access-token cookie (the
refresh cookie is path-scoped), so an expired access token yields
``401 session_expired`` there; the frontend then calls ``POST /api/auth/refresh``
and retries.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, Request, Response

from .cookies import clear_session_cookies, read_tokens, set_session_cookies
from .models import AuthUser
from .service import AuthService, not_authenticated
from .supabase_client import AuthConfigError, load_config

log = logging.getLogger("backend.auth")
_warned = False


def get_auth_service() -> AuthService:
    """Configured service, or an unconfigured one whose provider calls fail with 503 auth_not_configured."""
    global _warned
    try:
        return AuthService(load_config())
    except AuthConfigError as error:
        if not _warned:  # GET /api/auth/me runs on every page load; warn once per instance
            log.warning("Supabase Auth is not configured: %s", error)  # names env vars only, never values
            _warned = True
        return AuthService(None)


async def get_current_user(request: Request, response: Response,
                           service: AuthService = Depends(get_auth_service)) -> Optional[AuthUser]:
    """The signed-in user, or None. Refreshes an expired session when the refresh cookie
    is available (``/api/auth/*``) and rewrites the cookies. Provider outages raise 503."""
    access_token, refresh_token = read_tokens(request)
    if not access_token and not refresh_token:
        return None
    user, session = await service.resolve(access_token, refresh_token)
    if session:
        set_session_cookies(response, request, access_token=session.access_token,
                            refresh_token=session.refresh_token, expires_in=session.expires_in)
    elif user is None:
        clear_session_cookies(response, request, keep_refresh=refresh_token is None)
    return user


async def require_authenticated_user(user: Optional[AuthUser] = Depends(get_current_user)) -> AuthUser:
    if user is None:
        raise not_authenticated()
    return user
