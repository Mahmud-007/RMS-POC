"""Generate static PNG charts for docs/DATA_INSIGHTS.md.

Mirrors the Dataset Explorer page in the Streamlit dashboard but renders to disk
so the docs always reflect the current dataset.

Run from repo root:
    python -m app.eval.insights
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.data.generator import REGIME_SHIFT_DAY, START_DATE

DB_PATH = Path("artifacts/rms.db")
FIG_DIR = Path("docs/figures")

CHANNELS = ("dine_in", "delivery", "takeaway")
CHANNEL_COLORS = {"dine_in": "#1f77b4", "delivery": "#ff7f0e", "takeaway": "#2ca02c"}
DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WIDTH, HEIGHT = 1100, 480


def _save(fig: go.Figure, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / f"{name}.png"
    fig.write_image(out, width=WIDTH, height=HEIGHT, scale=2)
    print(f"  wrote {out}")
    return out


def _load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with sqlite3.connect(DB_PATH) as conn:
        obs = pd.read_sql("SELECT ts, channel, covers FROM observations", conn)
        weather = pd.read_sql("SELECT date, hour, temp, rain_mm, condition FROM weather", conn)
        events = pd.read_sql("SELECT date, type, severity FROM events", conn)
    obs["ts"] = pd.to_datetime(obs["ts"])
    obs["date"] = obs["ts"].dt.date
    obs["hour"] = obs["ts"].dt.hour
    obs["dow"] = obs["ts"].dt.dayofweek
    weather["date"] = pd.to_datetime(weather["date"]).dt.date
    events["date"] = pd.to_datetime(events["date"]).dt.date
    return obs, weather, events


# --------------------------------------------------------------------------------------
# Individual chart builders
# --------------------------------------------------------------------------------------

def fig_daily_covers(obs: pd.DataFrame, events: pd.DataFrame) -> go.Figure:
    daily = obs.groupby(["date", "channel"], as_index=False)["covers"].sum()
    fig = px.line(
        daily, x="date", y="covers", color="channel",
        color_discrete_map=CHANNEL_COLORS,
        labels={"covers": "Daily covers", "date": ""},
        title="Daily covers per channel — full dataset",
    )
    regime_d = START_DATE + timedelta(days=REGIME_SHIFT_DAY)
    fig.add_shape(type="line", x0=regime_d, x1=regime_d, xref="x",
                  y0=0, y1=1, yref="paper",
                  line=dict(color="red", dash="dash", width=2))
    fig.add_annotation(x=regime_d, y=1.0, xref="x", yref="paper",
                       text="regime shift (delivery 2×)", showarrow=False,
                       xanchor="left", yanchor="bottom", font=dict(color="red"))
    for _, row in events.iterrows():
        color = {"holiday": "purple", "local_event": "gold", "promo": "lightblue"}.get(row["type"], "gray")
        fig.add_shape(type="line", x0=row["date"], x1=row["date"], xref="x",
                      y0=0, y1=1, yref="paper",
                      line=dict(color=color, dash="dot", width=1), opacity=0.35)
    fig.update_layout(margin=dict(t=60, b=40, l=40, r=20), legend=dict(orientation="h", y=-0.18))
    return fig


def fig_hour_of_day(obs: pd.DataFrame) -> go.Figure:
    hourly = obs.groupby(["hour", "channel"], as_index=False)["covers"].mean()
    fig = px.line(
        hourly, x="hour", y="covers", color="channel",
        color_discrete_map=CHANNEL_COLORS, markers=True,
        labels={"covers": "Average covers per hour"},
        title="Average covers by hour of day",
    )
    fig.update_layout(margin=dict(t=60, b=40, l=40, r=20), legend=dict(orientation="h", y=-0.18))
    return fig


def fig_dow(obs: pd.DataFrame) -> go.Figure:
    dow_df = obs.groupby(["dow", "channel"], as_index=False)["covers"].mean()
    dow_df["day"] = dow_df["dow"].map(lambda i: DOW_NAMES[i])
    fig = px.bar(
        dow_df, x="day", y="covers", color="channel", barmode="group",
        color_discrete_map=CHANNEL_COLORS,
        category_orders={"day": DOW_NAMES},
        labels={"covers": "Average hourly covers"},
        title="Average covers by day of week",
    )
    fig.update_layout(margin=dict(t=60, b=40, l=40, r=20), legend=dict(orientation="h", y=-0.18))
    return fig


def fig_heatmap(obs: pd.DataFrame, channel: str) -> go.Figure:
    sub = obs[obs["channel"] == channel]
    heat = sub.groupby(["dow", "hour"], as_index=False)["covers"].mean()
    heat_p = heat.pivot(index="dow", columns="hour", values="covers")
    heat_p.index = [DOW_NAMES[i] for i in heat_p.index]
    fig = px.imshow(
        heat_p, color_continuous_scale="Viridis",
        labels=dict(color="avg covers", x="hour", y=""),
        aspect="auto",
        title=f"Hour × Day-of-week heatmap — {channel}",
    )
    fig.update_layout(margin=dict(t=60, b=40, l=40, r=20))
    return fig


def fig_rain_effect(obs: pd.DataFrame, weather: pd.DataFrame) -> go.Figure:
    merged = obs.merge(weather, on=["date", "hour"], how="left")
    merged["rain_bucket"] = pd.cut(
        merged["rain_mm"], bins=[-0.1, 0.0, 1.0, 3.0, 6.0, 100.0],
        labels=["dry", "trace", "light", "moderate", "heavy"],
    )
    rain_agg = (
        merged.groupby(["rain_bucket", "channel"], observed=True, as_index=False)["covers"].mean()
    )
    fig = px.bar(
        rain_agg, x="rain_bucket", y="covers", color="channel", barmode="group",
        color_discrete_map=CHANNEL_COLORS,
        labels={"covers": "Average hourly covers", "rain_bucket": "Rain intensity"},
        title="Rain effect on covers per channel",
    )
    fig.update_layout(margin=dict(t=60, b=40, l=40, r=20), legend=dict(orientation="h", y=-0.18))
    return fig


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------

def run() -> list[Path]:
    obs, weather, events = _load()
    outputs: list[Path] = []
    outputs.append(_save(fig_daily_covers(obs, events), "01_daily_covers"))
    outputs.append(_save(fig_hour_of_day(obs), "02_hour_of_day"))
    outputs.append(_save(fig_dow(obs), "03_day_of_week"))
    for ch in CHANNELS:
        outputs.append(_save(fig_heatmap(obs, ch), f"04_heatmap_{ch}"))
    outputs.append(_save(fig_rain_effect(obs, weather), "05_rain_effect"))
    print(f"\nWrote {len(outputs)} figures into {FIG_DIR}")
    return outputs


if __name__ == "__main__":
    run()
