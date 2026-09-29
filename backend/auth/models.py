"""Auth request/response models. Responses never carry tokens or provider data."""

from __future__ import annotations

import re
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, Field, field_validator

# Pragmatic check (Supabase does the authoritative validation): one @, a dot in the domain, no spaces.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN = 8
PASSWORD_MAX = 72  # bcrypt input limit used by Supabase Auth


def _email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address.")
    return value


Email = Annotated[str, AfterValidator(_email)]


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: Email
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name is required.")
        return value


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class ForgotPasswordRequest(BaseModel):  # prepared for POST /api/auth/forgot-password (not routed yet)
    email: Email


class AuthUser(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None


class SessionResponse(BaseModel):
    """GET /me, POST /login, POST /refresh."""
    authenticated: bool
    user: Optional[AuthUser] = None


class SignupResponse(BaseModel):
    success: bool = True
    emailVerificationRequired: bool
    authenticated: bool
    user: Optional[AuthUser] = None


class SuccessResponse(BaseModel):
    success: bool = True
