{#
    The landing volume and the raw tables it is copied into. The build workflow runs

        dbt run-operation create_landing
        dbt run-operation load_landing

    before `dbt build`. Both are safe to repeat: COPY INTO remembers which files it
    has loaded, so a second load only picks up files that arrived after the first.
    COPY INTO fails when its path matches no file, so a folder the ingest has not
    written yet is skipped, and a build before the first upload loads nothing.
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
    {% set folders = [] %}
    {% for row in run_query("list '" ~ volume ~ "'").rows %}
        {% do folders.append(row['name'].rstrip('/')) %}
    {% endfor %}

    {% set copy_tickets %}
        copy into {{ source('traffy', 'raw_tickets') }}
        from (
            select
                value as line,
                _metadata.file_path as file_path,
                current_timestamp() as loaded_at
            from '{{ volume }}/tickets'
        )
        fileformat = text
        pattern = 'run=*/page-*.jsonl.gz'
    {% endset %}

    {# A manifest is one JSON document, so each file is read whole. #}
    {% set copy_runs %}
        copy into {{ source('traffy', 'raw_runs') }}
        from (
            select
                value as manifest,
                _metadata.file_path as file_path,
                current_timestamp() as loaded_at
            from '{{ volume }}/runs'
        )
        fileformat = text
        pattern = '*.json'
        format_options ('wholeText' = 'true')
    {% endset %}

    {% for table, folder, statement in [('raw_tickets', 'tickets', copy_tickets), ('raw_runs', 'runs', copy_runs)] %}
        {% if folder in folders %}
            {% set result = run_query(statement) %}
            {% set counts = [] %}
            {% for column in result.column_names %}
                {% do counts.append(column ~ '=' ~ result.rows[0][column]) %}
            {% endfor %}
            {{ log(table ~ ': ' ~ counts | join(', '), info=true) }}
        {% else %}
            {{ log(table ~ ': nothing in ' ~ volume ~ '/' ~ folder ~ ' yet', info=true) }}
        {% endif %}
    {% endfor %}
{% endmacro %}
