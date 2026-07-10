# AI Job Radar

Find fresh Applied AI, LLM, RAG, Machine Learning, and Generative AI opportunities from Greenhouse job boards.

## Features

- Fetches AI/ML jobs from multiple Greenhouse company boards
- AI keyword matching and filtering
- Time-based quick filters and custom time filters
- Job status tracking (New, Saved, Applied, Not Interested) via localStorage
- Company panel with enabled/disabled company counts
- Job configuration panel for keywords and locations
- Failed company tracking

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
- The frontend calls `/api/companies` on startup via `src/services/companyConfigService.js`.
- Jobs are fetched only from companies where `enabled === true`.
- During local development, if `/api/companies` is unavailable, the app falls back to `src/config/greenhouse-companies.json`. In production, a configuration failure shows a visible error instead of silently using the local file.

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
