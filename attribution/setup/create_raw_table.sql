CREATE SCHEMA IF NOT EXISTS `attribution-dashboard-501310.raw`
  OPTIONS (location = 'US');

CREATE TABLE IF NOT EXISTS `attribution-dashboard-501310.raw.streamed_events`
(
  event_id          STRING,
  event_date        DATE,
  event_ts          TIMESTAMP,
  event_name        STRING,
  user_pseudo_id    STRING,
  ga_session_id     INT64,
  source            STRING,
  medium            STRING,
  campaign          STRING,
  purchase_revenue  FLOAT64,
  inserted_at       TIMESTAMP
);