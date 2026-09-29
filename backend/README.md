# Job Radar Python API (Phase 2 — Resume AI)

FastAPI backend that brings the standalone
[Resume Tailor](https://github.com/nannapanenir/resume-tailor) into Job Radar,
reimplemented in Python. The Phase 1 job agent stays in `agent/`.

```bash
pip install -r backend/requirements.txt  # runtime (root requirements.txt) + uvicorn + pytest
uvicorn backend.main:app --port 8000      # from the repo root (or: python -m backend)
npm run dev                               # Vite proxies /api/health, /api/ai, /api/resume, /api/jobs
```

Open **Resume AI** in the app (or `/resume-ai`).

## Architecture

```
React (Vite)  Jobs ──"Tailor Resume" (Common Job)──► Resume AI ──► Applications
                                                      │  fetch /api/*
FastAPI  backend/main.py
  api/system.py   GET /api/health · GET /api/ai/status · POST|DELETE /api/ai/settings · GET /api/jobs (local jobs.json)
  api/jobs.py     POST /api/jobs/refresh  → jobs/refresh.py (Job Refresh Manager) → agent adapters + pipeline
  api/resume.py   POST /api/resume/{parse, extract-text, analyze, tailor, check-change,
                                   tailored-profile, generate, chat}
  resume/  parser → profile_extractor → tailor (AI or fallback_engine) → validator → apply → docx/pdf
  ai/      AIProvider ─ OpenRouterProvider · LocalProvider · GeminiProvider (shared infrastructure)
  models/  CandidateProfile (protected fields) · JobPosting (Phase 1 Common Job) · TailoringSession
```

The server keeps **no user data** (it is stateless and serverless-friendly). The
browser persists the profile, Master Resume metadata, current job, session and
tailored-resume history in localStorage behind
`src/features/resume-ai/services/resumeStore.js` (swap for a database later).
API keys never reach the browser.

## Deployment (Vercel, same project as the React app)

| Piece | Where |
|---|---|
| Entry point | `api/index.py` — imports the existing `backend.main:app` (no second backend) |
| Dependencies | root `requirements.txt` (runtime only); dev extras in `backend/requirements.txt` |
| Routing | `vercel.json` rewrites `/api/health`, `/api/ai/*`, `/api/resume/*`, `/api/jobs/*`, `/api/auth/*` → `/api/index`; `/api/companies` stays `api/companies.js` (Node); SPA fallback excludes `/api/`, `/assets/`, `/data/` |
| Function | `maxDuration: 60`; bundles `backend/**`, `agent/**` and `src/config/*.json` (company list, location keywords); excludes frontend code/tests/scripts |
| AI config | **Vercel environment variables only** (`VERCEL=1` ⇒ settings are read-only, the settings file is never read or written, save attempts return 409) |
| Uploads | 4 MB app limit (Vercel rejects request bodies over 4.5 MB) — same limit locally |
| AI time budget | 25 s per attempt, 50 s total across retries on Vercel (`AI_REQUEST_TIMEOUT_SECONDS`, `AI_TOTAL_BUDGET_SECONDS`) so retries finish inside the 60 s function window |
| `POST /api/jobs/refresh` | Server-side job fetching (see below). GZip-compressed response (Vercel caps responses at about 4.5 MB) |
| `GET /api/jobs` | Legacy local-dev reader for `public/data/jobs.json`. Not used by the app; returns 404 on Vercel |
| `/api/companies` | Still needed: it feeds the **Companies** panel (Node function, `GREENHOUSE_COMPANIES`) |

## Authentication (Phase 3A: `backend/auth/`)

Architecture: React → FastAPI (`/api/auth/*`) → Supabase Auth. The browser never talks to Supabase
and never sees a token; the session is two HttpOnly cookies set by FastAPI.

```
auth/router.py           routes + HTTP status mapping; error body {"detail", "code"}
auth/service.py          signup / login / logout / refresh / current user; Supabase error → Job Radar error
auth/models.py           request/response models (responses carry no tokens or provider data)
auth/dependencies.py     get_current_user (optional) · require_authenticated_user (401) for other APIs
auth/cookies.py          cookie names, flags, lifetimes
auth/supabase_client.py  the only Supabase-aware code: plain HTTPS calls to the Auth REST API with the
                         publishable key (stateless, so it suits serverless; no supabase-py session state)
```

| Endpoint | Success | Notes |
|---|---|---|
| `POST /api/auth/signup` `{name, email, password}` | `{success, emailVerificationRequired, authenticated, user}` | Name goes to Supabase user metadata. Confirmation on → `emailVerificationRequired: true`, no cookies; off → signed in |
| `POST /api/auth/login` `{email, password}` | `{authenticated: true, user}` + cookies | |
| `POST /api/auth/logout` | `{success: true}` | Revokes the session at Supabase (best effort), always clears cookies |
| `POST /api/auth/refresh` | `{authenticated: true, user}` + new cookies | From the refresh cookie |
| `GET /api/auth/me` | `{authenticated: true, user: {id, email, name}}` | **Always 200**; signed out → `{authenticated: false, user: null}`. Transparently refreshes an expired access token |

Errors: `{"detail": "<message for the user>", "code": "<stable code>"}`. Provider text is never forwarded.

| Code | Status | When |
|---|---|---|
| `invalid_credentials` | 401 | wrong email/password |
| `email_not_verified` | 403 | login before confirming the email |
| `account_exists` | 409 | signup with a registered email (also detected when confirmation is on) |
| `weak_password` | 422 | Supabase password policy (request validation 422s use FastAPI's list format) |
| `rate_limited` | 429 | Supabase rate limits |
| `signup_disabled` | 403 | sign-ups turned off in Supabase |
| `not_authenticated` / `session_expired` | 401 | no / dead session (cookies cleared) |
| `auth_not_configured` | 503 | `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` missing or invalid |
| `auth_unavailable` | 503 | Supabase timeout, network error or 5xx (session is kept) |

**Cookies** (frontend and API are the same origin, so these are first-party cookies):

| | `jr_access` | `jr_refresh` |
|---|---|---|
| Holds | Supabase access token | Supabase refresh token |
| Path | `/api` (every API call) | `/api/auth` (auth endpoints only) |
| Max-Age | token lifetime (`expires_in`, 1 h by default) | 30 days (`AUTH_REFRESH_COOKIE_MAX_AGE`) |
| Flags | `HttpOnly; SameSite=Lax` + `Secure` | same |

- `Secure`: always on Vercel (production and every Preview are HTTPS) and on any HTTPS request.
  Plain-HTTP local dev gets non-Secure cookies. Override with `AUTH_COOKIE_SECURE=1|0`.
- `SameSite=Lax`: cross-site requests never carry the session (CSRF); `Strict` adds nothing for a
  same-origin app and would drop the session when arriving from an email link.
- No `Domain`: host-only. Each Preview URL has its own session; nothing leaks across `*.vercel.app`.
- The access token is checked against Supabase (`GET /auth/v1/user`) on each authenticated request,
  so sign-out and revoked sessions take effect immediately (costs one round trip).
- Outside `/api/auth` an expired access token returns `401 session_expired` (the refresh cookie isn't
  sent there). The client calls `POST /api/auth/refresh` and retries: `authFetch()` in
  `src/features/auth/services/authApi.js` does this.
- Responses carry `Cache-Control: no-store`.

**Protecting an API later:** `user: AuthUser = Depends(require_authenticated_user)`. Nothing is protected yet.

| Endpoint | Recommendation |
|---|---|
| `/api/health`, `/api/ai/status` | stay public |
| `/api/auth/*` | public by design |
| `/api/resume/*` (parse, analyze, tailor, generate, chat, …) | protect: they spend AI quota. Do it together with the sign-in UI, or signed-out users lose Resume AI |
| `POST /api/jobs/refresh` | protect, or rate-limit per user: it fans out to every provider |
| `POST/DELETE /api/ai/settings` | read-only on Vercel already; protect if ever writable in production |
| future Applications / saved jobs / resume history APIs | protected from day one (per-user data) |
| `/api/companies` (Node) | public (non-sensitive company list) |

**Not implemented yet:** `POST /api/auth/forgot-password`. `AuthService.request_password_reset` and the
Supabase `recover` call are ready, but the route waits for Supabase redirect URLs and a reset-password page.

| Variable | Required | Notes |
|---|---|---|
| `SUPABASE_URL` | yes | `https://<project-ref>.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | yes | `sb_publishable_…` (or the legacy anon key). Secret/service-role keys are refused |
| `AUTH_EMAIL_REDIRECT_URL` | no | where the confirmation link lands; default is the requesting deployment's origin |
| `AUTH_REFRESH_COOKIE_MAX_AGE` | no | seconds, default 2592000 (30 days) |
| `AUTH_COOKIE_SECURE` | no | force `1`/`0`; default automatic |
| `SUPABASE_TIMEOUT_SECONDS` | no | default 10 |

## Job refresh (`POST /api/jobs/refresh`)

The Jobs page's **Fetch Latest Jobs** button is the only trigger. There is no cron, schedule, queue or database.

| Setting | Default | Meaning |
|---|---|---|
| `JOB_FETCH_CONCURRENCY` | 6 | Maximum simultaneous board requests. Uses a sliding window: the next company starts when a slot frees |
| `JOB_FETCH_TIMEOUT_SECONDS` | 15 | One HTTP request |
| `JOB_FETCH_COMPANY_TIMEOUT_SECONDS` | 25 | One company, all attempts included |
| `JOB_FETCH_RETRIES` | 2 | Extra attempts for timeouts, network errors, 429 and 5xx, with backoff 0.5 s, 1 s, … (capped at 4 s) and 50–100% jitter. Other 4xx errors are not retried |
| `JOB_REFRESH_BUDGET_SECONDS` | 45 on Vercel, 120 locally | Whole refresh. Companies that can't start in time are reported as "not attempted" |

Companies come from `GREENHOUSE_COMPANIES` (else `src/config/greenhouse-companies.json`) and
`agent/config/sources.json` (Lever/Ashby). For local development and tests only (both are ignored on Vercel),
`JOB_SOURCES_FILE` and `JOB_FETCH_FIXTURES_DIR` switch to fixture data.

Responses:

- `200`: the full jobs document (`jobs`, `companies`, `statistics`, …) plus `refresh`.
- `502`: `{detail, refresh}` when every company failed.
- `503`: no companies are configured.
- `500`: invalid configuration.

Failure reasons are short and sanitized (`HTTP 404`, `timeout`, `network error`, `invalid response`), with no URLs, stack traces or settings.

Measured with simulated provider latency (0.3–2 s per board, 5% of boards taking 6 s; live providers are not reachable from CI):

| Companies | Concurrency 1 | 6 | 12 |
|---|---|---|---|
| 6 | 6.3 s | 1.6 s | 1.6 s |
| 60 | 45 s (budget hit, 26 not attempted) | 15.8 s | 10.2 s |
| 120 | — | 29.2 s | 17.1 s |

Each response reports `refresh.durationMs` and the five slowest boards (`refresh.slowest`). Check these on the
Vercel preview with the real company list. If the duration gets close to the 45 s budget, raise `JOB_FETCH_CONCURRENCY`
or trim companies before reaching for background infrastructure.

## AI providers

| Provider | Config |
|---|---|
| OpenRouter | `AI_PROVIDER=openrouter`, `AI_MODEL`, `OPENROUTER_API_KEY` |
| Local (Ollama, LM Studio, llama.cpp, vLLM) | `AI_PROVIDER=local`, `AI_MODEL`, `LOCAL_AI_BASE_URL` (e.g. `http://localhost:11434/v1`), optional `LOCAL_AI_API_KEY` |
| Gemini | `AI_PROVIDER=gemini`, `AI_MODEL` (e.g. `gemini-2.0-flash`), `GEMINI_API_KEY` — via Gemini's OpenAI-compatible endpoint |
| Any provider (optional) | `AI_FALLBACK_MODEL` — comma-separated models of the same provider, tried once each (within the time budget) when the primary model is overloaded or rate-limited (429/5xx), e.g. Gemini "503 high demand" |

Environment variables win (and are the only source on Vercel). Locally, without them, **Resume AI → Settings** saves the
provider to `backend/data/settings.json` (mode 0600, git-ignored; folder
overridable with `RESUME_AI_DATA_DIR`), like the standalone app.
`/api/ai/status` reports configuration but never the key. Retries: 3 attempts
for timeouts, 429 and 5xx; 4xx fails fast.

Without a provider, tailoring uses the ported local keyword engine (same as the
standalone app); resume **extraction** needs a provider.

## Truthfulness protection

1. **Prompts** (unchanged from Resume Tailor) forbid invented content.
2. **Reference rules** (`validator.validate_changes`, stage 1): a change may only
   target an existing bullet id or `summary`, its `original` must equal that
   line exactly, and `updated` must be non-empty. Employer, title, dates,
   education and certifications are never targets.
3. **Evidence rules** (stage 2): blocked with a reason if the new text introduces
   anything the Master profile doesn't support (bullets: that role's own text,
   technologies, company and location; summary: the whole profile):
   - a skill/technology from the lexicon, the JD keywords or `keywordsAdded`;
   - **any new named entity** — a token that reads as a proper noun
     (capitalized mid-sentence, CamelCase, `C#`/`Node.js`/`.NET`, letter+digit
     like `EC2`) absent from the original line and its evidence. This general
     rule catches "Rust", "Go", "at Google" without a static list; lower-case
     rewording and reordering pass;
   - a number, or a word-form metric ("doubling", "tenfold", "hundreds of");
   - seniority/title words never held, or leadership/scope claims ("led",
     "managed a team", "mentored", "team of") without evidence or a lead title;
   - a degree/certification not on file, or another employer from the profile.
4. **Claims correction**: JD skills without evidence can't be "Verified" or a
   "strong match" — they stay in *Still missing*; blocked changes lower the
   proposed score.
5. **User edits** are checked (`/check-change`); unsupported edits need an
   explicit "Save anyway (flagged)".
6. **Generation** applies only `accepted`/`edited` changes, server-side, to a
   deep copy of the Master profile, skips changes whose original line no longer
   matches, **re-validates every applied text** (an accepted change that fails is
   skipped — so neither a stale session nor "Accept All Safe" can ship it; a
   failing edit is applied only with the user's explicit `userFlagged` override,
   reported in `X-User-Overrides`), and asserts protected facts are unchanged.
   Flagged text lives only in the session and never becomes evidence.

## Tests & parity

```bash
python -m pytest                                        # agent + backend (268 tests)
node scripts/resume-parity.mjs --reference ../resume-tailor   # needs `npm install` there
NODE_PATH=$(npm root -g) node tests/e2e/resume-ai.e2e.mjs      # browser end-to-end (Playwright)
```

`resume-parity.mjs` runs the **original Node modules** (only the AI call is
stubbed) and the Python port on the same fixtures. Intentional differences:

- skills returned as plain strings are kept (Node drops them);
- evidence validator blocks more AI suggestions and corrects claims;
- local engine matches profile skills case-insensitively and skips an empty summary;
- PDFs from ReportLab (incl. Resume AI's own output) parse in Python; the Node
  parser (pdf-parse 1.1.1) fails on them, and fails its first parse per process.
