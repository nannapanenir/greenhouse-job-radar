"""Job Radar Agent entry point.

    python agent/main.py                       # live APIs -> public/data/jobs.json
    python agent/main.py --fixtures DIR        # offline, saved responses
    python agent/main.py --only greenhouse     # subset of providers
    python agent/main.py --save-fixtures DIR   # also save raw responses for replay/parity

Pipeline: collect (adapters) -> normalize -> filter -> deduplicate -> sort -> export.
This file only orchestrates; provider parsing lives in agent/adapters.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    # Allow `python agent/main.py` from the repo root.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "agent"

import json  # noqa: E402

from agent.adapters import ADAPTERS, FixtureTransport, HttpTransport, RecordingTransport, collect_all  # noqa: E402
from agent.config import settings  # noqa: E402
from agent.models.job import SOURCES  # noqa: E402
from agent.output import build_output, write_json  # noqa: E402
from agent.processing import deduplicate_jobs, filter_jobs, normalize_jobs, sort_jobs  # noqa: E402

log = logging.getLogger("agent")


def run(
    *,
    sources_file: Path | None = None,
    fixtures: Path | None = None,
    only: list[str] | None = None,
    generated_at: str | None = None,
    save_fixtures: Path | None = None,
) -> dict:
    """Run the pipeline and return the jobs.json payload (does not write)."""
    sources = settings.load_sources(sources_file)
    location_keywords = settings.load_location_keywords()
    transport = FixtureTransport(fixtures) if fixtures else HttpTransport(settings.REQUEST_TIMEOUT_SECONDS)
    if save_fixtures:
        transport = RecordingTransport(transport, save_fixtures)
        _save_sources(sources, Path(save_fixtures) / "sources.json")

    tasks = []
    for source in SOURCES:
        if only and source not in only:
            continue
        adapter = ADAPTERS[source](transport)
        tasks.extend((adapter, company) for company in sources[source] if company.enabled)

    log.info("Collecting from %d companies", len(tasks))
    results = collect_all(tasks, max_workers=settings.MAX_WORKERS)

    kept = []
    for result in results:
        result.jobs = filter_jobs(normalize_jobs(result.jobs), location_keywords)
        result.jobs_kept = len(result.jobs)
        kept.extend(result.jobs)

    jobs = sort_jobs(deduplicate_jobs(kept))
    return build_output(jobs, results, jobs_after_filters=len(kept), generated_at=generated_at)


def _save_sources(sources: dict, path: Path) -> None:
    """Write the resolved company lists next to recorded fixtures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        source: [{"name": c.name, "token" if source == "greenhouse" else "key": c.key, "enabled": c.enabled}
                 for c in companies]
        for source, companies in sources.items()
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect jobs into public/data/jobs.json")
    parser.add_argument("--sources", type=Path, help="sources.json path (default: agent/config/sources.json)")
    parser.add_argument("--fixtures", type=Path, help="read saved responses from DIR/<source>/<key>.json")
    parser.add_argument("--output", type=Path, default=settings.DEFAULT_OUTPUT_FILE)
    parser.add_argument("--only", help="comma-separated providers, e.g. greenhouse,lever")
    parser.add_argument("--save-fixtures", type=Path, help="save raw provider responses to DIR for replay")
    parser.add_argument("--generated-at", help="fixed generatedAt timestamp (reproducible output)")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    if only and set(only) - set(SOURCES):
        parser.error(f"--only must be from: {', '.join(SOURCES)}")

    try:
        data = run(sources_file=args.sources, fixtures=args.fixtures, only=only,
                   generated_at=args.generated_at, save_fixtures=args.save_fixtures)
    except (OSError, ValueError) as error:
        log.error("Configuration error: %s", error)
        return 2

    stats = data["statistics"]
    if stats["companiesSearched"] > 0 and stats["successfulCompanies"] == 0:
        # Don't replace a good jobs.json with an empty one (e.g. network down).
        log.error("All %d companies failed; %s was NOT updated", stats["companiesSearched"], args.output)
        return 1

    write_json(data, args.output)
    log.info(
        "Wrote %s: %d jobs (%d scanned, %d/%d companies ok, %d duplicates removed)",
        args.output,
        stats["jobsKept"],
        stats["jobsScanned"],
        stats["successfulCompanies"],
        stats["companiesSearched"],
        stats["duplicatesRemoved"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
