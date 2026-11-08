"""Pull Bangkok tickets from the Traffy Fondue public search API.

The API returns the current state of each ticket and nothing about its past, so
history comes from pulling often and keeping every version we see. One pull
covers a window of Bangkok dates on `last_activity` and is written to local
files laid out the same way as the landing volume:

    tickets/run=<run_id>/page-0000.jsonl.gz   one line per ticket
    runs/<run_id>.json                        what the run fetched, written last

The API takes longer to answer the more tickets a window holds, whatever the
page size: a page from one month of 2024 (22,478 tickets) took 19 s on average,
a page from two days of November 2026 (about 7,000) took 6.5 s. With more pages
as well as slower ones, paging a window costs about the square of its size, so
a pull asks for one day at a time.
"""

from __future__ import annotations

import gzip
import json
import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

API_URL = "https://publicapi.traffy.in.th/share/teamchadchart/search"
PAGE_SIZE = 1000
MAX_PAGES = 200  # stops a runaway loop; a busy day is about 5 pages
PAUSE = 1.0  # seconds between requests
RUN_ID_FORMAT = "%Y%m%dT%H%M%SZ"  # a run is named after the time it started, in UTC
BANGKOK = ZoneInfo("Asia/Bangkok")

# Reporters' own words, officers' notes and photos. Nothing downstream uses
# them and they can identify people, so they never leave the runner.
DROPPED_FIELDS = ("description", "note", "photo_url", "after_photo")

log = logging.getLogger(__name__)


class ApiError(RuntimeError):
    """The API answered, but not with a page of tickets."""


@dataclass(frozen=True)
class Page:
    number: int
    total: int
    tickets: list[dict]


def default_window(now: datetime) -> tuple[date, date]:
    """Yesterday and today in Bangkok, so a late or skipped run loses nothing."""
    today = now.astimezone(BANGKOK).date()
    return today - timedelta(days=1), today


def fetch_page(
    session: requests.Session,
    start: date,
    end: date,
    number: int,
    *,
    attempts: int = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> Page:
    params = {
        "last_activity_start": start.isoformat(),
        "last_activity_end": end.isoformat(),
        "limit": PAGE_SIZE,
        "offset": number * PAGE_SIZE,
    }
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(API_URL, params=params, timeout=90)
            response.raise_for_status()
            return _parse(response.json(), number)
        except (requests.RequestException, ValueError, ApiError) as exc:
            if attempt == attempts:
                raise
            delay = 5 * 2 ** (attempt - 1)
            log.warning(
                "page %d, attempt %d failed (%s); retrying in %ds", number, attempt, exc, delay
            )
            sleep(delay)
    raise AssertionError("unreachable")


def _parse(body: object, number: int) -> Page:
    if not isinstance(body, dict) or body.get("status") is not True:
        raise ApiError(f"status is not true: {str(body)[:200]}")
    tickets = body.get("results")
    if not isinstance(tickets, list):
        raise ApiError("results is missing or not a list")
    # a window with no tickets reports a total of null
    return Page(number=number, total=int(body.get("total") or 0), tickets=tickets)


def iter_pages(
    session: requests.Session,
    start: date,
    end: date,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[Page]:
    """Yield pages until one comes back short.

    Results are sorted newest report first. A ticket reported while we page
    pushes every later ticket down one place, so a page can repeat the last
    tickets of the page before it (staging drops repeats), and the end of the
    list moves past the `total` the first page reported. Stopping on a short
    page instead of on `total` keeps that tail.
    """
    for number in range(MAX_PAGES):
        page = fetch_page(session, start, end, number, sleep=sleep)
        yield page
        if len(page.tickets) < PAGE_SIZE:
            return
        sleep(PAUSE)
    raise ApiError(f"more than {MAX_PAGES} pages for {start}..{end}")


def pull(
    session: requests.Session,
    start: date,
    end: date,
    out_dir: Path,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Write one window of tickets under out_dir, a day at a time, and return the run manifest."""
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    started_at = now()
    run_id = started_at.strftime(RUN_ID_FORMAT)
    pages_dir = out_dir / "tickets" / f"run={run_id}"
    pages_dir.mkdir(parents=True, exist_ok=False)

    pages = tickets = api_total = 0
    day = start
    while day <= end:
        if day > start:
            sleep(PAUSE)
        pages_before, tickets_before = pages, tickets
        for page in iter_pages(session, day, day, sleep=sleep):
            if page.number == 0:
                api_total += page.total
            fetched_at = now().isoformat()
            with gzip.open(pages_dir / f"page-{pages:04d}.jsonl.gz", "wt", encoding="utf-8") as f:
                for ticket in page.tickets:
                    row = {
                        "run_id": run_id,
                        "page": pages,
                        "fetched_at": fetched_at,
                        "ticket": {k: v for k, v in ticket.items() if k not in DROPPED_FIELDS},
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            pages += 1
            tickets += len(page.tickets)
        log.info("%s: %d tickets, %d pages", day, tickets - tickets_before, pages - pages_before)
        day += timedelta(days=1)

    manifest = {
        "run_id": run_id,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": now().isoformat(),
        "pages": pages,
        "tickets": tickets,
        "api_total": api_total,
    }
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{run_id}.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
