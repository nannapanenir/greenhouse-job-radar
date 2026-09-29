"""Authentication business logic: signup, login, logout, refresh, current user.

Translates Supabase results/errors into Job Radar's own contract (``AuthError``
codes and clean models). Never returns provider payloads or tokens to callers
other than the router, which puts tokens into HttpOnly cookies only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .models import AuthUser, LoginRequest, SignupRequest
from .supabase_client import SupabaseAuthClient, SupabaseConfig, SupabaseError, SupabaseUnavailable

log = logging.getLogger("backend.auth")


class AuthError(Exception):
    """Job Radar auth error: HTTP status, stable machine code, user-safe message."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


def not_configured() -> AuthError:
    return AuthError(503, "auth_not_configured", "Authentication is not configured yet.")


def unavailable() -> AuthError:
    return AuthError(503, "auth_unavailable", "Authentication is temporarily unavailable. Please try again.")


def not_authenticated() -> AuthError:
    return AuthError(401, "not_authenticated", "Please sign in to continue.")


def session_expired() -> AuthError:
    return AuthError(401, "session_expired", "Your session has expired. Please sign in again.")

_SESSION_CODES = {"refresh_token_not_found", "refresh_token_already_used", "session_not_found", "session_expired",
                  "bad_jwt", "no_authorization", "user_not_found", "invalid_grant"}
_EXISTS_CODES = {"user_already_exists", "email_exists", "identity_already_exists"}
_WEAK_REASONS = {"length": "at least the required number of characters",
                 "characters": "a mix of letters, numbers and symbols",
                 "pwned": "a password that has not appeared in a data breach"}


def translate(error: SupabaseError, *, context: str) -> AuthError:
    """Supabase error -> Job Radar error. ``context``: signup | login | refresh | session."""
    code, text = error.code, error.message.lower()
    if error.status == 429 or code.startswith("over_") or "rate limit" in text:
        return AuthError(429, "rate_limited", "Too many attempts. Please wait a moment and try again.")
    if code in _EXISTS_CODES or "already registered" in text:
        return AuthError(409, "account_exists", "An account with this email already exists. Try signing in.")
    if code == "email_not_confirmed" or "email not confirmed" in text:
        return AuthError(403, "email_not_verified", "Please verify your email address, then sign in.")
    if code == "weak_password":
        needs = [_WEAK_REASONS[r] for r in error.reasons if r in _WEAK_REASONS]
        detail = f" Use {', '.join(needs)}." if needs else ""
        return AuthError(422, "weak_password", f"This password is too weak.{detail}")
    if code in ("signup_disabled", "email_provider_disabled"):
        return AuthError(403, "signup_disabled", "New sign-ups are currently disabled.")
    if code in ("email_address_invalid", "email_address_not_authorized", "validation_failed"):
        return AuthError(422, "invalid_email", "This email address can't be used. Check it and try again.")
    if context == "login" and (code in ("invalid_credentials", "invalid_grant") or "invalid login" in text):
        return AuthError(401, "invalid_credentials", "Incorrect email or password.")
    if context in ("refresh", "session") and (code in _SESSION_CODES or error.status in (401, 403)
                                              or "refresh token" in text):
        return session_expired()
    log.warning("Unmapped Supabase auth error during %s: HTTP %d (%s)", context, error.status, code)
    return AuthError(400, "auth_failed", "Authentication failed. Please try again.")


def to_user(data: dict) -> AuthUser:
    metadata = data.get("user_metadata") if isinstance(data.get("user_metadata"), dict) else {}
    name = metadata.get("name") or metadata.get("full_name")
    return AuthUser(id=str(data["id"]), email=data.get("email"), name=name if isinstance(name, str) else None)


@dataclass
class AuthSession:
    """Internal only: tokens go to cookies, ``user`` goes to the response."""
    user: AuthUser
    access_token: str
    refresh_token: Optional[str]
    expires_in: Optional[int]


