with events as (

    select *
    from {{ ref('stg_ga4__events') }}
    where ga_session_id is not null

),

session_agg as (

    select
        user_pseudo_id,
        ga_session_id,
        min(event_ts) as touchpoint_ts,
        array_agg(source ignore nulls order by event_ts limit 1)[safe_offset(0)] as source,
        array_agg(medium ignore nulls order by event_ts limit 1)[safe_offset(0)] as medium,
        array_agg(campaign ignore nulls order by event_ts limit 1)[safe_offset(0)] as campaign

    from events
    group by 1, 2

)

select
    to_hex(md5(concat(user_pseudo_id, '|', cast(ga_session_id as string)))) as touchpoint_id,
    user_pseudo_id,
    ga_session_id,
    touchpoint_ts,
    coalesce(source, '(direct)') as source,
    coalesce(medium, '(none)') as medium,
    campaign,
    case
        when medium in ('cpc', 'ppc', 'paidsearch') then 'Paid Search'
        when medium = 'organic' then 'Organic Search'
        when medium like '%social%' then 'Social'
        when medium = 'email' then 'Email'
        when medium = 'referral' then 'Referral'
        when coalesce(medium, '(none)') = '(none)' then 'Direct'
        else 'Other'
    end as channel
from session_agg