{#
    Problems in the source data, counted on every build: one row per check, and
    one per unlisted state.
#}

with tickets as (

    select * from {{ ref('int_tickets') }}

),

runs as (

    select * from {{ ref('stg_traffy__runs') }}

)

select
    'ticket_without_category' as check_name,
    count_if(size(problem_types) = 0) as affected,
    count(*) as out_of,
    'tickets' as unit,
    cast(null as string) as detail
from tickets

union all

select 'address_without_district', count_if(district_code = -1), count(*), 'tickets', null
from tickets

union all

select 'activity_before_report', count_if(last_activity_at < reported_at), count(*), 'tickets', null
from tickets

union all

select 'state_not_in_seed', count(*), (select count(*) from tickets), 'tickets', state_th
from tickets
where state_code = 'other'
group by state_th

union all

-- the API's total on the first page against the tickets the run went on to fetch
select 'run_short_of_api_total', count_if(tickets < api_total), count(*), 'runs', null
from runs

union all

select
    'tickets_short_of_api_total',
    coalesce(sum(greatest(api_total - tickets, 0)), 0),
    coalesce(sum(api_total), 0),
    'tickets',
    null
from runs
