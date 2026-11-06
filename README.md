# Bangkok Traffy Fondue warehouse

People in Bangkok report broken roads, flooding, rubbish and other city problems through Traffy
Fondue, and the city's public API shows where each report stands now. It keeps no history, so this
project pulls the reports that changed every hour, keeps every version it sees, and models them
with dbt on Databricks Free Edition to measure how long the city takes to fix things, by district
and by type of problem.

Status: the hourly ingest is in place. The dbt models, tests and the dashboard come next.

## Ingest

`python -m ingest pull` reads every report whose last activity falls on yesterday or today in
Bangkok time, 1,000 per request, and writes one gzipped JSON Lines file per page and a manifest for
the run. Reading two days on every run means a late or skipped hourly run loses nothing; the
repeated versions are removed later, in staging. The reporter's text, officers' notes and photo
links are dropped before anything is written, because nothing downstream needs them.

`python -m ingest upload out` copies the files into the Unity Catalog volume
`workspace.traffy.landing` through the Databricks Files API, which needs no cluster or SQL
warehouse. Manifests go last, so a run counts as landed only once its manifest is there.

The `ingest` workflow runs both every hour at minute 17. A manual run with `start` and `end`
dates loads history, one year at a time.

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
