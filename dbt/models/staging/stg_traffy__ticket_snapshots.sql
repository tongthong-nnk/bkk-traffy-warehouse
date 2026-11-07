with lines as (

    select
        from_json(
            line,
            'run_id string, fetched_at string, ticket struct<
                ticket_id: string, state: string, `timestamp`: string, last_activity: string,
                type: string, problem_type_abdul: array<string>, org: string, address: string,
                coords: array<string>, star: string, count_reopen: string>'
        ) as parsed,
        loaded_at
    from {{ source('traffy', 'raw_tickets') }}

),

snapshots as (

    select
        parsed.run_id,
        try_cast(parsed.fetched_at as timestamp) as fetched_at,
        parsed.ticket.ticket_id,
        parsed.ticket.state as state_th,
        try_cast(parsed.ticket.`timestamp` as timestamp) as reported_at,
        try_cast(parsed.ticket.last_activity as timestamp) as last_activity_at,
        -- `type` lists categories as 'ถนน,แสงสว่าง' and problem_type_abdul repeats them as an array
        array_distinct(
            filter(
                transform(
                    coalesce(split(parsed.ticket.type, ','), parsed.ticket.problem_type_abdul),
                    category -> trim(category)
                ),
                category -> category != ''
            )
        ) as problem_types,
        parsed.ticket.org as organization,
        parsed.ticket.address,
        -- addresses end in 'แขวง… เขต… กรุงเทพมหานคร'; the word after เขต is the district.
        -- ราษฎร์บูรณะ is often misspelt with ฏ.
        nullif(
            replace(regexp_extract(parsed.ticket.address, 'เขต\\s*([^\\s,]+)', 1), 'ราษฏร์', 'ราษฎร์'),
            ''
        ) as district_th,
        try_cast(try_element_at(parsed.ticket.coords, 1) as double) as longitude,
        try_cast(try_element_at(parsed.ticket.coords, 2) as double) as latitude,
        try_cast(parsed.ticket.star as int) as star,
        try_cast(parsed.ticket.count_reopen as int) as reopen_count,
        loaded_at
    from lines

)

select * from snapshots
