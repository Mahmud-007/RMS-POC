"""Feature builder.

Produces the feature matrix consumed by both the LightGBM base and the SGD residual.

One model is trained per channel, so the builder is parameterised by channel.
Feature groups produced:

    calendar     dow, hour, month, day_of_year_{sin,cos}, is_weekend
    event        is_holiday, is_local_event, event_severity, is_promo
    weather      temp, rain_mm, condition_code (categorical)
    lags         lag_1d, lag_7d, dow_4w_mean, rolling_7d_mean
    interaction  rain_x_weekend, rain_x_dinner  (used only by the residual layer)
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DB_PATH = Path("artifacts/rms.db")

CONDITION_CODES = {
    "clear": 0,
    "rain_light": 1,
    "rain_heavy": 2,
    "snow": 3,
    "hot": 4,
    "cold": 5,
}

BASE_FEATURES = [
    "dow", "hour", "month", "day_of_year_sin", "day_of_year_cos", "is_weekend",
    "is_holiday", "is_local_event", "event_severity", "is_promo",
    "temp", "rain_mm", "condition_code",
    "lag_1d", "lag_7d", "dow_4w_mean", "rolling_7d_mean",
]

CATEGORICAL_FEATURES = ["condition_code", "dow", "hour", "month"]

INTERACTION_FEATURES = ["rain_x_weekend", "rain_x_dinner"]

# Lag history needed before the first usable training row
LAG_WARMUP_DAYS = 28


@dataclass(frozen=True)
class FeatureSpec:
    columns: list[str]
    categorical: list[str] = field(default_factory=list)
    target: str = "covers"


# --------------------------------------------------------------------------------------
# Raw load
# --------------------------------------------------------------------------------------

def _load_panel(channel: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Hourly observations for one channel, joined with weather and event flags."""
    with sqlite3.connect(db_path) as conn:
        obs = pd.read_sql(
            "SELECT ts, covers FROM observations WHERE channel = ? ORDER BY ts",
            conn, params=(channel,),
        )
        weather = pd.read_sql("SELECT date, hour, temp, rain_mm, condition FROM weather", conn)
        events = pd.read_sql("SELECT date, type, severity FROM events", conn)

    obs["ts"] = pd.to_datetime(obs["ts"])
    obs["date"] = obs["ts"].dt.strftime("%Y-%m-%d")
    obs["hour"] = obs["ts"].dt.hour

    df = obs.merge(weather, on=["date", "hour"], how="left")

    # Pivot events into per-date flags
    ev_pivot = events.pivot_table(
        index="date", columns="type", values="severity", aggfunc="max"
    ).reset_index()
    for col in ("holiday", "local_event", "promo"):
        if col not in ev_pivot.columns:
            ev_pivot[col] = np.nan
    ev_pivot = ev_pivot.rename(columns={
        "holiday": "_ev_holiday",
        "local_event": "_ev_local",
        "promo": "_ev_promo",
    })[["date", "_ev_holiday", "_ev_local", "_ev_promo"]]

    df = df.merge(ev_pivot, on="date", how="left")
    return df


# --------------------------------------------------------------------------------------
# Feature group helpers
# --------------------------------------------------------------------------------------

def _add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["dow"] = df["ts"].dt.dayofweek.astype("int16")
    df["month"] = df["ts"].dt.month.astype("int16")
    doy = df["ts"].dt.dayofyear
    df["day_of_year_sin"] = np.sin(2 * math.pi * doy / 365.25)
    df["day_of_year_cos"] = np.cos(2 * math.pi * doy / 365.25)
    df["is_weekend"] = (df["dow"] >= 5).astype("int8")
    return df


