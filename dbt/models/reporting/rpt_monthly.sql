{#
    Tickets by the month they were reported in. Finished means เสร็จสิ้น: a
    ticket closed as not relevant is closed but not finished. The 7-day share
    counts only tickets reported at least 7 days before the build, so the latest
    month is not pulled down by tickets that have not had 7 days yet.
#}

with tickets as (

    select
        date_trunc('MONTH', reported_date)::date as month_start,
        state_code = 'finished' as is_finished,
        case when state_code = 'finished' then hours_to_close end as hours_to_finish,
        problem_type_count,
        reported_at <= current_timestamp() - interval 7 days as has_had_7_days
    from {{ ref('fct_ticket') }}

)

select
    month_start,
    count(*) as reported,
    count_if(is_finished) as finished,
    count_if(has_had_7_days) as reported_7_days_ago_or_more,
    count_if(has_had_7_days and hours_to_finish <= 7 * 24) as finished_within_7_days,
    median(hours_to_finish) / 24 as median_days_to_finish,
    count_if(problem_type_count > 0) as with_category
from tickets
group by month_start
