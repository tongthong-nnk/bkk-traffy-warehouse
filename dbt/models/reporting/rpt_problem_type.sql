{#
    A ticket with two categories counts as half a ticket in each, so `tickets`
    adds up to the number of tickets. The median is over every finished ticket in
    the category.
#}

select
    types.problem_type,
    types.name_en,
    sum(bridge.weight) as tickets,
    sum(case when tickets.is_open then bridge.weight else 0 end) as open_tickets,
    median(case when tickets.state_code = 'finished' then tickets.hours_to_close end) / 24
        as median_days_to_finish
from {{ ref('bridge_ticket_problem_type') }} as bridge
inner join {{ ref('fct_ticket') }} as tickets on bridge.ticket_id = tickets.ticket_id
inner join {{ ref('dim_problem_type') }} as types on bridge.problem_type = types.problem_type
group by types.problem_type, types.name_en
