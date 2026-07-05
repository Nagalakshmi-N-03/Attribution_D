SELECT attribution_model, user_pseudo_id, channel, revenue, conversion_ts
FROM (
  SELECT * FROM `attribution-dashboard-501310.dbt_attribution.fct_attribution_first_click`
  UNION ALL
  SELECT * FROM `attribution-dashboard-501310.dbt_attribution.fct_attribution_last_click`
)
WHERE user_pseudo_id LIKE 'stream_user%'
ORDER BY user_pseudo_id, attribution_model;




