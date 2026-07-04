# Real-Time Attribution Pipeline

## Introduction

This project builds a near-real-time marketing attribution pipeline that answers one business question: when a customer buys something, which marketing channel deserves the credit?

Same purchase → two different answers depending on the model:
- **First-click** credits the channel that introduced the customer.
- **Last-click** credits the channel that closed the sale.

Both models run on the same GA4 event data and produce measurably different results — which is exactly why marketing teams need to see them side by side before deciding where to spend their budget. From this pipeline's own output:

| Channel | First-click conversions | Last-click conversions |
|---|---:|---:|
| Organic Search | 2,241 | 1,777 |
| Referral | 1,280 | 1,759 |
| Paid Search | 211 | 123 |
| Email | 6 | 12 |

The pipeline processes ~3 months of GA4 batch data (5,698 purchases) plus live streamed events, computes both models in dbt on BigQuery, and displays the results in two dashboards.

---

## How it works

1. **Sources** — the GA4 public dataset (batch, historical) and a Python streaming producer that pushes synthetic events into BigQuery every time it runs. Both land in the same shape.
2. **Staging (`stg_ga4__events`)** — flattens GA4's nested `event_params`, unions batch + streamed data, and deduplicates on `(user_pseudo_id, event_name, event_ts)` so everything downstream can trust one row per real-world event.
3. **Touchpoints & conversions** — extracts one touchpoint per (user, session) with its source/medium/campaign, and one conversion per `purchase` event with its revenue.
4. **Conversion paths (`int_conversion_paths`)** — for every purchase, joins all touchpoints from the same user within the previous 30 days. This reconstructs each customer's journey and is the shared foundation both attribution models sit on top of.
5. **Attribution marts** — first-click uses `ROW_NUMBER() ORDER BY touchpoint_ts ASC`, last-click uses `DESC`. Rank 1 wins 100% of the credit. Deterministic tie-breakers handle identical timestamps. Conversions with no eligible touchpoint fall back to "Unattributed" so revenue reconciles.
6. **Dashboards** — read the final tables. The live panel reads the raw streaming table directly (seconds of latency); attribution numbers refresh on the next `dbt build`.

The key correctness guarantee is a custom singular test (`assert_revenue_reconciles`) that fails if total attributed revenue under either model doesn't exactly equal total conversion revenue. It has always passed — meaning no purchase is ever dropped or double-counted.

![End-to-end pipeline flow](docs/images/pipeline_flow.png)


---


## Architecture
![Architecture](docs/images/architecture.png)

## Model
![Data model](docs/images/data_model.png)



---

## Tech Stack

| Layer | Tool |
|---|---|
| Storage + compute | BigQuery (free-tier sandbox) |
| Transformation | dbt-core 1.11 + dbt-bigquery 1.11 |
| Streaming ingestion | Python 3.11 + `google-cloud-bigquery` (load jobs) |
| Idempotency | Deterministic sha256 event_id + `ROW_NUMBER()` staging dedupe |
| Primary dashboard | Looker Studio (shareable link, 1-minute freshness) |
| Local realtime dashboard | Streamlit + Altair |
| Authentication | gcloud CLI application-default credentials |
| Testing | dbt generic tests + custom singular test for revenue reconciliation |
| Version control | Git + GitHub, incremental commits |
| Suggested prod orchestration | Cloud Scheduler + Cloud Run calling `dbt build` every 5–15 min |

---

## Data set used

**Primary source (batch):** `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`

The Google Merchandise Store GA4 export, obfuscated and hosted publicly by Google in BigQuery. Nov 1 2020 – Jan 31 2021, sharded as daily tables (`events_YYYYMMDD`). Roughly:
- 1.35M `page_view` events
- 354k `session_start` events
- 5,698 `purchase` events with revenue
- 17 distinct event types total

No download required — the dataset is queried directly from BigQuery. Free-tier quota easily covers full-table scans (dataset is only a few GB).

**Streaming source:** `attribution-dashboard-501310.raw.streamed_events` — an append-only landing table written by `streaming/stream_events.py`. Same flattened shape as the staging layer expects, so the transformation code doesn't care which source a given row came from.

**dbt output dataset:** `attribution-dashboard-501310.dbt_attribution`

---

## Model

### Staging layer
- **`stg_ga4__events`** — one row per event. Flattens GA4's nested `event_params` and `traffic_source` fields, unions batch + streamed sources, deduplicates on `(user_pseudo_id, event_name, event_ts)` using `ROW_NUMBER()`. Materialized as a view.

