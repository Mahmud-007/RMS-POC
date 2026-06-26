"""RMS dashboard — Streamlit.

Pages:
    1. Today / Tomorrow       — hourly covers + staffing for a chosen date
    2. Order Sheet            — ingredient orders over the horizon
    3. Corrections            — submit predicted-vs-actual feedback
    4. Model Health           — rolling MAE, registry, retrain controls
    5. Coefficient Inspector  — LGBM importance + SGD coefficients
    6. Dataset Explorer       — full dataset filters + charts (FEAT-005)
    7. Validation (last 28d)  — base-model holdout view (FEAT-005)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable when Streamlit launches this file directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Bootstrap data + models on first run (Streamlit Cloud / HF Spaces ephemeral disk).
# Idempotent: skips if the artifact DB already exists.
_ARTIFACT_DB = _REPO_ROOT / "artifacts" / "rms.db"
if not _ARTIFACT_DB.exists():
    print("[bootstrap] artifact db missing — generating dataset and training models")
    from app.data.generator import generate as _generate_data
    from app.train.init_sgd import run as _init_sgd
    from app.train.train_base import run as _train_base
    _generate_data()
    _train_base()
    _init_sgd()
    print("[bootstrap] done")

import sqlite3
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.api.corrections import Correction, submit_correction
from app.data.generator import REGIME_SHIFT_DAY, START_DATE
from app.eval.backtest import run as run_backtest
from app.eval.backtest import summary as backtest_summary
from app.eval.holdout import (
    load_latest_base,
    load_latest_sgd,
    predict_holdout_all_channels,
    summary_metrics,
)
from app.features.feature_builder import REASON_TAGS
from app.predict.covers import predict_day as predict_covers
from app.predict.orders import horizon_for_ingredients, predict_orders
from app.predict.staff import predict_day as predict_staff

DB_PATH = Path("artifacts/rms.db")
CHANNELS = ("dine_in", "delivery", "takeaway")
CHANNEL_COLORS = {"dine_in": "#1f77b4", "delivery": "#ff7f0e", "takeaway": "#2ca02c"}
DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
REGIME_SHIFT_DATE = (START_DATE + timedelta(days=REGIME_SHIFT_DAY)).isoformat()

st.set_page_config(page_title="RMS", layout="wide")


# --------------------------------------------------------------------------------------
# Cached loaders
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


@st.cache_data(show_spinner=False)
def load_corrections() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql(
            "SELECT ts, channel, predicted, actual, reason_tag, created_at FROM corrections "
            "ORDER BY created_at DESC", conn,
        )
    df["ts"] = pd.to_datetime(df["ts"])
    return df


@st.cache_data(show_spinner=False)
def load_registry() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(
            "SELECT version, type, trained_at, mae, r2, path FROM model_registry "
            "ORDER BY trained_at DESC", conn,
        )


@st.cache_data(show_spinner=True)
def load_backtest(n_days: int = 60) -> pd.DataFrame:
    return run_backtest(n_days=n_days)


# --------------------------------------------------------------------------------------
# Page 1 — Today / Tomorrow
# --------------------------------------------------------------------------------------

def page_today_tomorrow() -> None:
    st.title("Today / Tomorrow")
    st.caption("Hourly cover forecast per channel + staffing rule-derived from covers.")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        default_date = date.today() + timedelta(days=1)
        target = st.date_input("Forecast date", value=default_date)
    with col2:
        reason = st.selectbox(
            "Scenario (what-if reason tag)", REASON_TAGS,
            index=REASON_TAGS.index("normal"),
        )
    with col3:
        st.write("")
        st.write("")
        if st.button("Refresh forecast"):
            st.cache_data.clear()

    forecast = predict_covers(target=target, reason_tag=reason)
    staff = predict_staff(target)

    # Hourly covers chart
    hourly_rows = []
    for ch, rows in forecast.items():
        for row in rows:
            hourly_rows.append({
                "hour": row["hour"], "channel": ch, "covers": row["final_pred"],
                "base": row["base_pred"], "residual": row["residual_pred"],
            })
    hourly_df = pd.DataFrame(hourly_rows)

    st.subheader("Hourly cover forecast")
    fig = px.bar(
        hourly_df, x="hour", y="covers", color="channel",
        color_discrete_map=CHANNEL_COLORS, barmode="stack",
        labels={"covers": "Forecast covers"},
    )
    fig.update_layout(height=380, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Channel totals
    st.subheader("Daily channel totals")
    totals = hourly_df.groupby("channel", as_index=False)["covers"].sum()
    cols = st.columns(len(totals))
    for i, row in totals.iterrows():
        cols[i].metric(label=row["channel"], value=f"{row['covers']:.1f}")

    # Staffing table
    st.subheader("Recommended staffing")
    staff_rows = []
    for h in staff["hourly"]:
        rec = {"hour": h["hour"], "total_covers": round(h["covers_total"], 1)}
        rec.update(h["headcount"])
        staff_rows.append(rec)
    staff_df = pd.DataFrame(staff_rows).set_index("hour")
    st.dataframe(staff_df, use_container_width=True)
    cols = st.columns(4)
    for i, (role, hours) in enumerate(staff["person_hours"].items()):
        cols[i].metric(label=f"{role} person-hours", value=hours,
                        delta=f"peak {staff['peak_headcount'][role]}")

    # Base vs final composition
    with st.expander("Base vs residual breakdown"):
        breakdown = hourly_df.groupby("hour", as_index=False)[["base", "residual", "covers"]].sum()
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=breakdown["hour"], y=breakdown["base"], name="base", marker_color="#777"))
        fig2.add_trace(go.Bar(x=breakdown["hour"], y=breakdown["residual"], name="residual", marker_color="#ff7f0e"))
        fig2.update_layout(barmode="relative", height=340, margin=dict(t=20, b=10))
        st.plotly_chart(fig2, use_container_width=True)


# --------------------------------------------------------------------------------------
# Page 2 — Order Sheet
# --------------------------------------------------------------------------------------

def page_order_sheet() -> None:
    st.title("Order Sheet")
    st.caption("Ingredient orders over the supplier lead-time horizon, capped by shelf life × usage.")

    default_horizon = horizon_for_ingredients()
    col1, col2 = st.columns([1, 2])
    with col1:
        start = st.date_input("Window start", value=date.today() + timedelta(days=1))
    with col2:
        horizon = st.slider("Horizon (days)", min_value=1, max_value=21, value=default_horizon)
    end = start + timedelta(days=horizon - 1)

    rows = predict_orders(start, end)
    df = pd.DataFrame(rows)

    st.metric("Window", f"{start.isoformat()} → {end.isoformat()}")
    st.metric("Ingredients to order", int((df["recommended_order"] > 0).sum()))

    cap_clipped = df[df["shelf_cap"] < df["raw_order"]]
    if not cap_clipped.empty:
        st.warning(
            "Shelf-life cap binding on: "
            + ", ".join(cap_clipped["name"].tolist())
        )

    show = df[[
        "name", "unit", "stock_on_hand", "forecast_need",
        "shelf_cap", "raw_order", "recommended_order",
        "shelf_life_days", "lead_time_days",
    ]]
    st.dataframe(
        show.style.format({
            "stock_on_hand": "{:.2f}", "forecast_need": "{:.2f}",
            "shelf_cap": "{:.2f}", "raw_order": "{:.2f}",
            "recommended_order": "{:.2f}",
        }),
        use_container_width=True,
    )

    if st.button("Approve order (POC — no-op)"):
        st.success("Order approved (POC stub — supplier integration not wired).")


# --------------------------------------------------------------------------------------
# Page 3 — Corrections
# --------------------------------------------------------------------------------------

def page_corrections() -> None:
    st.title("Corrections")
    st.caption("Submit actual covers for a past hour. Updates the SGD residual layer immediately.")

    col1, col2 = st.columns(2)
    with col1:
        c_date = st.date_input("Date", value=date.today())
        c_hour = st.selectbox("Hour", list(range(11, 23)), index=8)  # default 19:00
        c_channel = st.selectbox("Channel", CHANNELS)
    with col2:
        actual = st.number_input("Actual covers", min_value=0.0, value=10.0, step=1.0)
        reason = st.selectbox("Reason tag", REASON_TAGS, index=REASON_TAGS.index("normal"))

    ts = datetime.combine(c_date, time(c_hour))

    if st.button("Submit correction", type="primary"):
        payload = Correction(ts=ts, channel=c_channel, actual=actual, reason_tag=reason)
        try:
            result = submit_correction(payload)
        except Exception as exc:
            st.error(f"Failed: {exc}")
        else:
            st.success(f"Correction logged. Model now at n_updates = {result.n_updates}")
            cols = st.columns(4)
            cols[0].metric("Base prediction", f"{result.base_pred:.2f}")
            cols[1].metric("Residual (before)", f"{result.residual_pred_before:+.3f}")
            cols[2].metric("Residual (after)", f"{result.residual_pred_after:+.3f}",
                            delta=f"{result.residual_pred_after - result.residual_pred_before:+.3f}")
            cols[3].metric("Clipped target", f"{result.target_residual_clipped:+.2f}",
                            delta=f"raw: {result.target_residual:+.2f}")
            st.cache_data.clear()

    st.subheader("Recent corrections")
    corr = load_corrections()
    if corr.empty:
        st.info("No corrections submitted yet.")
    else:
        st.dataframe(corr.head(50), use_container_width=True)


# --------------------------------------------------------------------------------------
# Page 4 — Model Health
# --------------------------------------------------------------------------------------

def page_model_health() -> None:
    st.title("Model Health")
    st.caption("Rolling accuracy + correction activity + model registry. Retrain controls live here.")

    holdout = load_holdout()
    summary = summary_metrics(holdout)
    st.subheader("Validation metrics (last 28d, base model only)")
    st.dataframe(summary.style.format({"MAE": "{:.3f}", "MAPE": "{:.1%}", "Bias": "{:+.3f}", "R2": "{:.3f}"}))

    # Activity counters
    st.subheader("Activity")
    corr = load_corrections()
    activity_cols = st.columns(3)
    for i, ch in enumerate(CHANNELS):
        sgd = load_latest_sgd(ch)
        n_corr = int((corr["channel"] == ch).sum()) if not corr.empty else 0
        activity_cols[i].metric(
            f"{ch}",
            f"{n_corr} corrections",
            delta=f"SGD n_updates = {sgd.n_updates}" if sgd else "no SGD",
        )

    # Daily MAE chart
    st.subheader("Daily MAE on validation window")
    daily = holdout.copy()
    daily["abs_err"] = daily["residual"].abs()
    daily_mae = daily.groupby(["date", "channel"], as_index=False)["abs_err"].mean()
    fig = px.line(daily_mae, x="date", y="abs_err", color="channel",
                  color_discrete_map=CHANNEL_COLORS, markers=True)
    fig.update_layout(height=320, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Retrain controls
    st.subheader("Retrain controls")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Retrain base (LightGBM, all channels)"):
            from app.train.train_base import run as run_train
            with st.spinner("Training..."):
                result = run_train()
            st.success(f"Retrained {len(result)} channels.")
            st.json({ch: {"mae": v["metrics"]["mae"], "r2": v["metrics"]["r2"]} for ch, v in result.items()})
            st.cache_data.clear()
    with col_b:
        if st.button("Reset SGD residual (warm-start from base)"):
            from app.train.init_sgd import run as run_init
            with st.spinner("Warm-starting SGD..."):
                result = run_init()
            st.success("SGD warm-started.")
            st.json({ch: {"warm_mae": v["warm_mae"], "n_train": v["n_train"]} for ch, v in result.items()})
            st.cache_data.clear()

    # Backtest convergence
    st.subheader("Backtest replay — naive vs base vs hybrid")
    st.caption(
        "Fresh SGD warm-started on data before the backtest window, then replayed "
        "hour-by-hour with corrections fed back. On stationary data the hybrid tracks "
        "the base closely; the value of the residual layer shows up on regime shifts "
        "and via manager-tagged corrections submitted in real time."
    )
    bt_days = st.slider("Backtest window (days)", 14, 90, 60, key="bt_days")
    bt = load_backtest(bt_days)
    if bt.empty:
        st.info("Not enough data in the window.")
    else:
        st.dataframe(
            backtest_summary(bt).style.format("{:.3f}"),
            use_container_width=True,
        )
        bt_ch = st.selectbox("Channel", CHANNELS, key="bt_channel")
        sub = bt[bt["channel"] == bt_ch]
        fig_bt = px.line(
            sub, x="date", y="rolling_mae", color="variant",
            color_discrete_map={"naive": "#888", "base": "#1f77b4", "hybrid": "#ff7f0e"},
            markers=True,
            labels={"rolling_mae": "7-day rolling MAE"},
        )
        fig_bt.update_layout(height=380, margin=dict(t=20, b=10))
        st.plotly_chart(fig_bt, use_container_width=True)

    # Registry
    st.subheader("Model registry")
    reg = load_registry()
    st.dataframe(
        reg.style.format({"mae": "{:.3f}", "r2": "{:.3f}"}),
        use_container_width=True,
    )


# --------------------------------------------------------------------------------------
# Page 5 — Coefficient Inspector
# --------------------------------------------------------------------------------------

def page_coefficient_inspector() -> None:
    st.title("Coefficient Inspector")
    st.caption("What the model has learned. LightGBM feature importance (gain) + SGD residual coefficients.")

    channel = st.selectbox("Channel", CHANNELS)

    base = load_latest_base(channel)
    sgd = load_latest_sgd(channel)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("LightGBM base — feature importance (gain)")
        imp = pd.Series(base.feature_importance(importance_type="gain"))
        imp = imp.sort_values(ascending=True)
        fig = px.bar(imp, orientation="h", labels={"value": "gain", "index": "feature"})
        fig.update_layout(height=540, margin=dict(t=20, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("SGD residual — coefficients")
        if sgd is None or not sgd.fitted:
            st.warning("SGD not warm-started for this channel.")
        else:
            coefs = pd.Series(sgd.coefficients).sort_values(key=lambda s: s.abs(), ascending=True)
            colors = ["#d62728" if v < 0 else "#2ca02c" for v in coefs.values]
            fig2 = go.Figure(go.Bar(
                x=coefs.values, y=coefs.index, orientation="h",
                marker_color=colors,
            ))
            fig2.update_layout(height=540, margin=dict(t=20, b=10),
                               xaxis_title="coefficient (scaled features)")
            st.plotly_chart(fig2, use_container_width=True)
            st.metric("n_updates", sgd.n_updates)
            st.metric("intercept", f"{sgd.intercept:+.3f}")


# --------------------------------------------------------------------------------------
# Page 6 — Dataset Explorer (unchanged from FEAT-005)
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

    st.subheader("Daily covers per channel")
    daily = obs_f.groupby(["date", "channel"], as_index=False)["covers"].sum()
    fig = px.line(
        daily, x="date", y="covers", color="channel",
        color_discrete_map=CHANNEL_COLORS,
        labels={"covers": "Daily covers"},
    )
    regime_d = pd.to_datetime(REGIME_SHIFT_DATE).date()
    if start_d <= regime_d <= end_d:
        fig.add_shape(type="line", x0=regime_d, x1=regime_d, xref="x",
                      y0=0, y1=1, yref="paper",
                      line=dict(color="red", dash="dash", width=2))
        fig.add_annotation(x=regime_d, y=1.0, xref="x", yref="paper",
                           text="regime shift", showarrow=False,
                           xanchor="left", yanchor="bottom", font=dict(color="red"))
    ev_window = events[(events["date"] >= start_d) & (events["date"] <= end_d)]
    for _, row in ev_window.iterrows():
        color = {"holiday": "purple", "local_event": "gold", "promo": "lightblue"}.get(row["type"], "gray")
        fig.add_shape(type="line", x0=row["date"], x1=row["date"], xref="x",
                      y0=0, y1=1, yref="paper",
                      line=dict(color=color, dash="dot", width=1), opacity=0.35)
    fig.update_layout(height=380, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Vertical dotted lines: purple = holiday, gold = local event, light-blue = promo. Red dashed = regime shift.")

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
        dow_df["day"] = dow_df["dow"].map(lambda i: DOW_NAMES[i])
        fig3 = px.bar(dow_df, x="day", y="covers", color="channel", barmode="group",
                      color_discrete_map=CHANNEL_COLORS,
                      category_orders={"day": DOW_NAMES})
        fig3.update_layout(height=320, margin=dict(t=30, b=10))
        st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Hour × Day-of-week heatmap")
    ch_pick = st.selectbox("Channel", selected_channels or list(CHANNELS), key="heatmap_ch")
    heat_src = obs_f[obs_f["channel"] == ch_pick]
    if not heat_src.empty:
        heat = heat_src.groupby(["dow", "hour"], as_index=False)["covers"].mean()
        heat_p = heat.pivot(index="dow", columns="hour", values="covers")
        heat_p.index = [DOW_NAMES[i] for i in heat_p.index]
        fig4 = px.imshow(heat_p, color_continuous_scale="Viridis",
                         labels=dict(color="avg covers", x="hour", y="dow"),
                         aspect="auto")
        fig4.update_layout(height=320, margin=dict(t=30, b=10))
        st.plotly_chart(fig4, use_container_width=True)

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


# --------------------------------------------------------------------------------------
# Page 7 — Validation
# --------------------------------------------------------------------------------------

def page_validation() -> None:
    st.title("Validation (last 28d)")
    st.caption("Base-model predictions on the holdout window — basis of the FEAT-004 metrics.")

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


# --------------------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------------------

PAGES = {
    "Today / Tomorrow":      page_today_tomorrow,
    "Order Sheet":           page_order_sheet,
    "Corrections":           page_corrections,
    "Model Health":          page_model_health,
    "Coefficient Inspector": page_coefficient_inspector,
    "Dataset Explorer":      page_dataset_explorer,
    "Validation (last 28d)": page_validation,
}


def main() -> None:
    page = st.sidebar.radio("Page", list(PAGES.keys()))
    PAGES[page]()


if __name__ == "__main__":
    main()
