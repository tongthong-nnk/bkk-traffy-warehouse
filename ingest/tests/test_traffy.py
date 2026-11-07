import gzip
import json
from datetime import UTC, date, datetime

import pytest
import requests

from ingest.traffy import PAGE_SIZE, ApiError, default_window, fetch_page, iter_pages, pull


def ticket(n: int) -> dict:
    """A ticket shaped like the API's, with made-up values."""
    return {
        "ticket_id": f"2026-T{n:05d}",
        "type": "ถนน",
        "org": "กรุงเทพมหานคร",
        "description": "free text written by the reporter",
        "coords": ["100.56783", "13.91739"],
        "photo_url": "https://example.com/before.jpeg",
        "after_photo": "",
        "address": "แขวงดอนเมือง เขตดอนเมือง กรุงเทพมหานคร",
        "timestamp": "2026-11-06 07:47:56.613199+00",
        "problem_type_abdul": ["ถนน"],
        "star": None,
        "count_reopen": "0",
        "note": None,
        "state": "รอรับเรื่อง",
        "last_activity": "2026-11-06 07:47:56.613199+00",
    }


def body(tickets: list[dict], total: int = 0) -> dict:
    return {"status": True, "total": total, "results": tickets, "source": "db (expire 5m)"}


class FakeResponse:
    def __init__(self, status: int = 200, payload: object = None):
        self.status_code = status
        self.payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> object:
        if isinstance(self.payload, str):
            raise ValueError("not JSON")
        return self.payload


class FakeSession:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def get(self, url, params, timeout):
        self.calls.append(params)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def no_sleep(seconds: float) -> None:
    pass


def full_page(first: int) -> FakeResponse:
    return FakeResponse(payload=body([ticket(first + i) for i in range(PAGE_SIZE)], total=1003))


def test_default_window_is_yesterday_and_today_in_bangkok():
    # 18:30 UTC on 5 November is already 01:30 on 6 November in Bangkok
    assert default_window(datetime(2026, 11, 5, 18, 30, tzinfo=UTC)) == (
        date(2026, 11, 5),
        date(2026, 11, 6),
    )


def test_pages_until_a_short_page():
    session = FakeSession(full_page(0), FakeResponse(payload=body([ticket(1000), ticket(1001)])))
    pages = list(iter_pages(session, date(2026, 11, 5), date(2026, 11, 6), sleep=no_sleep))

    assert [len(p.tickets) for p in pages] == [PAGE_SIZE, 2]
    assert [c["offset"] for c in session.calls] == [0, PAGE_SIZE]
    assert session.calls[0]["last_activity_start"] == "2026-11-05"
    assert session.calls[0]["last_activity_end"] == "2026-11-06"


def test_keeps_paging_past_the_first_total():
    # total said 1003, but tickets reported during the pull pushed the list longer
    session = FakeSession(full_page(0), full_page(1000), FakeResponse(payload=body([])))
    pages = list(iter_pages(session, date(2026, 11, 6), date(2026, 11, 6), sleep=no_sleep))
    assert len(pages) == 3


def test_an_empty_window_is_one_empty_page():
    session = FakeSession(FakeResponse(payload={"status": True, "total": None, "results": []}))
    pages = list(iter_pages(session, date(2022, 1, 1), date(2022, 1, 7), sleep=no_sleep))
    assert [(p.total, len(p.tickets)) for p in pages] == [(0, 0)]


def test_retries_errors_and_slow_downs():
    waits = []
    session = FakeSession(
        FakeResponse(status=502),
        requests.ConnectionError("reset"),
        FakeResponse(payload="<html>maintenance</html>"),
        FakeResponse(payload=body([ticket(1)])),
    )
    page = fetch_page(session, date(2026, 11, 6), date(2026, 11, 6), 0, sleep=waits.append)
    assert len(page.tickets) == 1
    assert waits == [5, 10, 20]


def test_gives_up_after_the_last_attempt():
    session = FakeSession(*[FakeResponse(status=503)] * 3)
    with pytest.raises(requests.HTTPError):
        fetch_page(session, date(2026, 11, 6), date(2026, 11, 6), 0, attempts=3, sleep=no_sleep)


def test_rejects_a_body_that_is_not_a_page():
    session = FakeSession(*[FakeResponse(payload={"status": False, "error": "bad query"})] * 2)
    with pytest.raises(ApiError):
        fetch_page(session, date(2026, 11, 6), date(2026, 11, 6), 0, attempts=2, sleep=no_sleep)


def test_pull_writes_pages_then_a_manifest(tmp_path):
    session = FakeSession(
        full_page(0),
        FakeResponse(payload=body([ticket(1000)])),
        FakeResponse(payload=body([ticket(2000)], total=1)),
    )
    clock = iter(datetime(2026, 11, 6, 3, 17, s, tzinfo=UTC) for s in range(10))

    manifest = pull(
        session,
        date(2026, 11, 5),
        date(2026, 11, 6),
        tmp_path,
        now=lambda: next(clock),
        sleep=no_sleep,
    )

    # one day at a time: two pages of the 5th, then one of the 6th
    assert [(c["last_activity_start"], c["offset"]) for c in session.calls] == [
        ("2026-11-05", 0),
        ("2026-11-05", PAGE_SIZE),
        ("2026-11-06", 0),
    ]
    assert all(c["last_activity_start"] == c["last_activity_end"] for c in session.calls)

    assert manifest["run_id"] == "20261106T031700Z"
    assert (manifest["pages"], manifest["tickets"], manifest["api_total"]) == (3, 1002, 1004)
    assert (manifest["window_start"], manifest["window_end"]) == ("2026-11-05", "2026-11-06")

    run_dir = tmp_path / "tickets" / "run=20261106T031700Z"
    assert sorted(p.name for p in run_dir.iterdir()) == [
        "page-0000.jsonl.gz",
        "page-0001.jsonl.gz",
        "page-0002.jsonl.gz",
    ]
    with gzip.open(run_dir / "page-0002.jsonl.gz", "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    assert len(rows) == 1
    assert rows[0]["run_id"] == "20261106T031700Z"
    assert rows[0]["page"] == 2
    assert rows[0]["ticket"]["ticket_id"] == "2026-T02000"
    assert rows[0]["ticket"]["address"] == "แขวงดอนเมือง เขตดอนเมือง กรุงเทพมหานคร"

    saved = json.loads((tmp_path / "runs" / "20261106T031700Z.json").read_text(encoding="utf-8"))
    assert saved == manifest


def test_pull_drops_free_text_and_photos(tmp_path):
    session = FakeSession(FakeResponse(payload=body([ticket(1)])))
    pull(session, date(2026, 11, 6), date(2026, 11, 6), tmp_path, sleep=no_sleep)

    page = next((tmp_path / "tickets").glob("run=*/page-0000.jsonl.gz"))
    with gzip.open(page, "rt", encoding="utf-8") as f:
        kept = json.loads(f.readline())["ticket"]
    assert not {"description", "note", "photo_url", "after_photo"} & kept.keys()
    assert {"ticket_id", "state", "timestamp", "last_activity", "coords"} <= kept.keys()


def test_pull_refuses_a_backwards_window(tmp_path):
    with pytest.raises(ValueError):
        pull(FakeSession(), date(2026, 11, 6), date(2026, 11, 5), tmp_path)
