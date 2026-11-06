{#
    The landing volume and the raw tables it is copied into. The build workflow runs

        dbt run-operation create_landing
        dbt run-operation load_landing

    before `dbt build`. Both are safe to repeat: COPY INTO remembers which files it
    has loaded, so a second load only picks up files that arrived after the first.
    The loads read from the volume root, which exists as soon as the volume does, so
    a build before the first upload loads nothing instead of failing.
#}

{% macro create_landing() %}
    {% set tickets = source('traffy', 'raw_tickets') %}
    {% set schema = tickets.database ~ '.' ~ tickets.schema %}

    {% do run_query('create schema if not exists ' ~ schema) %}
    {% do run_query('create volume if not exists ' ~ schema ~ '.landing') %}
    {% do run_query(
        'create table if not exists ' ~ tickets
        ~ ' (line string, file_path string, loaded_at timestamp)'
    ) %}
    {% do run_query(
        'create table if not exists ' ~ source('traffy', 'raw_runs')
        ~ ' (manifest string, file_path string, loaded_at timestamp)'
    ) %}
{% endmacro %}


{% macro load_landing() %}
    {% set volume = var('landing_volume') %}

    {% set copy_tickets %}
        copy into {{ source('traffy', 'raw_tickets') }}
        from (
            select
                value as line,
                _metadata.file_path as file_path,
                current_timestamp() as loaded_at
            from '{{ volume }}'
        )
        fileformat = text
        pattern = 'tickets/run=*/page-*.jsonl.gz'
    {% endset %}

    {% set copy_runs %}
        copy into {{ source('traffy', 'raw_runs') }}
        from (
            select
                value as manifest,
                _metadata.file_path as file_path,
                current_timestamp() as loaded_at
            from '{{ volume }}'
        )
        fileformat = text
        pattern = 'runs/*.json'
        format_options ('wholeText' = 'true')
    {% endset %}

    {% for table, statement in [('raw_tickets', copy_tickets), ('raw_runs', copy_runs)] %}
        {% set result = run_query(statement) %}
        {% if result.rows %}
            {% set counts = [] %}
            {% for column in result.column_names %}
                {% do counts.append(column ~ '=' ~ result.rows[0][column]) %}
            {% endfor %}
            {{ log(table ~ ': ' ~ counts | join(', '), info=true) }}
        {% endif %}
    {% endfor %}
{% endmacro %}
