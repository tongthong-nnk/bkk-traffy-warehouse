{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['ticket_id', 'last_activity_at'],
    )
}}

{#
    A version is a ticket as it stood after one activity, so ticket_id and
    last_activity_at identify it. Most snapshots in a batch repeat a version we
    already have; for those the merge only moves last_seen_at forward.
#}

with new_snapshots as (

    select *
    from {{ ref('stg_traffy__ticket_snapshots') }}
    {% if is_incremental() %}
    where loaded_at > (select max(loaded_at) from {{ this }})
    {% endif %}

),

sightings as (

    select
        ticket_id,
        last_activity_at,
        reported_at,
        state_code,
        problem_types,
        address,
        district_th,
        longitude,
        latitude,
        star,
        reopen_count,
        fetched_at as first_seen_at,
        fetched_at as last_seen_at,
        loaded_at
    from new_snapshots

    {% if is_incremental() %}

    union all

    -- what we already know about versions seen again, so the merge keeps their first_seen_at
    select
        known.ticket_id,
        known.last_activity_at,
        known.reported_at,
        known.state_code,
        known.problem_types,
        known.address,
        known.district_th,
        known.longitude,
        known.latitude,
        known.star,
        known.reopen_count,
        known.first_seen_at,
        known.last_seen_at,
        known.loaded_at
    from {{ this }} as known
    inner join (select distinct ticket_id, last_activity_at from new_snapshots) as seen_again
        on known.ticket_id = seen_again.ticket_id
        and known.last_activity_at = seen_again.last_activity_at

    {% endif %}

)

-- if a field changes without a new activity, the latest sighting wins
select
    ticket_id,
    last_activity_at,
    max_by(reported_at, last_seen_at) as reported_at,
    max_by(state_code, last_seen_at) as state_code,
    max_by(problem_types, last_seen_at) as problem_types,
    max_by(address, last_seen_at) as address,
    max_by(district_th, last_seen_at) as district_th,
    max_by(longitude, last_seen_at) as longitude,
    max_by(latitude, last_seen_at) as latitude,
    max_by(star, last_seen_at) as star,
    max_by(reopen_count, last_seen_at) as reopen_count,
    min(first_seen_at) as first_seen_at,
    max(last_seen_at) as last_seen_at,
    max(loaded_at) as loaded_at
from sightings
group by ticket_id, last_activity_at
