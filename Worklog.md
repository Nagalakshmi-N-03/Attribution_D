## Day 1 — 03 Jul
Installed gcloud CLI + dbt on Windows. Hit OAuth consent issue (cloud-platform
scope unchecked) — fixed by re-running login and ticking all scopes. dbt debug
passes. Tomorrow: staging model.

## Day-2 - 04 Jul
Built staging model — UNNEST pattern for event_params, ROW_NUMBER dedupe, md5 event_id. Added uniqueness/not-null tests, all passing.