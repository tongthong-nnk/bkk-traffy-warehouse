select
    snapshot_date,
    sum(open_tickets) as open_tickets,
    sum(open_30_days_or_more) as open_30_days_or_more
from {{ ref('fct_backlog_daily') }}
group by snapshot_date