def _add_event(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_holiday"] = df["_ev_holiday"].notna().astype("int8")
    df["is_local_event"] = df["_ev_local"].notna().astype("int8")
    df["event_severity"] = df["_ev_local"].fillna(0.0).astype("float32")
    df["is_promo"] = df["_ev_promo"].notna().astype("int8")
    return df.drop(columns=["_ev_holiday", "_ev_local", "_ev_promo"])


def _add_weather(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["condition_code"] = df["condition"].map(CONDITION_CODES).fillna(0).astype("int16")
    return df.drop(columns=["condition"])


def _add_lags(df: pd.DataFrame) -> pd.DataFrame:
    """Lag features relative to the same hour on previous days.

    Assumes `df` is sorted by ts ascending and has exactly one row per (date, hour)
    for a single channel — which the generator guarantees (12 service hours/day).
    """
    df = df.copy().sort_values("ts").reset_index(drop=True)
    hours_per_day = 12  # service window 11..22
    df["lag_1d"] = df["covers"].shift(hours_per_day)
    df["lag_7d"] = df["covers"].shift(hours_per_day * 7)

    # dow_4w_mean = mean of covers at same hour 7/14/21/28 days ago
    lag2 = df["covers"].shift(hours_per_day * 14)
    lag3 = df["covers"].shift(hours_per_day * 21)
    lag4 = df["covers"].shift(hours_per_day * 28)
    df["dow_4w_mean"] = pd.concat(
        [df["lag_7d"], lag2, lag3, lag4], axis=1
    ).mean(axis=1)

    # rolling_7d_mean: mean of same-hour covers across the previous 7 days (excluding today)
    same_hour = (
        df.set_index("ts")["covers"]
          .shift(hours_per_day)            # exclude today's value
          .rolling(window=hours_per_day * 7, min_periods=1)
          .mean()
          .reset_index(drop=True)
    )
    df["rolling_7d_mean"] = same_hour
    return df


def _add_interactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rain_x_weekend"] = df["rain_mm"] * df["is_weekend"]
    df["rain_x_dinner"] = df["rain_mm"] * ((df["hour"] >= 18) & (df["hour"] <= 21)).astype("int8")
    return df


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------

def build_training_frame(
    channel: str,
    db_path: Path = DB_PATH,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, FeatureSpec]:
    """Build (X, y, ts, spec) ready for LightGBM training.

    Drops the first LAG_WARMUP_DAYS days so all lag features are populated.
    """
    df = _load_panel(channel, db_path)
    df = _add_calendar(df)
    df = _add_event(df)
    df = _add_weather(df)
    df = _add_lags(df)

    df = df.dropna(subset=["lag_1d", "lag_7d", "dow_4w_mean", "rolling_7d_mean"]).reset_index(drop=True)

    spec = FeatureSpec(columns=list(BASE_FEATURES), categorical=list(CATEGORICAL_FEATURES))
    X = df[spec.columns].copy()
    y = df["covers"].astype("float32")
    return X, y, df["ts"].copy(), spec


def build_inference_row(
    ts: datetime,
    channel: str,
    db_path: Path = DB_PATH,
    include_interactions: bool = False,
) -> pd.DataFrame:
    """Single-row feature frame for a future (ts, channel). Lags pulled from history."""
    df = _load_panel(channel, db_path)

    # Inject a placeholder row for the target ts if missing, so the pipeline computes lags for it
    target_date = ts.strftime("%Y-%m-%d")
    target_hour = ts.hour
    if not ((df["date"] == target_date) & (df["hour"] == target_hour)).any():
        placeholder = {
            "ts": pd.Timestamp(ts),
            "covers": np.nan,
            "date": target_date,
            "hour": target_hour,
            "temp": np.nan,
            "rain_mm": np.nan,
            "condition": "clear",
            "_ev_holiday": np.nan,
            "_ev_local": np.nan,
            "_ev_promo": np.nan,
        }
        df = pd.concat([df, pd.DataFrame([placeholder])], ignore_index=True)
        df = df.sort_values("ts").reset_index(drop=True)

    df = _add_calendar(df)
    df = _add_event(df)
    df = _add_weather(df)
    df = _add_lags(df)
    if include_interactions:
        df = _add_interactions(df)

    row = df[df["ts"] == pd.Timestamp(ts)]
    if row.empty:
        raise ValueError(f"No row produced for ts={ts}, channel={channel}")
    cols = BASE_FEATURES + (INTERACTION_FEATURES if include_interactions else [])
    return row[cols].reset_index(drop=True)


def append_residual_features(
    base_features: pd.DataFrame,
    base_pred: float,
    reason_tag: str,
    reason_vocab: list[str],
) -> pd.DataFrame:
    """Extend a base feature row with base_pred + reason-tag one-hots for SGD input."""
    out = base_features.copy()
    out["base_pred"] = base_pred
    for tag in reason_vocab:
        out[f"reason_{tag}"] = int(reason_tag == tag)
    return out
