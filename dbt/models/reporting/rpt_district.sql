with tickets as (

    select
        district_code,
        is_open,
        case when state_code = 'finished' then hours_to_close end as hours_to_finish,
        datediff({{ bangkok_date('current_timestamp()') }}, reported_date) as age_days,
        reported_at <= current_timestamp() - interval 7 days as has_had_7_days
    from {{ ref('fct_ticket') }}

)

select
    districts.district_code,
    districts.name_th,
    districts.name_en,
    count(tickets.district_code) as tickets,
    count_if(tickets.is_open) as open_tickets,
    count_if(tickets.is_open and tickets.age_days >= 30) as open_30_days_or_more,
    count_if(tickets.has_had_7_days) as reported_7_days_ago_or_more,
    count_if(tickets.has_had_7_days and tickets.hours_to_finish <= 7 * 24) as finished_within_7_days,
    median(tickets.hours_to_finish) / 24 as median_days_to_finish
from {{ ref('dim_district') }} as districts
left join tickets on districts.district_code = tickets.district_code
group by districts.district_code, districts.name_th, districts.name_en
