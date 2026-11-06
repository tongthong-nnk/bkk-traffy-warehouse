with bounds as (

    select
        min({{ bangkok_date('reported_at') }}) as first_day,
        {{ bangkok_date('current_timestamp()') }} as last_day
    from {{ ref('int_tickets') }}

),

days as (

    select explode(sequence(first_day, last_day)) as date_day
    from bounds

)

select
    date_day,
    year(date_day) as year,
    quarter(date_day) as quarter,
    month(date_day) as month,
    date_format(date_day, 'MMMM') as month_name,
    day(date_day) as day_of_month,
    -- 1 is Monday, 7 is Sunday
    weekday(date_day) + 1 as day_of_week,
    date_format(date_day, 'EEEE') as day_name,
    weekday(date_day) >= 5 as is_weekend,
    date_trunc('week', date_day)::date as week_start,
    date_trunc('month', date_day)::date as month_start
from days