### Intermediate layer
- **`int_touchpoints`** — one row per (user_pseudo_id, ga_session_id). Picks up the source/medium/campaign from the first event in the session, back-filling from later events if the first one is missing UTM params. Adds a channel grouping (Paid Search / Organic Search / Social / Email / Direct / Referral / Other).
- **`int_conversions`** — one row per `purchase` event with user_pseudo_id, timestamp, and revenue.
- **`int_conversion_paths`** — for every conversion, joins all eligible touchpoints (same user, touchpoint at or before conversion, within 30 days). The fan-out this creates is the substrate both attribution models sit on.

### Attribution marts
- **`fct_attribution_first_click`** — 100% credit to the earliest touchpoint in the path. `ROW_NUMBER() ORDER BY touchpoint_ts ASC, touchpoint_id ASC` — the second sort key is the deterministic tie-breaker.
- **`fct_attribution_last_click`** — same structure but `ORDER BY touchpoint_ts DESC, touchpoint_id DESC`.

Both marts also emit an "Unattributed" row for any conversion with no eligible touchpoint in the lookback window, so revenue totals always reconcile.

### Tests (12 total, all passing)
- **Generic tests:** `unique` and `not_null` on primary keys across staging and marts.
- **Custom singular test `assert_revenue_reconciles`:** total attributed revenue under each model must exactly equal total conversion revenue. This is the highest-signal canary for the whole pipeline.

### Key assumptions (see `docs/assumptions_edge_cases.md` for the full page)
- Conversion event = `purchase` (var-driven, one place to swap)
- Lookback window = 30 days
- Identity = `user_pseudo_id` (no cross-device stitching — public sample has no reliable `user_id`)
- Touchpoint = first event of a session, not every event
- Session key is always `(user_pseudo_id, ga_session_id)` together — GA4's session id is only unique per user

---

## Run instruction

### 1. Authenticate to GCP
```powershell
gcloud auth application-default login
```
In the browser, tick all OAuth scope checkboxes including `cloud-platform` before clicking Continue.

### 2. Create the raw landing table (one time)
Open `setup/create_raw_table.sql` in the BigQuery console and run it. Creates the `raw` dataset and the `streamed_events` table.

### 3. Build dbt models
```powershell
cd attribution
dbt debug        # confirms BigQuery connection
dbt build        # runs models + tests in dependency order
```
Expected result: **6 models, 12 tests, all PASS**.

### 4. Stream sample events
```powershell
cd streaming
pip install google-cloud-bigquery
python stream_events.py
```
Loads ~19 synthetic GA4-shaped events across multi-session users so first-click and last-click will visibly disagree.

### 5. Rebuild marts to include streamed events
```powershell
cd ..
dbt build
```

### 6. View dashboards
**Looker Studio (shareable):** open the link at the top of this README.

**Streamlit (local realtime demo):**
```powershell
cd dashboard
pip install streamlit pandas altair db-dtypes google-cloud-bigquery
streamlit run app.py
```
Open `http://localhost:8501`.

### 7. Demonstrate end-to-end flow
1. Note the "streamed users only" numbers in the Streamlit dashboard.
2. Run `python streaming\stream_events.py` again.
3. Run `dbt build`.
4. Refresh the Streamlit tab — numbers should change.

### Dedupe / idempotency (verified live)
Ran the streaming loader twice on purpose → 38 raw rows → 36 staged rows. Two exact-timestamp collisions were caught by the transform-layer dedupe. The attribution tables never saw duplicates.

### Expected latency
| Stage | Latency |
|---|---|
| Event loaded → queryable in `raw.streamed_events` | seconds |
| `raw.streamed_events` → attribution marts | next `dbt build` (5–15 min schedule in prod) |
| Dashboard live panel | seconds (reads raw table directly) |
| Dashboard attribution totals | matches dbt schedule |

### Monitoring suggestions
- `dbt source freshness` against `raw.streamed_events` — warn at 15 min stale, error at 60 min
- Alert on any `dbt build` non-zero exit
- Row-count trend on `raw.streamed_events`
- GCP budget alert on the project

### Cost notes
BigQuery sandbox (free tier) covers everything here. Dataset is a few GB, well within the 1 TB/month query allowance. Streaming inserts (paid) not used — the sandbox blocks them, so the pipeline uses free load jobs and relies on the transform-layer dedupe.

---

## Demo video

_paste your screencast link here (Loom / YouTube unlisted / Google Drive)_

The 5–8 minute walkthrough covers: architecture on the whiteboard sketch, dbt models in VS Code, `dbt build` running green with all tests passing, the payoff query showing first-click and last-click crediting different channels for the same streamed purchase, the streaming script producing new events, and both dashboards updating end-to-end.

---

## Author

**Nagalakshmi N**
- GitHub: https://github.com/Nagalakshmi-N-03
- Email: nagalakshmi.n.23003@gmail.com
- LinkedIn: https://www.linkedin.com/in/nagalakshmi-n-5a7672268/

Built as part of the CustomerLabs Data Engineer candidate assessment.