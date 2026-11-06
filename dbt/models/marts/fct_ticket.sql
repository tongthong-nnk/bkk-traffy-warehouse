{#
    One row per ticket, updated as the ticket moves along (an accumulating snapshot).
#}

with tickets as (

    select * from {{ ref('int_tickets') }}

),

periods as (

    select * from {{ ref('int_ticket_state_periods') }}

),

states as (

    select state_code, is_open from {{ ref('ticket_states') }}

),

milestones as (

    select
        ticket_id,
        -- no period 0: we saw the ticket as it was reported
        min(period_number) = 1 as observed_from_start,
        max(case when period_number = 1 then ended_at end) as first_change_at,
        max_by(started_at, period_number) as current_state_since,
        max_by(is_start_observed, period_number) as is_current_state_start_observed,
        count_if(period_number >= 2) as state_change_count
    from periods
    group by ticket_id

),

joined as (

    select
        tickets.ticket_id,
        tickets.reported_at,
        tickets.district_code,
        tickets.state_code,
        states.is_open,
        milestones.observed_from_start,
        case when milestones.observed_from_start then milestones.first_change_at end as first_response_at,
        case when not states.is_open then milestones.current_state_since end as closed_at,
        case when not states.is_open then milestones.is_current_state_start_observed end as is_close_observed,
        tickets.reopen_count,
        tickets.star,
        size(tickets.problem_types) as problem_type_count,
        tickets.version_count,
        milestones.state_change_count,
        tickets.first_seen_at,
        tickets.last_activity_at
    from tickets
    inner join milestones on tickets.ticket_id = milestones.ticket_id
    inner join states on tickets.state_code = states.state_code

)

select
    ticket_id,
    reported_at,
    {{ bangkok_date('reported_at') }} as reported_date,
    district_code,
    state_code,
    is_open,
    observed_from_start,
    first_response_at,
    timestampdiff(SECOND, reported_at, first_response_at) / 3600.0 as hours_to_first_response,
    closed_at,
    {{ bangkok_date('closed_at') }} as closed_date,
    timestampdiff(SECOND, reported_at, closed_at) / 3600.0 as hours_to_close,
    is_close_observed,
    reopen_count,
    star,
    problem_type_count,
    version_count,
    state_change_count,
    first_seen_at,
    last_activity_at
from joined
