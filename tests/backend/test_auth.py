"""Phase 3A authentication (backend/auth). Supabase is mocked with httpx.MockTransport."""

import base64
import json
import re
from pathlib import Path

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend import auth
from backend.auth import cookies
from backend.auth.dependencies import get_auth_service, get_current_user, require_authenticated_user
from backend.auth.models import AuthUser
from backend.auth.service import AuthService
from backend.auth.supabase_client import AuthConfigError, SupabaseConfig, load_config
from backend.main import app

URL = "https://proj-ref.supabase.co"
KEY = "sb_publishable_TESTKEY123"
PASSWORD = "Sup3r-Secret-Pass!"
ACCESS, REFRESH = "access-token-AAA", "refresh-token-RRR"
NEW_ACCESS, NEW_REFRESH = "access-token-BBB", "refresh-token-SSS"
SECRETS = (ACCESS, REFRESH, NEW_ACCESS, NEW_REFRESH, KEY, PASSWORD, "proj-ref", "supabase")

USER = {"id": "user-1", "aud": "authenticated", "role": "authenticated", "email": "ram@example.com",
        "email_confirmed_at": "2026-09-29T00:00:00Z", "phone": "", "app_metadata": {"provider": "email"},
        "user_metadata": {"name": "Ram"}, "identities": [{"id": "i1", "provider": "email"}]}


def session(access=ACCESS, refresh=REFRESH, expires_in=3600):
    return {"access_token": access, "token_type": "bearer", "expires_in": expires_in, "expires_at": 1,
            "refresh_token": refresh, "user": USER}


