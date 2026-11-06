{#
    One row per change of state that we saw happen: the ticket was in one state at
    one pull and in another at a later one. The move out of period 0 is not here,
    because we never saw the state it moved from.
#}

with periods as (

    select
        ticket_id,
        period_number,
        state_code,
        started_at,
        lag(state_code) over by_ticket as from_state_code,
        lag(started_at) over by_ticket as from_state_since,
        lag(is_start_observed) over by_ticket as is_from_state_start_observed
    from {{ ref('int_ticket_state_periods') }}
    window by_ticket as (partition by ticket_id order by period_number)

),

tickets as (

    select ticket_id, district_code from {{ ref('int_tickets') }}

)

select
    periods.ticket_id,
    periods.started_at as changed_at,
    {{ bangkok_date('periods.started_at') }} as changed_date,
    tickets.district_code,
    periods.from_state_code,
    periods.state_code as to_state_code,
    case
        when periods.is_from_state_start_observed
            then timestampdiff(SECOND, periods.from_state_since, periods.started_at) / 3600.0
    end as hours_in_from_state
from periods
inner join tickets on periods.ticket_id = tickets.ticket_id
where periods.period_number >= 2
