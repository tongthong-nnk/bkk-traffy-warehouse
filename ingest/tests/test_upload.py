from datetime import UTC, datetime, timedelta

import pytest
import requests

from ingest import __main__ as cli
from ingest.traffy import RUN_ID_FORMAT
from ingest.upload import latest_run, upload_dir

HOST = "https://dbc-example.cloud.databricks.com"
VOLUME = "/Volumes/workspace/traffy/landing"


class FakeResponse:
    def __init__(self, status: int, body: dict | None = None):
        self.status_code = status
        self.body = body

    def json(self) -> dict:
        return self.body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, status_for=None):
        self.status_for = status_for or {}
        self.puts: list[str] = []

    def put(self, url, params, data, headers, timeout):
        assert params == {"overwrite": "false"}
        assert headers["Authorization"] == "Bearer secret"
        self.puts.append(url)
        replies = self.status_for.get(url.rsplit("/", 1)[-1], [204])
        return FakeResponse(replies.pop(0) if len(replies) > 1 else replies[0])


def make_run(root):
    pages = root / "tickets" / "run=20261106T031700Z"
    pages.mkdir(parents=True)
    (pages / "page-0000.jsonl.gz").write_bytes(b"page 0")
    (pages / "page-0001.jsonl.gz").write_bytes(b"page 1")
    (root / "runs").mkdir()
    (root / "runs" / "20261106T031700Z.json").write_text("{}")


def test_uploads_pages_before_the_manifest(tmp_path):
    make_run(tmp_path)
    session = FakeSession()

    assert upload_dir(tmp_path, VOLUME, HOST, "secret", session=session) == 3
    assert session.puts == [
        f"{HOST}/api/2.0/fs/files{VOLUME}/tickets/run%3D20261106T031700Z/page-0000.jsonl.gz",
        f"{HOST}/api/2.0/fs/files{VOLUME}/tickets/run%3D20261106T031700Z/page-0001.jsonl.gz",
        f"{HOST}/api/2.0/fs/files{VOLUME}/runs/20261106T031700Z.json",
    ]


def test_skips_files_already_in_the_volume(tmp_path):
    make_run(tmp_path)
    session = FakeSession({"page-0000.jsonl.gz": [409]})
    assert upload_dir(tmp_path, VOLUME, HOST, "secret", session=session) == 2


def test_retries_throttling_then_fails_on_other_errors(tmp_path):
    make_run(tmp_path)
    waits = []
    session = FakeSession({"page-0000.jsonl.gz": [429, 503, 204], "page-0001.jsonl.gz": [403]})
    with pytest.raises(requests.HTTPError):
        upload_dir(tmp_path, VOLUME, HOST, "secret", session=session, sleep=waits.append)
    assert waits == [5, 10]
    assert not any(url.endswith(".json") for url in session.puts)


class FakeListing:
    """Answers a listing of the runs folder, one page per page token."""

    def __init__(self, pages: dict[str | None, dict], status: int = 200):
        self.pages = pages
        self.status = status
        self.urls: list[str] = []

    def get(self, url, params, headers, timeout):
        assert headers["Authorization"] == "Bearer secret"
        self.urls.append(url)
        return FakeResponse(self.status, self.pages.get(params.get("page_token")))


def test_latest_run_reads_every_page_of_the_listing():
    session = FakeListing(
        {
            None: {
                "contents": [
                    {"name": "20261107T180357Z.json", "is_directory": False},
                    {"name": "20261108T012745Z.json", "is_directory": False},
                ],
                "next_page_token": "page-2",
            },
            "page-2": {"contents": [{"name": "20261107T215412Z.json", "is_directory": False}]},
        }
    )
    assert latest_run(VOLUME, HOST, "secret", session=session) == "20261108T012745Z"
    assert session.urls == [f"{HOST}/api/2.0/fs/directories{VOLUME}/runs"] * 2


def test_latest_run_is_none_before_the_first_run():
    assert latest_run(VOLUME, HOST, "secret", session=FakeListing({}, status=404)) is None


@pytest.mark.parametrize(("minutes_ago", "expected"), [(None, "true"), (50, "true"), (10, "false")])
def test_due_when_the_newest_run_is_old_enough(monkeypatch, capsys, minutes_ago, expected):
    newest = None
    if minutes_ago is not None:
        newest = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).strftime(RUN_ID_FORMAT)
    monkeypatch.setattr(cli, "latest_run", lambda volume, host, token: newest)
    monkeypatch.setenv("DATABRICKS_HOST", "dbc-example.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "secret")

    assert cli.main(["due", "--minutes", "45"]) == 0
    assert capsys.readouterr().out == f"{expected}\n"
