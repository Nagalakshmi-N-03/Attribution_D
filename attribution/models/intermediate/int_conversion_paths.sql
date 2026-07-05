with conversions as (

    select * from {{ ref('int_conversions') }}

),

touchpoints as (

    select * from {{ ref('int_touchpoints') }}

)

select
    c.conversion_id,
    c.user_pseudo_id,
    c.conversion_ts,
    c.revenue,
    t.touchpoint_id,
    t.touchpoint_ts,
    t.source,
    t.medium,
    t.campaign,
    t.channel
from conversions c
inner join touchpoints t
    on c.user_pseudo_id = t.user_pseudo_id
    and t.touchpoint_ts <= c.conversion_ts
    and t.touchpoint_ts >= timestamp_sub(c.conversion_ts, interval 30 day)





    