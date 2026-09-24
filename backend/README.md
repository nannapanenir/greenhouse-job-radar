# Job Radar Python API (Phase 2 — Resume AI)

FastAPI backend that brings the standalone
[Resume Tailor](https://github.com/nannapanenir/resume-tailor) into Job Radar,
reimplemented in Python. The Phase 1 job agent stays in `agent/`.

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --port 8000      # from the repo root (or: python -m backend)
npm run dev                               # Vite proxies /api/health, /api/ai, /api/resume, /api/jobs
```

Open **Resume AI** in the app (or `/resume-ai`).

## Architecture

```
React (Vite)  Jobs ──"Tailor Resume" (Common Job)──► Resume AI ──► Applications
                                                      │  fetch /api/*
FastAPI  backend/main.py
  api/system.py   GET /api/health · GET /api/ai/status · POST|DELETE /api/ai/settings · GET /api/jobs
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

## AI providers

| Provider | Config |
|---|---|
| OpenRouter | `AI_PROVIDER=openrouter`, `AI_MODEL`, `OPENROUTER_API_KEY` |
| Local (Ollama, LM Studio, llama.cpp, vLLM) | `AI_PROVIDER=local`, `AI_MODEL`, `LOCAL_AI_BASE_URL` (e.g. `http://localhost:11434/v1`), optional `LOCAL_AI_API_KEY` |
| Gemini | `AI_PROVIDER=gemini`, `AI_MODEL` (e.g. `gemini-2.0-flash`), `GEMINI_API_KEY` — via Gemini's OpenAI-compatible endpoint |

Environment variables win. Without them, **Resume AI → Settings** saves the
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
3. **Evidence rules** (stage 2, new): blocked with a reason if the new text adds
   a skill/technology without evidence (same role for bullets, whole profile
   for the summary), a number/metric not in the original or its evidence, a
   seniority/title word the candidate never held, a degree/certification not
   on file, or another employer's name.
4. **Claims correction**: JD skills without evidence can't be "Verified" or a
   "strong match" — they stay in *Still missing*; blocked changes lower the
   proposed score.
5. **User edits** are checked (`/check-change`); unsupported edits need an
   explicit "Save anyway (flagged)".
6. **Generation** applies only `accepted`/`edited` changes, server-side, to a
   deep copy of the Master profile, skips changes whose original line no longer
   matches, and asserts protected facts are unchanged.

## Tests & parity

```bash
python -m pytest                                        # agent + backend (131 tests)
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
