{% test unique_combination(model, columns) %}

select {{ columns | join(', ') }}, count(*) as rows_with_this_key
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
