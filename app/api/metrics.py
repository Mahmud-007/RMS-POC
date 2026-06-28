"""Model health and metric endpoints."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query

from app.eval.holdout import load_latest_sgd
from app.train.train_base import VALIDATION_DAYS, _evaluate

DB_PATH = Path("artifacts/rms.db")
CHANNELS = ("dine_in", "delivery", "takeaway")
DEFAULT_ROLLING_DAYS = 30

router = APIRouter()


def _rolling_metrics(channel: str, days: int, db_path: Path) -> dict:
    """Compare stored predictions against observed actuals over the last `days`."""
    with sqlite3.connect(db_path) as conn:
        pred = pd.read_sql(
            "SELECT ts, final_pred FROM predictions WHERE channel = ?",
            conn, params=(channel,),
        )
        obs = pd.read_sql(
            "SELECT ts, covers AS actual FROM observations WHERE channel = ?",
            conn, params=(channel,),
        )
    if pred.empty or obs.empty:
        return {"n": 0, "mae": None, "mape": None, "bias": None, "r2": None}

    pred["ts"] = pd.to_datetime(pred["ts"])
    obs["ts"] = pd.to_datetime(obs["ts"])
    cutoff = obs["ts"].max() - pd.Timedelta(days=days)
    merged = pred.merge(obs, on="ts", how="inner")
    merged = merged[merged["ts"] >= cutoff]
    if merged.empty:
        return {"n": 0, "mae": None, "mape": None, "bias": None, "r2": None}

    m = _evaluate(merged["actual"].to_numpy(), merged["final_pred"].to_numpy())
    return {"n": int(len(merged)), **m}


def _correction_count(channel: str, db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM corrections WHERE channel = ?", (channel,),
        ).fetchone()[0]
    return int(n)


@router.get("")
def get_metrics(rolling_days: int = Query(DEFAULT_ROLLING_DAYS, ge=1, le=365)) -> dict:
    """Per-channel rolling MAE/MAPE/bias/R² and correction counts."""
    out: dict[str, dict] = {}
    for ch in CHANNELS:
        rolling = _rolling_metrics(ch, rolling_days, DB_PATH)
        sgd = load_latest_sgd(ch)
        out[ch] = {
            "rolling": rolling,
            "rolling_days": rolling_days,
            "n_corrections": _correction_count(ch, DB_PATH),
            "sgd_n_updates": int(sgd.n_updates) if sgd else 0,
            "sgd_fitted": bool(sgd.fitted) if sgd else False,
        }
    return out


@router.get("/accuracy")
def get_accuracy(n_days: int = Query(VALIDATION_DAYS, ge=7, le=120)) -> dict:
    """Real, measured accuracy from the holdout window.

    Unlike /metrics (which needs a populated predictions table), this runs the
    current base models on the last `n_days` of *known actuals* and reports the
    measured error. accuracy = 1 - MAPE.
    """
    from app.eval.holdout import predict_holdout_all_channels, summary_metrics

    df = predict_holdout_all_channels(n_days=n_days)
    summary = summary_metrics(df)  # indexed by channel: MAE, MAPE, Bias, R2, n

    channels: dict[str, dict] = {}
    for ch, row in summary.iterrows():
        mape = float(row["MAPE"])
        channels[str(ch)] = {
            "mae": float(row["MAE"]),
            "mape": mape,
            "bias": float(row["Bias"]),
            "r2": float(row["R2"]),
            "n": int(row["n"]),
            "accuracy": max(0.0, 1.0 - mape),
        }
    overall_mape = float(summary["MAPE"].mean())
    return {
        "n_days": n_days,
        "overall_accuracy": max(0.0, 1.0 - overall_mape),
        "overall_mape": overall_mape,
        "channels": channels,
    }


@router.get("/registry")
def get_model_registry() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT version, type, trained_at, mae, r2, path FROM model_registry "
            "ORDER BY trained_at DESC"
        ).fetchall()
    return [
        {"version": r[0], "type": r[1], "trained_at": r[2],
         "mae": r[3], "r2": r[4], "path": r[5]}
        for r in rows
    ]


@router.get("/coefficients")
def get_sgd_coefficients(channel: str | None = Query(None)) -> dict:
    """Current SGD coefficients per channel (top by absolute magnitude first)."""
    channels = (channel,) if channel else CHANNELS
    out: dict[str, dict] = {}
    for ch in channels:
        sgd = load_latest_sgd(ch)
        if sgd is None:
            out[ch] = {"fitted": False, "coefficients": {}, "intercept": 0.0, "n_updates": 0}
            continue
        coefs = sgd.coefficients
        sorted_coefs = dict(sorted(coefs.items(), key=lambda kv: abs(kv[1]), reverse=True))
        out[ch] = {
            "fitted": sgd.fitted,
            "intercept": sgd.intercept,
            "n_updates": int(sgd.n_updates),
            "coefficients": sorted_coefs,
        }
    return out
