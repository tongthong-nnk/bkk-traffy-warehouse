with manifests as (

    select
        from_json(
            manifest,
            'run_id string, window_start string, window_end string, started_at string,
             finished_at string, pages int, tickets int, api_total int'
        ) as parsed,
        loaded_at
    from {{ source('traffy', 'raw_runs') }}

)

select
    parsed.run_id,
    try_cast(parsed.window_start as date) as window_start,
    try_cast(parsed.window_end as date) as window_end,
    try_cast(parsed.started_at as timestamp) as started_at,
    try_cast(parsed.finished_at as timestamp) as finished_at,
    parsed.pages,
    parsed.tickets,
    parsed.api_total,
    loaded_at
from manifests
