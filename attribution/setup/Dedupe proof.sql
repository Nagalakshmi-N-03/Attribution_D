SELECT COUNT(*) AS raw_rows FROM `attribution-dashboard-501310.raw.streamed_events`;
SELECT COUNT(*) AS staged_rows
FROM `attribution-dashboard-501310.dbt_attribution.stg_ga4__events`
WHERE user_pseudo_id LIKE 'stream_user%';




