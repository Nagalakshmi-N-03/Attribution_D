import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from google.cloud import bigquery

PROJECT = "attribution-dashboard-501310"
DATASET = f"{PROJECT}.dbt_attribution"

st.set_page_config(page_title="Attribution Dashboard", layout="wide")


@st.cache_resource
def client():
    return bigquery.Client(project=PROJECT)


@st.cache_data(ttl=60)
def query(sql: str) -> pd.DataFrame:
    return client().query(sql).to_dataframe()


st.title("Real-Time Attribution Dashboard")
st.caption("First-click vs last-click · GA4 sample + live streamed events")

# ---- Panel 1: totals ----
totals = query(f"""
    SELECT attribution_model,
           COUNT(*) AS conversions,
           ROUND(SUM(revenue), 2) AS revenue
    FROM (
      SELECT * FROM `{DATASET}.fct_attribution_first_click`
      UNION ALL
      SELECT * FROM `{DATASET}.fct_attribution_last_click`
    )
    GROUP BY 1
""")

c1, c2 = st.columns(2)
for col, model in [(c1, "first_click"), (c2, "last_click")]:
    row = totals[totals.attribution_model == model].iloc[0]
    col.metric(
        label=model.replace("_", " ").title(),
        value=f"{int(row.conversions):,} conversions",
        delta=f"${row.revenue:,.0f} revenue",
    )

# ---- Panel 2: channel breakdown ----
st.subheader("Channel breakdown")
channels = query(f"""
    SELECT attribution_model, channel, COUNT(*) AS conversions
    FROM (
      SELECT * FROM `{DATASET}.fct_attribution_first_click`
      UNION ALL
      SELECT * FROM `{DATASET}.fct_attribution_last_click`
    )
    GROUP BY 1, 2
""")

chart = alt.Chart(channels).mark_bar().encode(
    x=alt.X("channel:N", sort="-y", title=None),
    y=alt.Y("conversions:Q"),
    color="attribution_model:N",
    xOffset="attribution_model:N",
).properties(height=320)
st.altair_chart(chart, use_container_width=True)

# ---- Panel 3: 14-day time series ----
st.subheader("Conversions over time (last 14 days of dataset)")
series = query(f"""
    WITH both_models AS (
      SELECT * FROM `{DATASET}.fct_attribution_first_click`
      UNION ALL
      SELECT * FROM `{DATASET}.fct_attribution_last_click`
    ),
    max_day AS (
      SELECT MAX(DATE(conversion_ts)) AS d FROM both_models
      WHERE user_pseudo_id NOT LIKE 'stream_user%'
    )
    SELECT DATE(conversion_ts) AS day,
           attribution_model,
           COUNT(*) AS conversions
    FROM both_models, max_day
    WHERE DATE(conversion_ts) BETWEEN DATE_SUB(max_day.d, INTERVAL 14 DAY) AND max_day.d
    GROUP BY 1, 2
    ORDER BY 1
""")

line = alt.Chart(series).mark_line(point=True).encode(
    x=alt.X("day:T", title=None),
    y="conversions:Q",
    color="attribution_model:N",
).properties(height=300)
st.altair_chart(line, use_container_width=True)

# ---- Panel 4: live streamed events ----
st.subheader("Live panel — recently streamed events")
if st.button("Refresh live events"):
    st.cache_data.clear()
    st.rerun()

live = query(f"""
    SELECT event_ts, event_name, user_pseudo_id, source, medium, purchase_revenue
    FROM `{PROJECT}.raw.streamed_events`
    ORDER BY event_ts DESC
    LIMIT 25
""")
st.dataframe(live, hide_index=True, use_container_width=True)
st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")