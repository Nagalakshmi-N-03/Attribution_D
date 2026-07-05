"""Micro-batch loads 5-20 synthetic GA4-style events into BigQuery.

Uses load jobs (free tier compatible) rather than the streaming
insert API, which the BigQuery sandbox blocks. Idempotency is
handled at the transform layer: staging dedupes on
(user_pseudo_id, event_name, event_ts) via ROW_NUMBER(), so
re-delivered events never reach the attribution models twice.
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone

from google.cloud import bigquery

PROJECT = "attribution-dashboard-501310"
TABLE = f"{PROJECT}.raw.streamed_events"
 
CHANNELS = [
    ("google", "cpc", "summer_sale"),
    ("google", "organic", None),
    ("newsletter", "email", "july_promo"),
    ("facebook", "social", "brand_push"),
    ("(direct)", "(none)", None),
]


def make_id(user, event, ts):
    return hashlib.sha256(f"{user}|{event}|{ts}".encode()).hexdigest()


def build_events(n_users=3):
    """Each user gets 1-3 sessions; only the LAST session has a
    purchase, so first-click and last-click credit differently."""
    events = []
    now = datetime.now(timezone.utc)

    for u in range(n_users):
        user = f"stream_user_{u}_{now.strftime('%H%M%S')}"
        n_sessions = random.randint(2, 3)
        t = now - timedelta(minutes=30)

        for s in range(n_sessions):
            source, medium, campaign = random.choice(CHANNELS)
            session_id = random.randint(100000, 999999)

            t += timedelta(minutes=random.randint(2, 8))
            events.append(row(user, "session_start", t, source, medium, campaign, session_id))

            t += timedelta(seconds=45)
            events.append(row(user, "page_view", t, source, medium, campaign, session_id))

            if s == n_sessions - 1:  # last session converts
                t += timedelta(minutes=2)
                revenue = round(random.uniform(20, 150), 2)
                events.append(row(user, "purchase", t, source, medium,
                                  campaign, session_id, revenue))

    return events


def row(user, event, ts, source, medium, campaign, session_id, revenue=None):
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "event_id": make_id(user, event, ts_str),
        "event_date": ts.strftime("%Y-%m-%d"),
        "event_ts": ts_str,
        "event_name": event,
        "user_pseudo_id": user,
        "ga_session_id": session_id,
        "source": source,
        "medium": medium,
        "campaign": campaign,
        "purchase_revenue": revenue,
        "inserted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    events = build_events()
    print(f"Generated {len(events)} events")

    client = bigquery.Client(project=PROJECT)

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        schema=[
            bigquery.SchemaField("event_id", "STRING"),
            bigquery.SchemaField("event_date", "DATE"),
            bigquery.SchemaField("event_ts", "TIMESTAMP"),
            bigquery.SchemaField("event_name", "STRING"),
            bigquery.SchemaField("user_pseudo_id", "STRING"),
            bigquery.SchemaField("ga_session_id", "INT64"),
            bigquery.SchemaField("source", "STRING"),
            bigquery.SchemaField("medium", "STRING"),
            bigquery.SchemaField("campaign", "STRING"),
            bigquery.SchemaField("purchase_revenue", "FLOAT64"),
            bigquery.SchemaField("inserted_at", "TIMESTAMP"),
        ],
    )

    job = client.load_table_from_json(events, TABLE, job_config=job_config)
    job.result()  # wait for completion

    print(f"Loaded {len(events)} events into {TABLE}")
    print("Queryable within seconds. Next: dbt run to materialize.")


if __name__ == "__main__":
    main()