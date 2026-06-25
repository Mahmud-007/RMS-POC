"""RMS dashboard — Streamlit.

Pages currently implemented:
    - Dataset Explorer        (live)
    - Validation (last 28d)   (live)
    - Today / Tomorrow        (stub)
    - Order Sheet             (stub)
    - Corrections             (stub)
    - Model Health            (stub)
    - Coefficient Inspector   (stub)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable when Streamlit launches this file directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import sqlite3
from datetime import date, datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.data.generator import REGIME_SHIFT_DAY, START_DATE
from app.eval.holdout import predict_holdout_all_channels, summary_metrics

DB_PATH = Path("artifacts/rms.db")
CHANNELS = ("dine_in", "delivery", "takeaway")
CHANNEL_COLORS = {"dine_in": "#1f77b4", "delivery": "#ff7f0e", "takeaway": "#2ca02c"}
REGIME_SHIFT_DATE = (START_DATE + pd.Timedelta(days=REGIME_SHIFT_DAY)).strftime("%Y-%m-%d")

st.set_page_config(page_title="RMS", layout="wide")


# --------------------------------------------------------------------------------------
# Cached data loaders
# --------------------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_observations() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT ts, channel, covers FROM observations", conn)
    df["ts"] = pd.to_datetime(df["ts"])
    df["date"] = df["ts"].dt.date
    df["hour"] = df["ts"].dt.hour
    df["dow"] = df["ts"].dt.dayofweek
    return df


@st.cache_data(show_spinner=False)
def load_weather() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT date, hour, temp, rain_mm, condition FROM weather", conn)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


@st.cache_data(show_spinner=False)
def load_events() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT date, type, severity FROM events", conn)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


@st.cache_data(show_spinner=True)
def load_holdout() -> pd.DataFrame:
    df = predict_holdout_all_channels()
    df["date"] = df["ts"].dt.date
    df["hour"] = df["ts"].dt.hour
    return df


# --------------------------------------------------------------------------------------
# Dataset Explorer
# --------------------------------------------------------------------------------------

def page_dataset_explorer() -> None:
    st.title("Dataset Explorer")
    st.caption(f"Synthetic dataset. Regime shift on **{REGIME_SHIFT_DATE}** — delivery volume doubles from this day onward.")

    obs = load_observations()
    weather = load_weather()
    events = load_events()

    min_d, max_d = obs["date"].min(), obs["date"].max()
    col1, col2 = st.columns([3, 1])
    with col1:
        date_range = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    with col2:
        selected_channels = st.multiselect("Channels", list(CHANNELS), default=list(CHANNELS))

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = min_d, max_d

    obs_f = obs[(obs["date"] >= start_d) & (obs["date"] <= end_d) & (obs["channel"].isin(selected_channels))]

    st.metric("Total observations in window", f"{len(obs_f):,}")

    # Daily totals per channel
    st.subheader("Daily covers per channel")
    daily = obs_f.groupby(["date", "channel"], as_index=False)["covers"].sum()
    fig = px.line(
        daily, x="date", y="covers", color="channel",
        color_discrete_map=CHANNEL_COLORS,
        labels={"covers": "Daily covers"},
    )
    regime_d = pd.to_datetime(REGIME_SHIFT_DATE).date()
    if start_d <= regime_d <= end_d:
        # Use add_shape + add_annotation separately. add_vline(annotation_text=...) trips
        # a Plotly bug where annotation_params_for_line tries float(sum([date])) -> TypeError.
        fig.add_shape(type="line", x0=regime_d, x1=regime_d, xref="x",
                      y0=0, y1=1, yref="paper",
                      line=dict(color="red", dash="dash", width=2))
        fig.add_annotation(x=regime_d, y=1.0, xref="x", yref="paper",
                           text="regime shift", showarrow=False,
                           xanchor="left", yanchor="bottom", font=dict(color="red"))
    # Events overlay
    ev_window = events[(events["date"] >= start_d) & (events["date"] <= end_d)]
    for _, row in ev_window.iterrows():
        color = {"holiday": "purple", "local_event": "gold", "promo": "lightblue"}.get(row["type"], "gray")
        fig.add_shape(type="line", x0=row["date"], x1=row["date"], xref="x",
                      y0=0, y1=1, yref="paper",
                      line=dict(color=color, dash="dot", width=1), opacity=0.35)
    fig.update_layout(height=380, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Vertical dotted lines: purple = holiday, gold = local event, light-blue = promo. Red dashed = regime shift.")

    # Hour-of-day curve per channel
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Average covers by hour")
        hourly = obs_f.groupby(["hour", "channel"], as_index=False)["covers"].mean()
        fig2 = px.line(hourly, x="hour", y="covers", color="channel",
                       color_discrete_map=CHANNEL_COLORS, markers=True)
        fig2.update_layout(height=320, margin=dict(t=30, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    with col_b:
        st.subheader("Average covers by day of week")
        dow_df = obs_f.groupby(["dow", "channel"], as_index=False)["covers"].mean()
        dow_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        dow_df["day"] = dow_df["dow"].map(lambda i: dow_names[i])
        fig3 = px.bar(dow_df, x="day", y="covers", color="channel", barmode="group",
                      color_discrete_map=CHANNEL_COLORS,
                      category_orders={"day": dow_names})
        fig3.update_layout(height=320, margin=dict(t=30, b=10))
        st.plotly_chart(fig3, use_container_width=True)

    # DOW x Hour heatmap (one channel at a time)
    st.subheader("Hour × Day-of-week heatmap")
    ch_pick = st.selectbox("Channel", selected_channels or list(CHANNELS), key="heatmap_ch")
    heat_src = obs_f[obs_f["channel"] == ch_pick]
    if not heat_src.empty:
        heat = heat_src.groupby(["dow", "hour"], as_index=False)["covers"].mean()
        heat_p = heat.pivot(index="dow", columns="hour", values="covers")
        heat_p.index = [dow_names[i] for i in heat_p.index]
        fig4 = px.imshow(heat_p, color_continuous_scale="Viridis",
                         labels=dict(color="avg covers", x="hour", y="dow"),
                         aspect="auto")
        fig4.update_layout(height=320, margin=dict(t=30, b=10))
        st.plotly_chart(fig4, use_container_width=True)

    # Rain effect
    st.subheader("Rain effect on covers")
    merged = obs_f.merge(weather, on=["date", "hour"], how="left")
    merged["rain_bucket"] = pd.cut(
        merged["rain_mm"], bins=[-0.1, 0.0, 1.0, 3.0, 6.0, 100.0],
        labels=["dry", "trace", "light", "moderate", "heavy"],
    )
    rain_agg = (
        merged.groupby(["rain_bucket", "channel"], observed=True, as_index=False)["covers"].mean()
    )
    fig5 = px.bar(rain_agg, x="rain_bucket", y="covers", color="channel", barmode="group",
                  color_discrete_map=CHANNEL_COLORS)
    fig5.update_layout(height=320, margin=dict(t=30, b=10),
                       xaxis_title="Rain intensity (per hour)")
    st.plotly_chart(fig5, use_container_width=True)
    st.caption("Rain hurts dine-in, mildly helps delivery, near-neutral on takeaway — matches the injected ground-truth coefficients.")

    # Weather sample
    with st.expander("Weather sample"):
        st.dataframe(weather[(weather["date"] >= start_d) & (weather["date"] <= end_d)].head(200))


# --------------------------------------------------------------------------------------
# Validation page
# --------------------------------------------------------------------------------------

def page_validation() -> None:
    st.title("Validation (last 28 days)")
    st.caption("These are the exact predictions the trained LightGBM base models produce on the holdout window — the basis of the metrics recorded in FEAT-004.")

    df = load_holdout()
    summary = summary_metrics(df)
    st.subheader("Summary metrics per channel")
    st.dataframe(summary.style.format({"MAE": "{:.3f}", "MAPE": "{:.1%}", "Bias": "{:+.3f}", "R2": "{:.3f}"}))

    st.subheader("Actual vs Predicted")
    for ch in CHANNELS:
        sub = df[df["channel"] == ch].sort_values("ts")
        if sub.empty:
            continue
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sub["ts"], y=sub["actual"], name="actual",
                                 line=dict(color=CHANNEL_COLORS[ch], width=2)))
        fig.add_trace(go.Scatter(x=sub["ts"], y=sub["predicted"], name="predicted",
                                 line=dict(color=CHANNEL_COLORS[ch], width=2, dash="dot")))
        fig.update_layout(title=f"{ch} — hourly", height=320, margin=dict(t=40, b=10),
                          legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Daily MAE")
    daily = df.copy()
    daily["abs_err"] = daily["residual"].abs()
    daily_mae = daily.groupby(["date", "channel"], as_index=False)["abs_err"].mean()
    fig_mae = px.line(daily_mae, x="date", y="abs_err", color="channel",
                      color_discrete_map=CHANNEL_COLORS, markers=True,
                      labels={"abs_err": "Daily MAE"})
    fig_mae.update_layout(height=320, margin=dict(t=20, b=10))
    st.plotly_chart(fig_mae, use_container_width=True)

    st.subheader("Residual distribution")
    fig_hist = px.histogram(df, x="residual", color="channel", barmode="overlay",
                            nbins=60, color_discrete_map=CHANNEL_COLORS, opacity=0.55)
    fig_hist.update_layout(height=320, margin=dict(t=20, b=10))
    st.plotly_chart(fig_hist, use_container_width=True)
    st.caption("A residual = predicted − actual. The visible left-shift on delivery is the regime-shift bias (≈ −0.30 from FEAT-004). The SGD residual layer (FEAT-005, upcoming) will close this gap.")

    st.subheader("Hourly profile — predicted vs actual")
    prof = df.groupby(["hour", "channel"], as_index=False)[["actual", "predicted"]].mean()
    fig_prof = go.Figure()
    for ch in CHANNELS:
        s = prof[prof["channel"] == ch]
        if s.empty:
            continue
        fig_prof.add_trace(go.Scatter(x=s["hour"], y=s["actual"], name=f"{ch} actual",
                                      line=dict(color=CHANNEL_COLORS[ch])))
        fig_prof.add_trace(go.Scatter(x=s["hour"], y=s["predicted"], name=f"{ch} pred",
                                      line=dict(color=CHANNEL_COLORS[ch], dash="dot")))
    fig_prof.update_layout(height=360, margin=dict(t=20, b=10),
                           legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_prof, use_container_width=True)


# --------------------------------------------------------------------------------------
# Stub pages
# --------------------------------------------------------------------------------------

def page_stub(title: str) -> None:
    st.title(title)
    st.info("Stub — implementation pending. See PLANNING.md §10 and AGENTS.md Feature Log.")


# --------------------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------------------

PAGES = {
    "Dataset Explorer":      page_dataset_explorer,
    "Validation (last 28d)": page_validation,
    "Today / Tomorrow":      lambda: page_stub("Today / Tomorrow"),
    "Order Sheet":           lambda: page_stub("Order Sheet"),
    "Corrections":           lambda: page_stub("Corrections"),
    "Model Health":          lambda: page_stub("Model Health"),
    "Coefficient Inspector": lambda: page_stub("Coefficient Inspector"),
}


def main() -> None:
    page = st.sidebar.radio("Page", list(PAGES.keys()))
    PAGES[page]()


if __name__ == "__main__":
    main()
