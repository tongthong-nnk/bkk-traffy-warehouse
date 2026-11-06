# Bangkok Traffy Fondue warehouse

People in Bangkok report broken roads, flooding, rubbish and other city problems through Traffy
Fondue, and the city's public API shows where each report stands now. It keeps no history, so this
project pulls the reports that changed every hour, keeps every version it sees, and models them
with dbt on Databricks Free Edition to measure how long the city takes to fix things, by district
and by type of problem.

Status: the hourly ingest and the dbt models are written. The dashboard comes next.

## Ingest

`python -m ingest pull` reads every report whose last activity falls on yesterday or today in
Bangkok time, 1,000 per request, and writes one gzipped JSON Lines file per page and a manifest for
the run. Reading two days on every run means a late or skipped hourly run loses nothing; the
repeats are removed later, in `int_ticket_versions`. The reporter's text, officers' notes and photo
links are dropped before anything is written, because nothing downstream needs them.

`python -m ingest upload out` copies the files into the Unity Catalog volume
`workspace.traffy.landing` through the Databricks Files API, which needs no cluster or SQL
warehouse. Manifests go last, so a run counts as landed only once its manifest is there.

The `ingest` workflow runs both every hour at minute 17. A manual run with `start` and `end`
dates loads history, one year at a time.

## Models

`dbt/` is a dbt project for Databricks SQL. The build workflow runs it every night.

| Layer | Models | What happens there |
|---|---|---|
| raw | `raw_tickets`, `raw_runs` | `COPY INTO` copies new files from the volume, one row per line, unparsed |
| staging | `stg_traffy__ticket_snapshots`, `stg_traffy__runs` | JSON parsed into typed columns; the district is read from the address |
| intermediate | `int_ticket_versions`, `int_tickets`, `int_ticket_state_periods` | repeated snapshots dropped (incrementally), then each ticket's versions turned into the time it spent in each state |
| marts | `fct_ticket`, `fct_state_change`, `fct_backlog_daily`, `dim_date`, `dim_district`, `dim_state`, `dim_problem_type`, `bridge_ticket_problem_type` | a star schema with one fact table of each kind: accumulating snapshot, transaction and periodic snapshot |

A ticket reported before collection began was seen only in its latest state. The time between its
report and that state is kept as period 0 with state `unknown`, and `fct_ticket.observed_from_start`
says which tickets were seen from the report onwards, so durations can be filtered to the ones that
were measured rather than inferred.

## Running it locally

```sh
pip install -e ".[dev]"
pytest
python -m ingest pull --out out --start 2026-11-05 --end 2026-11-05
```

## Data

Reports come from the Traffy Fondue public API for the Bangkok Metropolitan Administration
(`publicapi.traffy.in.th`). This repository publishes only counts and durations, never single
reports.
