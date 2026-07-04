with source as (

    select *
    from `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`

),

flattened as (

    select
        parse_date('%Y%m%d', event_date) as event_date,
        timestamp_micros(event_timestamp) as event_ts,
        event_name,
        user_pseudo_id,

        (select value.int_value from unnest(event_params)
         where key = 'ga_session_id') as ga_session_id,

        (select value.string_value from unnest(event_params)
         where key = 'source') as event_source,

        (select value.string_value from unnest(event_params)
         where key = 'medium') as event_medium,

        (select value.string_value from unnest(event_params)
         where key = 'campaign') as event_campaign,

        traffic_source.source as user_source,
        traffic_source.medium as user_medium,

        ecommerce.purchase_revenue as purchase_revenue

    from source

),

deduped as (

    select
        *,
        row_number() over (
            partition by user_pseudo_id, event_name, event_ts
            order by event_ts
        ) as rn
    from flattened

)

select
    to_hex(md5(concat(user_pseudo_id, '|', event_name, '|',
        cast(event_ts as string)))) as event_id,
    event_date,
    event_ts,
    event_name,
    user_pseudo_id,
    ga_session_id,
    coalesce(event_source, user_source) as source,
    coalesce(event_medium, user_medium) as medium,
    event_campaign as campaign,
    purchase_revenue
from deduped
where rn = 1