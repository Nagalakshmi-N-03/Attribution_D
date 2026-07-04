import time
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st
from google.cloud import bigquery

PROJECT = "attribution-dashboard-501310"
DATASET = f"{PROJECT}.dbt_attribution"

# Palette
FOREST  = "#0F2A1D"
PINE    = "#375534"
MOSS    = "#6B9071"
SAGE    = "#AEC3B0"
MIST    = "#E3EED4"
CREAM   = "#F5F7EE"

MODEL_COLORS = {"first_click": PINE, "last_click": MOSS}

st.set_page_config(page_title="Attribution Dashboard", layout="wide")

st.markdown(
    f"""
    <style>
      .stApp {{ background-color: {CREAM}; }}

      .stApp, .stApp p, .stApp span, .stApp div,
      h1, h2, h3, h4, h5, h6,
      [data-testid="stMarkdownContainer"],
      [data-testid="stHeading"] {{ color: {FOREST} !important; }}

      /* Metric cards */
      [data-testid="stMetric"] {{
          background-color: {MIST};
          padding: 16px;
          border-radius: 8px;
          border: 1px solid {SAGE};
      }}
      [data-testid="stMetricLabel"] {{ color: {PINE} !important; }}
      [data-testid="stMetricValue"] {{ color: {FOREST} !important; }}
      [data-testid="stMetricDelta"] {{ color: {MOSS} !important; }}

      [data-testid="stCaptionContainer"], .stCaption {{ color: {MOSS} !important; }}

      /* Buttons */
      .stButton>button, .stButton>button p,
      .stButton>button span, .stButton>button div {{
          background-color: {PINE} !important;
          color: {CREAM} !important;
          border: none !important;
          border-radius: 6px !important;
          font-weight: 600 !important;
      }}
      .stButton>button:hover, .stButton>button:hover p,
      .stButton>button:hover span, .stButton>button:hover div {{
          background-color: {FOREST} !important;
          color: {CREAM} !important;
      }}
      .stButton>button:focus, .stButton>button:active {{
          background-color: {FOREST} !important;
          color: {CREAM} !important;
      }}

      /* Checkbox */
      .stCheckbox label, .stCheckbox label p {{ color: {FOREST} !important; }}

      /* Hide Altair chart toolbar (the tiny SVG icon box on charts) */
      .vega-embed summary, .vega-embed details {{ display: none !important; }}

      /* Dataframe toolbar (search/download/fullscreen) — dark pill, cream icons */
      [data-testid="stElementToolbar"] {{
          background-color: {PINE} !important;
          border-radius: 8px !important;
          padding: 2px 4px !important;
      }}
      [data-testid="stElementToolbar"] button {{
          background-color: transparent !important;
          color: {CREAM} !important;
      }}
      [data-testid="stElementToolbar"] button:hover {{
          background-color: {FOREST} !important;
      }}
      [data-testid="stElementToolbar"] svg,
      [data-testid="stElementToolbar"] svg path {{
          color: {CREAM} !important;
          stroke: {CREAM} !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def client():
    return bigquery.Client(project=PROJECT)


@st.cache_data(ttl=60)
def cached_query(sql: str) -> pd.DataFrame:
    return client().query(sql).to_dataframe()


def live_query(sql: str) -> pd.DataFrame:
    """Uncached — always fresh, for the live panel."""
    return client().query(sql).to_dataframe()


st.title("Real-Time Attribution Dashboard")
st.caption("First-click vs last-click · GA4 sample + live streamed events")

# ---- Panel 1: totals -------------------------------------------------------
totals = cached_query(f"""
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

# ---- Panel 2: channel breakdown --------------------------------------------
st.subheader("Channel breakdown")
channels = cached_query(f"""
    SELECT attribution_model, channel, COUNT(*) AS conversions
    FROM (
      SELECT * FROM `{DATASET}.fct_attribution_first_click`
      UNION ALL
      SELECT * FROM `{DATASET}.fct_attribution_last_click`
    )
    GROUP BY 1, 2
""")

bar = (
    alt.Chart(channels)
    .mark_bar()
    .encode(
        x=alt.X("channel:N", sort="-y", title=None,
                axis=alt.Axis(labelColor=FOREST, titleColor=FOREST,
                              labelFontSize=12, tickColor=SAGE)),
        y=alt.Y("conversions:Q",
                axis=alt.Axis(labelColor=FOREST, titleColor=FOREST,
                              gridColor=SAGE, labelFontSize=12)),
        color=alt.Color(
            "attribution_model:N",
            scale=alt.Scale(domain=list(MODEL_COLORS.keys()),
                            range=list(MODEL_COLORS.values())),
            legend=alt.Legend(title="Model",
                              labelColor=FOREST, titleColor=FOREST),
        ),
        xOffset="attribution_model:N",
    )
    .properties(height=320, background=CREAM)
    .configure_view(strokeWidth=0)
    .configure_axis(domainColor=FOREST)
)
st.altair_chart(bar, use_container_width=True)

# ---- Panel 3: 14-day time series -------------------------------------------
st.subheader("Conversions over time (last 14 days of dataset)")
series = cached_query(f"""
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

line = (
    alt.Chart(series)
    .mark_line(point=True, strokeWidth=2.5)
    .encode(
        x=alt.X("day:T", title=None,
                axis=alt.Axis(labelColor=FOREST, titleColor=FOREST,
                              tickColor=SAGE)),
        y=alt.Y("conversions:Q",
                axis=alt.Axis(labelColor=FOREST, titleColor=FOREST,
                              gridColor=SAGE)),
        color=alt.Color(
            "attribution_model:N",
            scale=alt.Scale(domain=list(MODEL_COLORS.keys()),
                            range=list(MODEL_COLORS.values())),
            legend=alt.Legend(title="Model",
                              labelColor=FOREST, titleColor=FOREST),
        ),
    )
    .properties(height=300, background=CREAM)
    .configure_view(strokeWidth=0)
    .configure_axis(domainColor=FOREST)
)
st.altair_chart(line, use_container_width=True)

# ---- Panel 4: live streamed events (uncached) ------------------------------
st.subheader("Live panel — recently streamed events")

col_a, col_b = st.columns([1, 3])
with col_a:
    if st.button("Refresh"):
        st.rerun()
    auto = st.checkbox("Auto-refresh (10s)", value=False)

live = live_query(f"""
    SELECT event_ts, event_name, user_pseudo_id, source, medium, purchase_revenue
    FROM `{PROJECT}.raw.streamed_events`
    ORDER BY event_ts DESC
    LIMIT 25
""")

st.dataframe(live, hide_index=True, use_container_width=True)

st.caption(
    f"Last refreshed: {datetime.now().strftime('%H:%M:%S')} · "
    f"{len(live)} events (uncached, live from BigQuery)"
)

if auto:
    time.sleep(10)
    st.rerun()