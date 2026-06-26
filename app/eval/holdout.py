"""Holdout / validation-window evaluation helpers.

Reproduces the prediction step from `app/train/train_base.py` so the dashboard can
visualise exactly what the recorded metrics were computed on.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.features.feature_builder import build_training_frame
from app.models.base_lgbm import LgbmBase
from app.models.residual_sgd import SgdResidual
from app.train.train_base import VALIDATION_DAYS

DB_PATH = Path("artifacts/rms.db")


def load_latest_base(channel: str, db_path: Path = DB_PATH) -> LgbmBase:
    """Load the most recently registered base model for a channel."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT path FROM model_registry WHERE type = ? "
            "ORDER BY trained_at DESC LIMIT 1",
            (f"lgbm_base_{channel}",),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"No base model registered for channel={channel}")
    model = LgbmBase()
    model.load(row[0])
    return model


def load_latest_sgd(channel: str, db_path: Path = DB_PATH) -> SgdResidual | None:
    """Load the most recently registered SGD residual for a channel, or None if absent."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT path FROM model_registry WHERE type = ? "
            "ORDER BY trained_at DESC LIMIT 1",
            (f"sgd_residual_{channel}",),
        ).fetchone()
    if row is None:
        return None
    sgd = SgdResidual()
    sgd.load(row[0])
    return sgd


def predict_holdout(
    channel: str,
    n_days: int = VALIDATION_DAYS,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """Return (ts, actual, predicted, residual) for the last n_days of data."""
    X, y, ts, _spec = build_training_frame(channel, db_path)
    cutoff = ts.max() - timedelta(days=n_days)
    mask = ts > cutoff
    X_va, y_va, ts_va = X[mask], y[mask], ts[mask]

    model = load_latest_base(channel, db_path)
    pred = model.predict(X_va)

    return pd.DataFrame({
        "ts": ts_va.reset_index(drop=True),
        "actual": y_va.reset_index(drop=True).astype(float),
        "predicted": np.asarray(pred, dtype=float),
        "residual": np.asarray(pred, dtype=float) - y_va.reset_index(drop=True).astype(float).to_numpy(),
    })


def predict_holdout_all_channels(
    channels: tuple[str, ...] = ("dine_in", "delivery", "takeaway"),
    n_days: int = VALIDATION_DAYS,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    frames = []
    for ch in channels:
        df = predict_holdout(ch, n_days, db_path)
        df["channel"] = ch
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def summary_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Per-channel MAE/MAPE/bias/R² from a holdout frame produced above."""
    rows = []
    for ch, g in df.groupby("channel"):
        err = g["residual"].to_numpy()
        actual = g["actual"].to_numpy()
        mae = float(np.mean(np.abs(err)))
        bias = float(np.mean(err))
        ss_res = float(np.sum(err ** 2))
        ss_tot = float(np.sum((actual - actual.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        nz = actual > 0
        mape = float(np.mean(np.abs(err[nz]) / actual[nz])) if nz.any() else float("nan")
        rows.append({"channel": ch, "MAE": mae, "MAPE": mape, "Bias": bias, "R2": r2, "n": len(g)})
    return pd.DataFrame(rows).set_index("channel")
