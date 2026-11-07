{#
    One row of headline numbers. The API keeps no ticket whose last activity is
    older than `earliest_activity_date`, so a month that starts before that day
    is missing tickets, and the dashboard's charts start at `first_complete_month`.
#}

with tickets as (

    select
        *,
        {{ bangkok_date('last_activity_at') }} as last_activity_date
    from {{ ref('fct_ticket') }}

)

select
    current_timestamp() as built_at,
    min(first_seen_at) as collection_started_at,
    min(reported_at) as first_reported_at,
    min(last_activity_date) as earliest_activity_date,
    case
        when day(min(last_activity_date)) = 1 then min(last_activity_date)
        else add_months(trunc(min(last_activity_date), 'MM'), 1)
    end as first_complete_month,
    count(*) as tickets,
    count_if(is_open) as open_tickets,
    count_if(observed_from_start) as tickets_observed_from_start,
    sum(version_count) as versions_seen,
    sum(state_change_count) as state_changes_seen,
    median(
        case
            when state_code = 'finished' and reported_at >= current_timestamp() - interval 365 days
                then hours_to_close
        end
    ) / 24 as median_days_to_finish_past_year
from tickets
