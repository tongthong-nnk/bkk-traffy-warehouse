import pytest
import requests

from ingest.upload import upload_dir

HOST = "https://dbc-example.cloud.databricks.com"
VOLUME = "/Volumes/workspace/traffy/landing"


class FakeResponse:
    def __init__(self, status: int):
        self.status_code = status

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
