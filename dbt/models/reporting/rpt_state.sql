{#
    Tickets by the state they are in now.
#}

select
    states.state_code,
    states.name_th,
    states.name_en,
    states.is_open,
    states.sort_order,
    count(*) as tickets,
    count_if(
        states.is_open
        and datediff({{ bangkok_date('current_timestamp()') }}, tickets.reported_date) >= 30
    ) as open_30_days_or_more
from {{ ref('fct_ticket') }} as tickets
inner join {{ ref('dim_state') }} as states on tickets.state_code = states.state_code
group by states.state_code, states.name_th, states.name_en, states.is_open, states.sort_order