def _session(data: dict) -> AuthSession:
    if not isinstance(data, dict) or not data.get("access_token") or not isinstance(data.get("user"), dict):
        raise unavailable()
    return AuthSession(user=to_user(data["user"]), access_token=data["access_token"],
                       refresh_token=data.get("refresh_token"), expires_in=data.get("expires_in"))


@dataclass
class SignupResult:
    session: Optional[AuthSession]  # present when Supabase signs the user in immediately (confirmation off)
    email_verification_required: bool


class AuthService:
    def __init__(self, config: Optional[SupabaseConfig], *, transport=None):
        self.client = SupabaseAuthClient(config, transport=transport) if config else None

    @property
    def configured(self) -> bool:
        return self.client is not None

    def _client(self) -> SupabaseAuthClient:
        if self.client is None:
            raise not_configured()
        return self.client

    async def _call(self, context: str, coro_factory):
        try:
            return await coro_factory(self._client())
        except SupabaseUnavailable:
            raise unavailable() from None
        except SupabaseError as error:
            raise translate(error, context=context) from None

    async def signup(self, request: SignupRequest, *, redirect_to: Optional[str] = None) -> SignupResult:
        data = await self._call("signup", lambda c: c.sign_up(request.email, request.password, request.name,
                                                               redirect_to=redirect_to))
        if not isinstance(data, dict):
            raise unavailable()
        if data.get("access_token"):
            return SignupResult(session=_session(data), email_verification_required=False)
        user = data.get("user") if isinstance(data.get("user"), dict) else data
        if not user.get("id"):
            raise unavailable()
        # With email confirmation on, Supabase answers a sign-up for an existing
        # address with an obfuscated user that has no identities.
        if user.get("identities") == []:
            raise translate(SupabaseError(400, "user_already_exists"), context="signup")
        return SignupResult(session=None, email_verification_required=True)

    async def login(self, request: LoginRequest) -> AuthSession:
        return _session(await self._call("login", lambda c: c.sign_in_with_password(request.email, request.password)))

    async def refresh(self, refresh_token: Optional[str]) -> AuthSession:
        if not refresh_token:
            raise session_expired()
        return _session(await self._call("refresh", lambda c: c.refresh_session(refresh_token)))

    async def current_user(self, access_token: Optional[str]) -> AuthUser:
        """Validates the access token with Supabase (honors sign-out and revoked sessions)."""
        if not access_token:
            raise not_authenticated()
        data = await self._call("session", lambda c: c.get_user(access_token))
        if not isinstance(data, dict) or not data.get("id"):
            raise session_expired()
        return to_user(data)

    async def resolve(self, access_token: Optional[str], refresh_token: Optional[str]
                      ) -> tuple[Optional[AuthUser], Optional[AuthSession]]:
        """Current user, refreshing the session when the access token expired.

        Returns (user, new_session); new_session is set when cookies must be rewritten.
        Raises AuthError only for provider outages/misconfiguration; an invalid session
        simply resolves to (None, None).
        """
        if not access_token and not refresh_token:
            return None, None
        if access_token:
            try:
                return await self.current_user(access_token), None
            except AuthError as error:
                if error.status != 401:
                    raise
        if not refresh_token:
            return None, None
        try:
            session = await self.refresh(refresh_token)
        except AuthError as error:
            if error.status != 401:
                raise
            return None, None
        return session.user, session

    async def logout(self, access_token: Optional[str]) -> None:
        """Revokes the session at Supabase when possible; the caller clears cookies regardless."""
        if not access_token or self.client is None:
            return
        try:
            await self.client.sign_out(access_token)
        except (SupabaseError, SupabaseUnavailable) as error:
            log.info("Supabase sign-out not confirmed (%s); cookies cleared anyway", type(error).__name__)

    async def request_password_reset(self, email: str, *, redirect_to: Optional[str] = None) -> None:
        """Prepared for POST /api/auth/forgot-password (needs Supabase redirect/reset setup first).
        Never reveals whether the address exists."""
        try:
            await self._call("signup", lambda c: c.recover(email, redirect_to=redirect_to))
        except AuthError as error:
            if error.code in ("auth_not_configured", "auth_unavailable", "rate_limited"):
                raise
