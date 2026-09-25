# Job Radar Agent (Phase 1)

Python agent that collects jobs from **Greenhouse, Lever and Ashby**, converts
them to one common Job model, applies the shared US-location filter,
deduplicates, sorts newest-first and writes `public/data/jobs.json`.

Standard library only (Python 3.10+). `pytest` is needed for tests only.

```
python agent/main.py                                   # live APIs -> public/data/jobs.json
python agent/main.py --only greenhouse,lever           # subset of providers
python agent/main.py --fixtures tests/agent/fixtures \
       --sources tests/agent/fixtures/sources.json     # offline, saved responses
python agent/main.py --save-fixtures /tmp/live         # also save raw responses for replay
python -m pytest                                       # tests (from repo root)
node scripts/greenhouse-parity.mjs                     # Greenhouse parity vs existing frontend
```

If **every** company fails (e.g. no network) the agent exits 1 and does not
overwrite an existing `jobs.json`.

## Architecture

```
main.py (orchestrator only)
  ├─ config/settings.py      load companies + location keywords
  ├─ adapters/               one per provider: fetch + map raw -> Job
  │    base.py               JobAdapter contract, HTTP/fixture transports,
  │                          per-company error isolation, concurrent collect_all
  │    greenhouse.py  lever.py  ashby.py
  ├─ processing/             provider-independent
  │    normalizer.py         clean_html_content (port of src/utils/htmlCleaner.js), empty -> None
  │    filters.py            US location filter (port of buildKeywordRegex, whole word)
  │    deduplicator.py       by applyUrl, then global id (first wins)
  │    sorter.py             newest first (updatedAt, else postedAt; undated last)
  └─ output/exporter.py      jobs.json (atomic write)
```

Adapters never filter, dedupe, sort or match roles. Role profiles, search,
time and status filters stay in the React app (they are per-user).

## Configuration

| Provider | Company list |
|---|---|
| Greenhouse | **Existing app config** — `GREENHOUSE_COMPANIES` env var (same JSON as on Vercel), else `src/config/greenhouse-companies.json`. A `"greenhouse"` array in `sources.json` overrides both. |
| Lever | `agent/config/sources.json` → `"lever"`: `{ "name", "key", "enabled" }`, key = `jobs.lever.co/<key>` |
| Ashby | `agent/config/sources.json` → `"ashby"`: key = `jobs.ashbyhq.com/<key>` |

Location keywords are read from `src/config/role-profiles.json` (same list as the UI).
The Lever/Ashby entries shipped in `sources.json` are unverified examples.

## Common Job model (`jobs.json` → `jobs[]`)

| Field | Greenhouse | Lever | Ashby |
|---|---|---|---|
| `id` | `greenhouse:{token}:{id}` | `lever:{key}:{id}` | `ashby:{key}:{id}` |
| `title` | `title` | `text` | `title` |
| `location` | `location.name` / `location` | `categories.location` | `location` |
| `description` | cleaned `content` | `descriptionPlain` + `lists` + `additionalPlain` | `descriptionPlain` / cleaned `descriptionHtml` |
| `postedAt` | `first_published` | `createdAt` (epoch ms → ISO) | `publishedAt` |
| `updatedAt` | `updated_at` | — (not provided) | `updatedAt` if present |
| `applyUrl` | `absolute_url` (**exact** — UI job-status key) | `applyUrl`, else `hostedUrl` | `applyUrl`, else `jobUrl` |
| `sourceUrl` | `absolute_url` | `hostedUrl` | `jobUrl` |
| `metadata` | internalJobId, requisitionId, departments | team, department, commitment, allLocations, workplaceType, country | isRemote, workplaceType, employmentType, department, team, secondaryLocations, country |

Missing values are `null`; nothing is fabricated. **Timestamps differ by
provider**: Greenhouse = last update, Lever/Ashby = publish time. Sorting and
the UI's freshness use `updatedAt ?? postedAt`.

`jobs.json` also contains `generatedAt`, `statistics`, per-provider `sources`,
per-company `companies` (status, jobsFetched, jobsKept, error) and `failures`.

## Frontend

The app keeps its live Greenhouse flow by default. `?data=agent` in the URL
makes **Fetch Latest Jobs** load `/data/jobs.json` instead, mapped by
`toUiJob()` in `src/services/agentJobsService.js` to the fields the UI already
uses (`absoluteUrl = applyUrl`, so saved statuses carry over).
`public/data/jobs.json` is git-ignored until the output is verified live.

## Greenhouse parity

`scripts/greenhouse-parity.mjs` runs the existing `greenhouseService.js`
(unchanged) and the agent on the same fixtures and compares every UI field,
job order, company success/failure lists, all role profiles, and the HTML
cleaner on edge cases.

Intentional difference: a Greenhouse location object with an empty name is
kept by the agent (as "no location"); the legacy flow accidentally drops it
because the object itself fails the location regex.

Known legacy quirk kept for parity: Greenhouse double-escapes `&`, and the
cleaner decodes entities once, so descriptions can show a literal `&amp;`.
Fix it in both cleaners together when the legacy flow is retired.

## Adding a provider

1. `adapters/<name>.py`: subclass `JobAdapter`, set `source`, implement
   `board_url`, `extract_postings`, `map_job` (return `None` to skip).
2. Add the name to `SOURCES` (`models/job.py`) and `ADAPTERS` (`adapters/__init__.py`).
3. Add fixtures under `tests/agent/fixtures/<name>/` and mapping tests.
