"""Tiny stand-in for the Supabase Auth REST API (end-to-end tests only).

    python tests/e2e/fake_supabase_server.py 8766

Supports what backend/auth uses: POST /auth/v1/signup, POST /auth/v1/token
(grant_type=password|refresh_token), GET /auth/v1/user, POST /auth/v1/logout.
Email confirmation is on (signup returns an unconfirmed user, no session).
One pre-confirmed account: e2e@example.com / E2E-password-123.
"""

import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PUBLISHABLE_KEY = "sb_publishable_E2E_KEY"
USERS = {"e2e@example.com": {"password": "E2E-password-123", "id": "e2e-user-1", "name": "E2E User"}}
ACCESS: dict[str, str] = {}   # token -> email
REFRESH: dict[str, str] = {}


def user_json(email):
    user = USERS[email]
    return {"id": user["id"], "email": email, "user_metadata": {"name": user["name"]},
            "email_confirmed_at": "2026-09-29T00:00:00Z", "identities": [{"id": "x", "provider": "email"}]}


def new_session(email):
    access, refresh = "at_" + secrets.token_hex(8), "rt_" + secrets.token_hex(8)
    ACCESS[access], REFRESH[refresh] = email, email
    return {"access_token": access, "refresh_token": refresh, "expires_in": 3600, "token_type": "bearer",
            "user": user_json(email)}


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body=None):
        payload = json.dumps(body).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def route(self, method):
        if self.headers.get("apikey") != PUBLISHABLE_KEY:
            return self.reply(401, {"message": "Invalid API key"})
        url = urlparse(self.path)
        grant = parse_qs(url.query).get("grant_type", [None])[0]
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        bearer = (self.headers.get("Authorization") or "").removeprefix("Bearer ")

        if (method, url.path) == ("POST", "/auth/v1/signup"):
            email = body["email"]
            if email in USERS:  # confirmation on: obfuscated user without identities
                return self.reply(200, {"id": "fake", "email": email, "identities": []})
            return self.reply(200, {"id": "new-" + secrets.token_hex(4), "email": email,
                                    "confirmation_sent_at": "2026-09-29T00:00:00Z", "identities": [{"id": "n"}]})
        if (method, url.path) == ("POST", "/auth/v1/token") and grant == "password":
            user = USERS.get(body.get("email"))
            if not user or user["password"] != body.get("password"):
                return self.reply(400, {"error_code": "invalid_credentials", "msg": "Invalid login credentials"})
            return self.reply(200, new_session(body["email"]))
        if (method, url.path) == ("POST", "/auth/v1/token") and grant == "refresh_token":
            email = REFRESH.pop(body.get("refresh_token"), None)
            if not email:
                return self.reply(400, {"error_code": "refresh_token_not_found", "msg": "Invalid Refresh Token"})
            return self.reply(200, new_session(email))
        if (method, url.path) == ("GET", "/auth/v1/user"):
            if bearer not in ACCESS:
                return self.reply(403, {"error_code": "bad_jwt", "msg": "invalid JWT"})
            return self.reply(200, user_json(ACCESS[bearer]))
        if (method, url.path) == ("POST", "/auth/v1/logout"):
            email = ACCESS.pop(bearer, None)
            for token, owner in list(REFRESH.items()):
                if owner == email:
                    REFRESH.pop(token)
            return self.reply(204)
        return self.reply(404, {"msg": "not found"})

    def do_GET(self):  # noqa: N802
        self.route("GET")

    def do_POST(self):  # noqa: N802
        self.route("POST")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1] if len(sys.argv) > 1 else 8766)), Handler).serve_forever()
