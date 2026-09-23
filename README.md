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
