"""Command line entry point: `python -m ingest pull` and `python -m ingest upload`."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import requests

from ingest.traffy import default_window, pull
from ingest.upload import upload_dir

DEFAULT_VOLUME = "/Volumes/workspace/traffy/landing"
USER_AGENT = "bkk-traffy-warehouse (+https://github.com/tongthong-nnk/bkk-traffy-warehouse)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ingest")
    commands = parser.add_subparsers(dest="command", required=True)

    pull_cmd = commands.add_parser("pull", help="pull one window of tickets into local files")
    pull_cmd.add_argument(
        "--start", type=date.fromisoformat, help="first Bangkok date (default: yesterday)"
    )
    pull_cmd.add_argument(
        "--end", type=date.fromisoformat, help="last Bangkok date (default: today)"
    )
    pull_cmd.add_argument("--out", type=Path, default=Path("out"))

    upload_cmd = commands.add_parser("upload", help="copy pulled files into the landing volume")
    upload_cmd.add_argument("out", type=Path)
    upload_cmd.add_argument("--volume", default=os.environ.get("TRAFFY_VOLUME", DEFAULT_VOLUME))

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "pull":
        default_start, default_end = default_window(datetime.now(UTC))
        with requests.Session() as session:
            session.headers["User-Agent"] = USER_AGENT
            manifest = pull(session, args.start or default_start, args.end or default_end, args.out)
        print(json.dumps(manifest))
        return 0

    host, token = os.environ.get("DATABRICKS_HOST", ""), os.environ.get("DATABRICKS_TOKEN", "")
    if not host or not token:
        print("DATABRICKS_HOST and DATABRICKS_TOKEN must be set", file=sys.stderr)
        return 2
    if not host.startswith("https://"):
        host = f"https://{host}"
    uploaded = upload_dir(args.out, args.volume, host, token)
    print(f"uploaded {uploaded} files to {args.volume}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
