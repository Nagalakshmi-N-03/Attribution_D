# Work Log

## Day 0 — 03 Jul 2026 · dataset picked, environment scoped
Picked `bigquery-public-data.ga4_obfuscated_sample_ecommerce` (Google Merchandise
Store GA4 export). Ran exploration queries in the BigQuery console:

- 17 event types total; `purchase` exists as the conversion event (~5,700 events)
- ~355k `session_start` events → good touchpoint volume
- Data range: Nov 2020 – Jan 2021 (important: "last 14 days" in the dashboard
  means last 14 days *of the dataset*, not today)
- Practiced the `UNNEST(event_params)` pattern for source/medium/campaign

Sketched pipeline shape on paper before writing any SQL:
sources → staging → touchpoints + conversions → attribution marts → dashboard.
GitHub repo created, first commit.

## Day 1 — Windows setup pain, dbt authenticated
Installed dbt-core + dbt-bigquery + gcloud CLI on Windows. Hit an OAuth consent
scope issue — first `gcloud auth application-default login` failed because the
`cloud-platform` scope checkbox was unchecked by default on the consent screen.
Re-ran with all scopes ticked → credentials saved → `dbt debug` returns
"All checks passed!". Deleted the dbt-init example models before writing
anything real.

## Day 1 — Staging model with union + dedupe
Built `stg_ga4__events`: flattens GA4's nested `event_params` and `traffic_source`
fields, prepared as a view. Chose to dedupe at this layer via
`ROW_NUMBER() PARTITION BY (user_pseudo_id, event_name, event_ts)` so everything
downstream can trust one row per real-world event. Added unique + not_null tests
on a deterministic hashed `event_id`. `dbt test`: PASS=5.

## Day 2 — Intermediate models (the real substrate)
Built three intermediate models:

- `int_touchpoints` — session-grain (one per user × session), with a channel
  CASE mapping. Chose session-level over event-level so a heavy browsing
  session doesn't over-credit itself.
- `int_conversions` — one row per `purchase` event with revenue.
- `int_conversion_paths` — the join that reconstructs each buyer's journey by
  pairing every purchase with all touchpoints from the same user in the previous
  30 days.

Sanity-checked the paths model: some conversions had 11–12 touchpoints, which is
exactly why first-click and last-click can disagree. That query confirmed the
project was worth building end-to-end.

## Day 2 — Attribution marts + revenue reconciliation test
First-click and last-click as `ROW_NUMBER()` over the shared paths model, one
line different between them (ASC vs DESC). Added a deterministic tie-breaker on
identical timestamps (smallest `touchpoint_id` for first, largest for last) —
otherwise synthetic streaming data with same-second events could give different
results on different runs.

Caught an edge case: conversions with no eligible touchpoint in the 30-day
window were silently disappearing from the union. Fixed with an
"Unattributed" fallback branch so revenue totals reconcile. Wrote a custom
singular test `assert_revenue_reconciles` — attributed revenue per model must
equal total conversion revenue to the cent. `dbt test`: PASS=12.

## Day 2 — The result that made the project real
Ran the channel comparison across both models on the batch data:

- Paid Search: 211 first-click vs 123 last-click conversions
- Referral: 1,280 first-click vs 1,759 last-click
- Organic Search: 2,241 first vs 1,777 last

Same purchases, materially different budget conclusions. This is the story the
demo hinges on.

## Day 3 — Streaming: the sandbox pivot to load jobs
Wrote `stream_events.py` — deterministic `event_id` (sha256 of user|event|ts),
generates 15-20 events across a handful of multi-session users so first-click
and last-click will visibly differ. First run failed with:

    403 Forbidden: Streaming insert is not allowed in the free tier

The BigQuery sandbox blocks the `insertAll` streaming API (which supports
`insertId` for best-effort buffer-level dedup). Pivoted to
`load_table_from_json` — micro-batch load jobs, free-tier compatible. Trade-off:
lose `insertId` dedup, so idempotency now rests *entirely* on the transform-layer
`ROW_NUMBER()` dedup — which is exactly why that layer was built first, before
touching streaming.

## Day 3 — End-to-end dedupe verified live
Streamed the same run twice on purpose. Result: 38 raw rows → 36 staged rows.
The 2 timestamp collisions were caught by the staging dedupe. Union'd streamed
events into `stg_ga4__events` and rebuilt the marts. Payoff query showed
streamed users appearing in the attribution tables with different channels
credited under first vs last click — for example:

- `stream_user_1`: first_click = Email, last_click = Direct
- `stream_user_2`: first_click = Social, last_click = Paid Search

End-to-end pipeline proven with events generated minutes earlier.

## Day 3 — Two dashboards, one pipeline
Built Looker Studio (primary, shareable link) with 4 panels — First-click and
Last-click scorecards, channel breakdown bar chart, 14-day time series,
live events table. Data freshness set to 1 minute. Fought the "report-level
chart" default that made panels appear on every page; toggled each to
page-level.

Also built Streamlit (`dashboard/app.py`) as a local realtime demo. Cached
attribution queries (60s TTL) but left the live-events query uncached so it
re-queries BigQuery on every render. Palette: forest green + cream, high
contrast. Fought Streamlit's dataframe toolbar rendering (the icons come as
SVG with `currentColor` and needed explicit styling to be visible). Added a
"streamed users only" panel that shows the pipeline change end-to-end when a
stream + `dbt build` cycle completes.

## Day 3 — Docs and delivery
Wrote README with introduction, architecture, tech stack, data set, model,
run instructions, demo video placeholder. Assumptions doc separates the
"decisions someone could reasonably disagree with" from the working code.
Sketch #2 (attribution timeline on paper: one user's journey, first-click
credits the earliest touch, last-click credits the latest). Recorded the
screencast: architecture → dbt walkthrough → live streaming demo → dashboard.
Committed final push.