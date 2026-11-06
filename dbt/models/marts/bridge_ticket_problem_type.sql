{#
    A ticket can have several categories. weight splits each ticket evenly across
    them, so summing weight by category counts every ticket exactly once.
#}

with tickets as (

    select
        ticket_id,
        case when size(problem_types) = 0 then array('ไม่ระบุ') else problem_types end as problem_types
    from {{ ref('int_tickets') }}

),

exploded as (

    select
        ticket_id,
        explode(problem_types) as problem_type,
        size(problem_types) as type_count
    from tickets

)

select
    ticket_id,
    problem_type,
    1.0 / type_count as weight
from exploded
