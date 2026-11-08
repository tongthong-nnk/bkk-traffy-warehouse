"""Copy pulled runs into a Unity Catalog volume, and find the newest run there,
through the Databricks Files API.

The Files API needs no cluster or SQL warehouse, so the hourly upload uses none
of the Free Edition compute quota.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import requests

RETRY_STATUS = {429, 500, 502, 503, 504}

log = logging.getLogger(__name__)


def upload_dir(
    out_dir: Path,
    volume: str,
    host: str,
    token: str,
    *,
    session: requests.Session | None = None,
    attempts: int = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Upload every file under out_dir to the same relative path in the volume.

    Run manifests go last, so a manifest in the volume means every page of its
    run is there too. A file that is already in the volume, from an earlier
    attempt, is left as it is.
    Returns the number of files uploaded.
    """
    session = session or requests.Session()
    files = sorted(p for p in out_dir.rglob("*") if p.is_file())
    files.sort(key=lambda p: p.relative_to(out_dir).parts[0] == "runs")
    uploaded = 0
    for path in files:
        target = f"{volume.rstrip('/')}/{path.relative_to(out_dir).as_posix()}"
        url = f"{host.rstrip('/')}/api/2.0/fs/files{quote(target)}"
        if _put(session, url, path.read_bytes(), token, attempts=attempts, sleep=sleep):
            uploaded += 1
        else:
            log.info("already in the volume: %s", target)
    return uploaded


def latest_run(
    volume: str, host: str, token: str, *, session: requests.Session | None = None
) -> str | None:
    """The id of the newest run with a manifest in the volume, or None when there is none."""
    session = session or requests.Session()
    url = f"{host.rstrip('/')}/api/2.0/fs/directories{quote(volume.rstrip('/') + '/runs')}"
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, str] = {}
    run_ids: list[str] = []
    while True:
        response = session.get(url, params=params, headers=headers, timeout=60)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        listing = response.json()
        run_ids += [
            entry["name"].removesuffix(".json")
            for entry in listing.get("contents", [])
            if entry["name"].endswith(".json")
        ]
        if not listing.get("next_page_token"):
            return max(run_ids, default=None)
        params["page_token"] = listing["next_page_token"]


def _put(
    session: requests.Session,
    url: str,
    body: bytes,
    token: str,
    *,
    attempts: int,
    sleep: Callable[[float], None],
) -> bool:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"}
    for attempt in range(1, attempts + 1):
        try:
            response = session.put(
                url, params={"overwrite": "false"}, data=body, headers=headers, timeout=120
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == attempts:
                raise
            log.warning("upload attempt %d failed (%s)", attempt, exc)
        else:
            if response.status_code == 409:
                return False
            if response.status_code not in RETRY_STATUS or attempt == attempts:
                response.raise_for_status()
                return True
            log.warning("upload attempt %d got HTTP %d", attempt, response.status_code)
        sleep(5 * 2 ** (attempt - 1))
    raise AssertionError("unreachable")
