select
    current_timestamp() as built_at,
    min(first_seen_at) as collection_started_at,
    min(reported_at) as first_reported_at,
    count(*) as tickets,
    count_if(is_open) as open_tickets,
    count_if(observed_from_start) as tickets_observed_from_start,
    sum(version_count) as versions_seen,
    sum(state_change_count) as state_changes_seen
from {{ ref('fct_ticket') }}
