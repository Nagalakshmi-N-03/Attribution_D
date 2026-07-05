select
    event_id as conversion_id,
    user_pseudo_id,
    event_ts as conversion_ts,
    coalesce(purchase_revenue, 0) as revenue
from {{ ref('stg_ga4__events') }}
where event_name = 'purchase'