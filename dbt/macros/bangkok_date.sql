{#
    The Bangkok calendar date of a timestamp. Bangkok is UTC+7 all year.
    Assumes the session time zone is UTC, which profiles.yml sets.
#}
{% macro bangkok_date(timestamp) -%}
    to_date(from_utc_timestamp({{ timestamp }}, 'Asia/Bangkok'))
{%- endmacro %}
