{#
    Turns the versions of each ticket into the periods it spent in each state.
    Versions in a row with the same state (a note added, say) make one period.

    Before the first version we saw, the ticket was open but we cannot say in which
    state: that is period 0, state 'unknown'. Every ticket reported before
    collection began has one, and so does a ticket that changed before the first
    pull reached it.
#}

with versions as (

    select ticket_id, reported_at, last_activity_at, state_code
    from {{ ref('int_ticket_versions') }}

),

marked as (

    select
        *,
        case
            when state_code = lag(state_code) over (partition by ticket_id order by last_activity_at)
                then 0
            else 1
        end as starts_period
    from versions

),

numbered as (

    select
        *,
        sum(starts_period) over (
            partition by ticket_id
            order by last_activity_at
            rows between unbounded preceding and current row
        ) as period_number
    from marked

),

seen as (

    select
        ticket_id,
        period_number,
        state_code,
        min(last_activity_at) as started_at,
        min(reported_at) as reported_at
    from numbered
    group by ticket_id, period_number, state_code

),

not_seen as (

    select
        ticket_id,
        0 as period_number,
        'unknown' as state_code,
        reported_at as started_at,
        reported_at
    from seen
    where period_number = 1 and started_at > reported_at

),

periods as (

    select * from not_seen
    union all
    select * from seen

)

select
    ticket_id,
    period_number,
    state_code,
    started_at,
    lead(started_at) over (partition by ticket_id order by period_number) as ended_at,
    period_number = max(period_number) over (partition by ticket_id) as is_current,
    -- false when the state may have begun before we first saw the ticket in it
    not (period_number = 1 and started_at > reported_at) as is_start_observed
from periods
