with first_click as (
    select round(sum(revenue), 2) as total from {{ ref('fct_attribution_first_click') }}
),

last_click as (
    select round(sum(revenue), 2) as total from {{ ref('fct_attribution_last_click') }}
),

conversions as (
    select round(sum(revenue), 2) as total from {{ ref('int_conversions') }}
)

select *
from first_click, last_click, conversions
where first_click.total != conversions.total
   or last_click.total != conversions.total