class FakeSupabase:
    """Scriptable Supabase Auth. ``routes[(method, path)]`` -> (status, body) or an exception."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.valid_access = {ACCESS}
        self.valid_refresh = {REFRESH}
        self.routes = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/auth/v1")
        grant = request.url.params.get("grant_type")
        key = (request.method, path + (f"?{grant}" if grant else ""))
        if key in self.routes:
            outcome = self.routes[key]
            if isinstance(outcome, Exception):
                raise outcome
            status, body = outcome
            return httpx.Response(status, json=body) if body is not None else httpx.Response(status)
        body = json.loads(request.content or b"{}")
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
        if key == ("POST", "/token?password"):
            if body.get("password") == PASSWORD:
                return httpx.Response(200, json=session())
            return httpx.Response(400, json={"code": 400, "error_code": "invalid_credentials",
                                             "msg": "Invalid login credentials"})
        if key == ("POST", "/token?refresh_token"):
            if body.get("refresh_token") in self.valid_refresh:
                self.valid_access.add(NEW_ACCESS)
                return httpx.Response(200, json=session(NEW_ACCESS, NEW_REFRESH))
            return httpx.Response(400, json={"code": 400, "error_code": "refresh_token_not_found",
                                             "msg": "Invalid Refresh Token: Refresh Token Not Found"})
        if key == ("GET", "/user"):
            if bearer in self.valid_access:
                return httpx.Response(200, json=USER)
            return httpx.Response(403, json={"code": 403, "error_code": "bad_jwt",
                                             "msg": "invalid JWT: token is expired"})
        if key == ("POST", "/logout"):
            self.valid_access.discard(bearer)
            return httpx.Response(204)
        if key == ("POST", "/signup"):
            return httpx.Response(200, json=session())  # confirmation off by default
        return httpx.Response(404, json={"msg": "not found"})

    def last(self, path):
        return next(r for r in reversed(self.requests) if r.url.path.endswith(path))


@pytest.fixture
def fake():
    return FakeSupabase()


@pytest.fixture
def client(fake, monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    config = SupabaseConfig(url=URL, publishable_key=KEY)
    app.dependency_overrides[get_auth_service] = lambda: AuthService(config, transport=httpx.MockTransport(fake.handler))
    yield TestClient(app)
    app.dependency_overrides.pop(get_auth_service, None)


def login(client):
    return client.post("/api/auth/login", json={"email": "Ram@Example.com", "password": PASSWORD})


def set_cookies(response):
    return [v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"]


def cookie_header(response, name):
    return next(c for c in set_cookies(response) if c.startswith(f"{name}="))


def assert_no_leak(response):
    text = response.text.lower()
    for secret in SECRETS:
        assert secret.lower() not in text, secret
    for field in ("access_token", "refresh_token", "app_metadata", "identities", "aud", "role"):
        assert f'"{field}"' not in text


# ---- configuration -------------------------------------------------------------------------------

def test_missing_configuration(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    with pytest.raises(AuthConfigError) as info:
        load_config()
    assert "SUPABASE_URL" in str(info.value) and "SUPABASE_PUBLISHABLE_KEY" in str(info.value)
    raw = TestClient(app)  # real dependency, no env
    for path, body in (("/api/auth/signup", {"name": "Ram", "email": "r@example.com", "password": PASSWORD}),
                       ("/api/auth/login", {"email": "r@example.com", "password": PASSWORD})):
        response = raw.post(path, json=body)
        assert response.status_code == 503
        assert response.json() == {"detail": "Authentication is not configured yet.", "code": "auth_not_configured"}
    me = raw.get("/api/auth/me")
    assert me.status_code == 200 and me.json() == {"authenticated": False, "user": None}


def test_stale_cookies_with_auth_unconfigured_resolve_to_signed_out(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    raw = TestClient(app)
    raw.cookies.set(cookies.ACCESS_COOKIE, ACCESS, path="/api")
    response = raw.get("/api/auth/me")
    assert response.json() == {"authenticated": False, "user": None}
    assert any(c.startswith("jr_access=") and "Max-Age=0" in c for c in set_cookies(response))


def test_config_loads_and_rejects_secret_keys(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", URL + "/")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", KEY)
    assert load_config() == SupabaseConfig(url=URL, publishable_key=KEY)
    service_role = "x." + base64.urlsafe_b64encode(b'{"role":"service_role"}').decode().rstrip("=") + ".y"
    for bad in ("sb_secret_abc", service_role):
        monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", bad)
        with pytest.raises(AuthConfigError) as info:
            load_config()
        assert bad not in str(info.value)
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", KEY)
    monkeypatch.setenv("SUPABASE_URL", "http://evil.example.com")
    with pytest.raises(AuthConfigError):
        load_config()


# ---- signup --------------------------------------------------------------------------------------

def test_signup_success_signs_in_when_confirmation_is_off(client, fake):
    response = client.post("/api/auth/signup", json={"name": "  Ram  ", "email": "Ram@Example.com",
                                                     "password": PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"success": True, "emailVerificationRequired": False, "authenticated": True,
                               "user": {"id": "user-1", "email": "ram@example.com", "name": "Ram"}}
    sent = fake.last("/signup")
    assert json.loads(sent.content) == {"email": "ram@example.com", "password": PASSWORD, "data": {"name": "Ram"}}
    assert sent.headers["apikey"] == KEY and "authorization" not in sent.headers
    assert sent.url.params["redirect_to"] == "http://testserver/"
    assert cookie_header(response, "jr_access") and cookie_header(response, "jr_refresh")
    assert_no_leak(response)


def test_signup_requiring_email_verification(client, fake):
    unconfirmed = {**USER, "email_confirmed_at": None, "confirmation_sent_at": "2026-09-29T00:00:00Z"}
    fake.routes[("POST", "/signup")] = (200, unconfirmed)
    response = client.post("/api/auth/signup", json={"name": "Ram", "email": "ram@example.com", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"success": True, "emailVerificationRequired": True, "authenticated": False,
                               "user": None}
    assert set_cookies(response) == []
    assert_no_leak(response)


@pytest.mark.parametrize("outcome", [
    (200, {**USER, "email_confirmed_at": None, "identities": []}),                      # confirmation on
    (422, {"code": 422, "error_code": "user_already_exists", "msg": "User already registered"}),
    (400, {"code": 400, "msg": "User already registered"}),                              # older servers
])
def test_signup_existing_account(client, fake, outcome):
    fake.routes[("POST", "/signup")] = outcome
    response = client.post("/api/auth/signup", json={"name": "Ram", "email": "ram@example.com", "password": PASSWORD})
    assert response.status_code == 409
    assert response.json()["code"] == "account_exists"
    assert set_cookies(response) == []


def test_signup_weak_password_and_rate_limit(client, fake):
    fake.routes[("POST", "/signup")] = (422, {"error_code": "weak_password", "msg": "Password should contain...",
                                              "weak_password": {"reasons": ["characters", "pwned"]}})
    body = {"name": "Ram", "email": "ram@example.com", "password": PASSWORD}
    response = client.post("/api/auth/signup", json=body)
    assert response.status_code == 422 and response.json()["code"] == "weak_password"
    assert "letters, numbers and symbols" in response.json()["detail"]
    fake.routes[("POST", "/signup")] = (429, {"error_code": "over_email_send_rate_limit", "msg": "rate limit"})
    response = client.post("/api/auth/signup", json=body)
    assert response.status_code == 429 and response.json()["code"] == "rate_limited"


@pytest.mark.parametrize("body", [
    {"name": "Ram", "email": "not-an-email", "password": PASSWORD},
    {"name": "   ", "email": "ram@example.com", "password": PASSWORD},
    {"name": "Ram", "email": "ram@example.com", "password": "short"},
    {"name": "Ram", "email": "ram@example.com", "password": "x" * 73},
])
def test_signup_validation(client, fake, body):
    assert client.post("/api/auth/signup", json=body).status_code == 422
    assert fake.requests == []


# ---- login ---------------------------------------------------------------------------------------

def test_invalid_login(client):
    response = client.post("/api/auth/login", json={"email": "ram@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password.", "code": "invalid_credentials"}
    assert set_cookies(response) == []
    assert "invalid login credentials" not in response.text.lower()  # provider text not forwarded


def test_login_email_not_verified(client, fake):
    fake.routes[("POST", "/token?password")] = (400, {"error_code": "email_not_confirmed", "msg": "Email not confirmed"})
    response = login(client)
    assert response.status_code == 403 and response.json()["code"] == "email_not_verified"


def test_successful_login_sets_cookies_without_tokens_in_json(client, fake):
    response = login(client)
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "user": {"id": "user-1", "email": "ram@example.com",
                                                               "name": "Ram"}}
    assert response.headers["cache-control"] == "no-store"
    assert_no_leak(response)
    access = cookie_header(response, "jr_access")
    refresh = cookie_header(response, "jr_refresh")
    assert access.startswith(f"jr_access={ACCESS};") and refresh.startswith(f"jr_refresh={REFRESH};")
    for header in (access, refresh):
        assert "HttpOnly" in header and "SameSite=lax" in header and "Secure" not in header  # plain-HTTP dev
    assert "Path=/api;" in access + ";" and "Max-Age=3600" in access
    assert "Path=/api/auth" in refresh and f"Max-Age={30 * 24 * 3600}" in refresh
    assert "Domain" not in access + refresh
    assert json.loads(fake.last("/token").content)["email"] == "ram@example.com"


@pytest.mark.parametrize("env, headers", [({"VERCEL": "1"}, {}), ({}, {"x-forwarded-proto": "https"}),
                                          ({"AUTH_COOKIE_SECURE": "1"}, {})])
def test_cookies_are_secure_on_vercel_and_https(client, monkeypatch, env, headers):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    response = client.post("/api/auth/login", json={"email": "ram@example.com", "password": PASSWORD},
                           headers=headers)
    assert "Secure" in cookie_header(response, "jr_access") and "Secure" in cookie_header(response, "jr_refresh")


# ---- current user --------------------------------------------------------------------------------

def test_me_authenticated(client, fake):
    login(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "user": {"id": "user-1", "email": "ram@example.com",
                                                               "name": "Ram"}}
    assert fake.last("/user").headers["authorization"] == f"Bearer {ACCESS}"
    assert_no_leak(response)


def test_me_unauthenticated(client, fake):
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}
    assert fake.requests == []  # no provider call without cookies


def test_me_refreshes_expired_access_token(client, fake):
    login(client)
    fake.valid_access.clear()  # access token expired
    response = client.get("/api/auth/me")
    assert response.json()["authenticated"] is True
    assert cookie_header(response, "jr_access").startswith(f"jr_access={NEW_ACCESS};")
    assert cookie_header(response, "jr_refresh").startswith(f"jr_refresh={NEW_REFRESH};")
    assert_no_leak(response)


def test_me_with_dead_session_clears_cookies(client, fake):
    login(client)
    fake.valid_access.clear()
    fake.valid_refresh.clear()
    response = client.get("/api/auth/me")
    assert response.status_code == 200 and response.json() == {"authenticated": False, "user": None}
    assert all("Max-Age=0" in c for c in set_cookies(response)) and len(set_cookies(response)) == 2


# ---- logout --------------------------------------------------------------------------------------

def test_logout_clears_cookies_and_revokes_session(client, fake):
    login(client)
    response = client.post("/api/auth/logout")
    assert response.status_code == 200 and response.json() == {"success": True}
    cleared = set_cookies(response)
    assert any(c.startswith("jr_access=") and "Max-Age=0" in c and "Path=/api" in c for c in cleared)
    assert any(c.startswith("jr_refresh=") and "Max-Age=0" in c and "Path=/api/auth" in c for c in cleared)
    assert fake.last("/logout").headers["authorization"] == f"Bearer {ACCESS}"
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_logout_succeeds_even_if_provider_fails(client, fake):
    login(client)
    fake.routes[("POST", "/logout")] = httpx.ConnectError("down")
    response = client.post("/api/auth/logout")
    assert response.status_code == 200 and len(set_cookies(response)) == 2


def test_logout_without_session(client, fake):
    response = client.post("/api/auth/logout")
    assert response.status_code == 200 and fake.requests == []


# ---- refresh -------------------------------------------------------------------------------------

def test_refresh_success(client, fake):
    login(client)
    response = client.post("/api/auth/refresh")
    assert response.status_code == 200 and response.json()["authenticated"] is True
    assert json.loads(fake.last("/token").content) == {"refresh_token": REFRESH}
    assert cookie_header(response, "jr_access").startswith(f"jr_access={NEW_ACCESS};")
    assert_no_leak(response)


def test_invalid_refresh_session(client, fake):
    login(client)
    fake.valid_refresh.clear()
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401
    assert response.json() == {"detail": "Your session has expired. Please sign in again.", "code": "session_expired"}
    assert len(set_cookies(response)) == 2 and all("Max-Age=0" in c for c in set_cookies(response))
    assert "refresh token not found" not in response.text.lower()


def test_refresh_without_cookie(client, fake):
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401 and response.json()["code"] == "session_expired"
    assert fake.requests == []


# ---- provider failures ---------------------------------------------------------------------------

@pytest.mark.parametrize("outcome", [httpx.ConnectError("boom"), httpx.ReadTimeout("slow"),
                                     (500, {"msg": "internal: db at 10.0.0.1 failed"}), (502, None)])
def test_supabase_provider_failure(client, fake, outcome):
    fake.routes[("POST", "/token?password")] = outcome
    response = login(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is temporarily unavailable. Please try again.",
                               "code": "auth_unavailable"}
    assert "10.0.0.1" not in response.text
    assert set_cookies(response) == []


def test_me_reports_outage_without_clearing_session(client, fake):
    login(client)
    fake.routes[("GET", "/user")] = httpx.ConnectError("down")
    response = client.get("/api/auth/me")
    assert response.status_code == 503 and response.json()["code"] == "auth_unavailable"
    assert set_cookies(response) == []  # a provider outage must not sign the user out


def test_unmapped_provider_error_is_generic(client, fake):
    fake.routes[("POST", "/token?password")] = (400, {"error_code": "something_new", "msg": "internal detail xyz"})
    response = login(client)
    assert response.status_code == 400
    assert response.json() == {"detail": "Authentication failed. Please try again.", "code": "auth_failed"}


# ---- no leakage across every endpoint ------------------------------------------------------------

def test_no_secret_or_token_leakage_anywhere(client, fake, caplog):
    caplog.set_level("DEBUG")
    responses = [
        client.post("/api/auth/signup", json={"name": "Ram", "email": "ram@example.com", "password": PASSWORD}),
        login(client), client.get("/api/auth/me"), client.post("/api/auth/refresh"),
        client.post("/api/auth/logout"), client.post("/api/auth/refresh"), client.get("/api/auth/me"),
    ]
    for response in responses:
        assert_no_leak(response)
    logs = caplog.text
    for secret in (ACCESS, REFRESH, NEW_ACCESS, NEW_REFRESH, KEY, PASSWORD, "ram@example.com"):
        assert secret not in logs


# ---- reusable dependency -------------------------------------------------------------------------

def test_require_authenticated_user_dependency(fake, monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    other = FastAPI()
    auth.register(other)

    @other.get("/api/private")
    async def private(user: AuthUser = Depends(require_authenticated_user)):
        return {"hello": user.name}

    @other.get("/api/optional")
    async def optional(user=Depends(get_current_user)):
        return {"signedIn": user is not None}

    config = SupabaseConfig(url=URL, publishable_key=KEY)
    other.dependency_overrides[get_auth_service] = lambda: AuthService(config, transport=httpx.MockTransport(fake.handler))
    c = TestClient(other)
    denied = c.get("/api/private")
    assert denied.status_code == 401 and denied.json() == {"detail": "Please sign in to continue.",
                                                           "code": "not_authenticated"}
    assert c.get("/api/optional").json() == {"signedIn": False}
    login(c)
    assert c.get("/api/private").json() == {"hello": "Ram"}
    fake.valid_access.clear()  # expired: refresh cookie isn't sent outside /api/auth -> 401, client refreshes
    expired = c.get("/api/private")
    assert expired.status_code == 401
    assert c.post("/api/auth/refresh").status_code == 200
    assert c.get("/api/private").json() == {"hello": "Ram"}


def test_existing_endpoints_stay_public(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ai/status").status_code == 200


# ---- frontend never talks to Supabase ------------------------------------------------------------

def test_frontend_has_no_supabase_client_or_token_storage():
    root = Path(__file__).resolve().parents[2]
    package = json.loads((root / "package.json").read_text())
    deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    assert not [d for d in deps if "supabase" in d]
    offenders = []
    for path in (root / "src").rglob("*"):
        if path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            text = path.read_text(encoding="utf-8")
            if re.search(r"@supabase/|createClient\(|VITE_SUPABASE|SUPABASE_URL|sb_publishable|supabase\.co", text) \
                    or re.search(r"(localStorage|sessionStorage)[^;\n]*(token|session)", text, re.I):
                offenders.append(str(path.relative_to(root)))
    assert offenders == []
    auth_api = (root / "src/features/auth/services/authApi.js").read_text()
    assert "'/api/auth'" in auth_api and not re.search(r"(localStorage|sessionStorage)\.(set|get)Item", auth_api)
