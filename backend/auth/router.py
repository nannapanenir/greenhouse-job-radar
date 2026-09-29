"""/api/auth routes: HTTP handling only (business logic lives in service.py).

Error contract (every auth error): ``{"detail": "<user-safe message>", "code": "<stable code>"}``
with a matching HTTP status (see ``auth_error_handler``). Responses never contain
tokens; the session lives in HttpOnly cookies (cookies.py).

Planned, not routed yet: ``POST /api/auth/forgot-password`` (``AuthService.request_password_reset``
is ready; needs Supabase redirect URLs and a reset-password page first).
"""

from __future__ import annotations

import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from .cookies import clear_session_cookies, read_tokens, set_session_cookies
from .dependencies import get_auth_service, get_current_user
from .models import AuthUser, LoginRequest, SessionResponse, SignupRequest, SignupResponse, SuccessResponse
from .service import AuthError, AuthService, AuthSession


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(_no_store)])
_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+(:\d+)?$")


def _email_redirect(request: Request) -> Optional[str]:
    """Where Supabase's confirmation link lands: this deployment's origin (production or the
    current Preview). Supabase ignores it unless it is in the project's Redirect URLs list."""
    configured = os.environ.get("AUTH_EMAIL_REDIRECT_URL", "").strip()
    if configured:
        return configured
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    host = host.split(",")[0].strip()
    if not _HOST_RE.match(host):
        return None
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
    return f"{'https' if proto == 'https' else 'http'}://{host}/"


def _start_session(response: Response, request: Request, session: AuthSession) -> None:
    set_session_cookies(response, request, access_token=session.access_token,
                        refresh_token=session.refresh_token, expires_in=session.expires_in)


@router.post("/signup", response_model=SignupResponse)
async def signup(body: SignupRequest, request: Request, response: Response,
                 service: AuthService = Depends(get_auth_service)) -> SignupResponse:
    result = await service.signup(body, redirect_to=_email_redirect(request))
    if result.session:
        _start_session(response, request, result.session)
        return SignupResponse(emailVerificationRequired=False, authenticated=True, user=result.session.user)
    return SignupResponse(emailVerificationRequired=True, authenticated=False)


@router.post("/login", response_model=SessionResponse)
async def login(body: LoginRequest, request: Request, response: Response,
                service: AuthService = Depends(get_auth_service)) -> SessionResponse:
    session = await service.login(body)
    _start_session(response, request, session)
    return SessionResponse(authenticated=True, user=session.user)


@router.post("/logout", response_model=SuccessResponse)
async def logout(request: Request, response: Response,
                 service: AuthService = Depends(get_auth_service)) -> SuccessResponse:
    access_token, _ = read_tokens(request)
    await service.logout(access_token)
    clear_session_cookies(response, request)
    return SuccessResponse()


@router.post("/refresh", response_model=SessionResponse)
async def refresh(request: Request, response: Response,
                  service: AuthService = Depends(get_auth_service)) -> SessionResponse:
    _, refresh_token = read_tokens(request)
    session = await service.refresh(refresh_token)  # 401 session_expired clears cookies (handler)
    _start_session(response, request, session)
    return SessionResponse(authenticated=True, user=session.user)


async def _optional_user(request: Request, response: Response,
                         service: AuthService = Depends(get_auth_service)) -> Optional[AuthUser]:
    try:
        return await get_current_user(request, response, service)
    except AuthError as error:
        if error.code != "auth_not_configured":
            raise
        clear_session_cookies(response, request)  # stale cookies, auth switched off
        return None


@router.get("/me", response_model=SessionResponse)
async def me(user: Optional[AuthUser] = Depends(_optional_user)) -> SessionResponse:
    """Always 200 with ``authenticated`` true/false (503 only if Supabase is unreachable)."""
    return SessionResponse(authenticated=user is not None, user=user)


async def auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
    response = JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code},
                            headers={"Cache-Control": "no-store"})
    access_token, refresh_token = read_tokens(request)
    if exc.status == 401 and (access_token or refresh_token):
        clear_session_cookies(response, request, keep_refresh=refresh_token is None)
    return response
