select
    district_code,
    name_th,
    name_en
from {{ ref('bangkok_districts') }}
