"""Write the reporting tables to JSON files for the dashboard.

usage: python dashboard/export.py <out_dir>

Reads DATABRICKS_HOST, DATABRICKS_HTTP_PATH and DATABRICKS_TOKEN, like the dbt
profile, and writes one <table>.json per table: a list of rows, each an object
keyed by column name. Only these aggregates leave the warehouse.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from databricks import sql

SCHEMA = "workspace.traffy_reporting"
TABLES = (
    "rpt_summary",
    "rpt_monthly",
    "rpt_backlog_daily",
    "rpt_district",
    "rpt_state",
    "rpt_problem_type",
    "rpt_data_quality",
)


def to_json(value: object) -> object:
    # the session runs in UTC, so timestamps come back as naive UTC times
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (
        sql.connect(
            server_hostname=os.environ["DATABRICKS_HOST"],
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            access_token=os.environ["DATABRICKS_TOKEN"],
            session_configuration={"TIMEZONE": "UTC"},
        ) as connection,
        connection.cursor() as cursor,
    ):
        for table in TABLES:
            cursor.execute(f"select * from {SCHEMA}.{table} order by 1")
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, map(to_json, row), strict=True)) for row in cursor.fetchall()]
            path = out_dir / f"{table}.json"
            path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), "utf-8")
            print(f"{path}: {len(rows)} rows")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python dashboard/export.py <out_dir>")
    main(Path(sys.argv[1]))
