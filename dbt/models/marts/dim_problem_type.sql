with used as (

    select distinct problem_type
    from {{ ref('bridge_ticket_problem_type') }}

),

labels as (

    select problem_type, name_en
    from {{ ref('problem_types') }}

)

select
    used.problem_type,
    coalesce(labels.name_en, used.problem_type) as name_en
from used
left join labels on used.problem_type = labels.problem_type
