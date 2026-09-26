# AI Job Radar

Find fresh Applied AI, LLM, RAG, Machine Learning, and Generative AI opportunities from Greenhouse job boards.

## Features

- Fetches jobs from Greenhouse, Lever and Ashby boards server-side (one `POST /api/jobs/refresh` per click)
- AI keyword matching and filtering
- Time-based quick filters and custom time filters
- Job status tracking (New, Saved, Applied, Not Interested) via localStorage
- Company panel with enabled/disabled company counts
- Job configuration panel for keywords and locations
- Failed company tracking

## Role Profiles

Jobs are fetched once (US locations only) and then filtered client-side by the active **role profile**, so switching roles is instant and needs no refetch.

- Built-in roles live in `src/config/role-profiles.json`: AI / LLM Engineer (default), Frontend Engineer, Full-Stack Engineer, and Security Engineer. The shared US `locationKeywords` list is also defined there.
- `locationKeywords` (shared by all roles) is applied at fetch time and covers the whole US: country terms (`United States`, `USA`, `US`, `Remote US`…), all 50 states + DC by name and as `, ST` codes (so any `City, ST` location matches), and ~230 tech cities from major hubs down to smaller markets (Boise, Des Moines, Chattanooga, Sioux Falls…) for locations that omit the state. Location matching is whole-word and case-insensitive. City names shared with other countries (Cambridge, Vancouver, Richmond, Birmingham…) are listed with their state, e.g. `Cambridge, MA`. Jobs with no location are always kept.
- Each profile has `includeKeywords`, `excludeTitleKeywords`, and `searchDescription`. A job is shown if its title has no excluded word and matches at least one include keyword. Matching is whole-word and case-insensitive (`RAG` does not match "leverage"), against the title only unless `searchDescription` is `true`.
- Use the **Role Profile** panel in the sidebar to switch roles, edit keywords, create new roles, delete roles, or reset to the defaults. Edits are saved in the browser's localStorage.
- The active role is reflected in the URL as `?role=<id>` (e.g. `?role=security`), so a link opens with that role selected. Otherwise the last used role, then the default, is used.

## Vercel Company Configuration

Greenhouse company board tokens are configured using the Vercel environment variable:

```
GREENHOUSE_COMPANIES
```

The environment variable contains JSON. Example:

```json
[
  {
    "name": "Anthropic",
    "token": "anthropic",
    "enabled": true
  },
  {
    "name": "Figma",
    "token": "figma",
    "enabled": true
  }
]
```

Each company object must contain:

- `name`: non-empty string (company display name)
- `token`: non-empty string (Greenhouse board token)
- `enabled`: boolean (whether to fetch jobs from this company)

### Vercel Workflow

1. Open the Vercel project.
2. Go to **Settings**.
3. Open **Environment Variables**.
4. Create or edit `GREENHOUSE_COMPANIES`.
5. Paste valid JSON (see the example above).
6. Save the environment variable.
7. Redeploy the application so the new configuration is used.

Updating `GREENHOUSE_COMPANIES` does not require modifying the GitHub repository.

A new Vercel deployment may be required for environment variable changes to take effect.

### How It Works

- The Vercel serverless function at `api/companies.js` reads `GREENHOUSE_COMPANIES` from `process.env`, validates each company object, and returns only `{ name, token, enabled }` to the frontend.
- The frontend calls `/api/companies` on startup via `src/services/companyConfigService.js` to fill the **Companies** panel. It no longer drives fetching.
- The Python refresh endpoint reads the same `GREENHOUSE_COMPANIES` variable and fetches only companies where `enabled === true`.
- During local development, if `/api/companies` is unavailable, the app falls back to `src/config/greenhouse-companies.json`. In production, a configuration failure shows a visible error instead of silently using the local file.

## Job fetching (server-side)

**Fetch Latest Jobs** makes one request, `POST /api/jobs/refresh`, to the Python API. The **Job Refresh Manager**
(`backend/jobs/refresh.py`) then fetches every enabled Greenhouse, Lever and Ashby board with bounded concurrency
(`JOB_FETCH_CONCURRENCY`, default 6). The browser never calls a job provider directly.

- Boards are fetched as a sliding window: a new company starts as soon as a slot frees up.
- Each company has its own timeouts; a failing board doesn't stop the others.
- Transient errors (timeouts, network errors, 429, 5xx) are retried with jittered backoff; 4xx errors are not retried.
- The whole refresh has a time budget.
- Results go through the agent's shared pipeline (normalize, filter, dedupe, sort).

The response contains the Common Jobs plus `refresh` metadata
(`companiesRequested`, `companiesSucceeded`, `companiesFailed`, `jobCount`, `failures[]`, `durationMs`, `slowest[]`).
Nothing is scheduled: jobs refresh only when you click the button.

The same adapters also run as a CLI (`python agent/main.py`, writing `public/data/jobs.json`).
See [`agent/README.md`](agent/README.md) for the adapters, configuration and Job model, and
[`backend/README.md`](backend/README.md) for the refresh settings and Vercel limits.

## Resume AI (Phase 2)

Job Radar now includes **Resume AI**, the standalone Resume Tailor reimplemented on a Python (FastAPI) backend:
upload a PDF/DOCX **Master Resume**, click **Tailor Resume** on any Greenhouse/Lever/Ashby job (or paste an external
job description), review evidence-backed changes (Accept/Edit/Reject), and download an ATS-friendly DOCX or PDF.
The server blocks unsupported claims and never changes employers, titles, dates or education.

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --port 8000   # Python API
npm run dev                            # app at http://localhost:5173 (proxies /api/resume, /api/ai, ...)
```

Configure an AI provider (OpenRouter, a local OpenAI-compatible server, or Gemini) with environment variables or, locally, in
Resume AI → Settings; keys stay on the server. On Vercel the API runs as a Python Function in the same project
(`api/index.py`) and is configured only through Vercel environment variables. See [`backend/README.md`](backend/README.md).

## Local Development

```bash
npm install
npm run dev
```

The local fallback config lives at `src/config/greenhouse-companies.json` and is only used when `import.meta.env.DEV === true` and `/api/companies` cannot be reached.

## Build

```bash
npm run build
```
