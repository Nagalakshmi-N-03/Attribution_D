with batch_source as (

    select
        parse_date('%Y%m%d', event_date) as event_date,
        timestamp_micros(event_timestamp) as event_ts,
        event_name,
        user_pseudo_id,

        (select value.int_value from unnest(event_params)
         where key = 'ga_session_id') as ga_session_id,

        coalesce(
            (select value.string_value from unnest(event_params) where key = 'source'),
            traffic_source.source
        ) as source,

        coalesce(
            (select value.string_value from unnest(event_params) where key = 'medium'),
            traffic_source.medium
        ) as medium,

        (select value.string_value from unnest(event_params)
         where key = 'campaign') as campaign,

        ecommerce.purchase_revenue as purchase_revenue

    from `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`

),

streamed_source as (

    select
        event_date,
        event_ts,
        event_name,
        user_pseudo_id,
        ga_session_id,
        source,
        medium,
        campaign,
        purchase_revenue

    from `attribution-dashboard-501310.raw.streamed_events`

),

unioned as (

    select * from batch_source
    union all
    select * from streamed_source

),

deduped as (

    select
        *,
        row_number() over (
            partition by user_pseudo_id, event_name, event_ts
            order by event_ts
        ) as rn
    from unioned

)

select
    to_hex(md5(concat(user_pseudo_id, '|', event_name, '|',
        cast(event_ts as string)))) as event_id,
    event_date,
    event_ts,
    event_name,
    user_pseudo_id,
    ga_session_id,
    source,
    medium,
    campaign,
    purchase_revenue
from deduped
where rn = 1




