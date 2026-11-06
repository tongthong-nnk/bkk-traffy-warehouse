{#
    Open tickets at the end of each Bangkok day, by district and state (a periodic
    snapshot). A period counts on every day from the one it started on up to the
    day before the one it ended on, so a ticket reported and closed on the same day
    never shows up.
#}

{%- set end_date = var('backlog_end_date') -%}
{%- if end_date -%}
    {%- set last_day = "date'" ~ end_date ~ "'" -%}
{%- else -%}
    {%- set last_day = "date_sub(" ~ bangkok_date('current_timestamp()') ~ ", 1)" -%}
{%- endif %}

with open_periods as (

    select
        periods.ticket_id,
        periods.state_code,
        tickets.district_code,
        {{ bangkok_date('tickets.reported_at') }} as reported_date,
        {{ bangkok_date('periods.started_at') }} as first_day,
        least(
            coalesce(date_sub({{ bangkok_date('periods.ended_at') }}, 1), {{ last_day }}),
            {{ last_day }}
        ) as last_day
    from {{ ref('int_ticket_state_periods') }} as periods
    inner join {{ ref('ticket_states') }} as states on periods.state_code = states.state_code
    inner join {{ ref('int_tickets') }} as tickets on periods.ticket_id = tickets.ticket_id
    where states.is_open

),

ticket_days as (

    select
        ticket_id,
        state_code,
        district_code,
        reported_date,
        explode(sequence(first_day, last_day)) as snapshot_date
    from open_periods
    where last_day >= first_day

)

select
    snapshot_date,
    district_code,
    state_code,
    count(*) as open_tickets,
    count_if(datediff(snapshot_date, reported_date) >= 30) as open_30_days_or_more
from ticket_days
group by snapshot_date, district_code, state_code
