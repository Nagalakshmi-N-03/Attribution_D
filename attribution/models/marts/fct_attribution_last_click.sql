with paths as (

    select
        *,
        row_number() over (
            partition by conversion_id
            order by touchpoint_ts desc, touchpoint_id desc
        ) as touch_rank
    from {{ ref('int_conversion_paths') }}

),

attributed as (

    select
        conversion_id,
        user_pseudo_id,
        conversion_ts,
        revenue,
        touchpoint_id,
        touchpoint_ts,
        source,
        medium,
        campaign,
        channel,
        'last_click' as attribution_model
    from paths
    where touch_rank = 1

),

unattributed as (

    select
        c.conversion_id,
        c.user_pseudo_id,
        c.conversion_ts,
        c.revenue,
        cast(null as string) as touchpoint_id,
        cast(null as timestamp) as touchpoint_ts,
        cast(null as string) as source,
        cast(null as string) as medium,
        cast(null as string) as campaign,
        'Unattributed' as channel,
        'last_click' as attribution_model
    from {{ ref('int_conversions') }} c
    left join attributed a
        on c.conversion_id = a.conversion_id
    where a.conversion_id is null

)

select * from attributed
union all
select * from unattributed