with versions as (

    select * from {{ ref('int_ticket_versions') }}

),

latest as (

    select *
    from versions
    qualify row_number() over (partition by ticket_id order by last_activity_at desc) = 1

),

history as (

    select
        ticket_id,
        min(first_seen_at) as first_seen_at,
        count(*) as version_count
    from versions
    group by ticket_id

),

districts as (

    select district_code, name_th from {{ ref('bangkok_districts') }}

)

select
    latest.ticket_id,
    latest.reported_at,
    latest.last_activity_at,
    latest.state_code,
    coalesce(districts.district_code, -1) as district_code,
    latest.district_th,
    latest.problem_types,
    latest.star,
    latest.reopen_count,
    latest.longitude,
    latest.latitude,
    history.first_seen_at,
    history.version_count
from latest
inner join history on latest.ticket_id = history.ticket_id
left join districts on latest.district_th = districts.name_th
