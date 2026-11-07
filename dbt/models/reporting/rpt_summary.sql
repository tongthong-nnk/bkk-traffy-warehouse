select
    current_timestamp() as built_at,
    min(first_seen_at) as collection_started_at,
    min(reported_at) as first_reported_at,
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
from {{ ref('fct_ticket') }}
