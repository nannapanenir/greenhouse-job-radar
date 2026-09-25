"""Tiny OpenAI-compatible server for end-to-end tests (acts as a "local model").

    python tests/e2e/fake_ai_server.py 8765

Replies with canned fixtures: resume extraction -> tests/backend/fixtures/profile.json,
tailoring -> tests/backend/fixtures/ai_tailor_response.json.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "fixtures"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        system = body["messages"][0]["content"]
        name = "profile.json" if "resume-parsing engine" in system else "ai_tailor_response.json"
        content = (FIXTURES / name).read_text(encoding="utf-8")
        payload = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1] if len(sys.argv) > 1 else 8765)), Handler).serve_forever()
