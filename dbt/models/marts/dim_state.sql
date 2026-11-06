select
    state_code,
    name_th,
    name_en,
    is_open,
    sort_order
from {{ ref('ticket_states') }}
