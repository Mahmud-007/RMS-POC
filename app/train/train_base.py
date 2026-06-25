"""Train LightGBM base models — one per channel — and register them."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from app.features.feature_builder import (
    CATEGORICAL_FEATURES,
    build_training_frame,
)
from app.models.base_lgbm import LgbmBase

CHANNELS = ("dine_in", "delivery", "takeaway")
DB_PATH = Path("artifacts/rms.db")
MODEL_DIR = Path("artifacts/models")
VALIDATION_DAYS = 28


def _time_split(ts, n_holdout_days: int = VALIDATION_DAYS):
    """Split by absolute timestamp — last n_holdout_days form the validation set."""
    cutoff = ts.max() - timedelta(days=n_holdout_days)
    train_mask = ts <= cutoff
    valid_mask = ts > cutoff
    return train_mask.to_numpy(), valid_mask.to_numpy()


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    bias = float(np.mean(err))
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    nonzero = y_true > 0
    mape = float(np.mean(np.abs(err[nonzero]) / y_true[nonzero])) if nonzero.any() else float("nan")
    return {"mae": mae, "mape": mape, "bias": bias, "r2": r2}


def _register(version: str, channel: str, metrics: dict[str, float], path: Path, db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO model_registry(version, type, trained_at, mae, r2, path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (version, f"lgbm_base_{channel}", datetime.now(UTC).isoformat(),
             metrics["mae"], metrics["r2"], str(path)),
        )
        conn.commit()


def train_channel(channel: str, db_path: Path = DB_PATH, model_dir: Path = MODEL_DIR) -> dict:
    X, y, ts, spec = build_training_frame(channel, db_path)
    train_mask, valid_mask = _time_split(ts)

    X_tr, X_va = X[train_mask], X[valid_mask]
    y_tr, y_va = y[train_mask].to_numpy(), y[valid_mask].to_numpy()

    model = LgbmBase()
    model.fit(X_tr, y_tr, X_va, y_va, categorical=CATEGORICAL_FEATURES)

    valid_pred = model.predict(X_va)
    metrics = _evaluate(y_va, valid_pred)

    version = f"v{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    model_path = model_dir / f"base_{version}_{channel}.txt"
    model.save(model_path)
    _register(version, channel, metrics, model_path, db_path)

    return {
        "channel": channel,
        "version": version,
        "path": str(model_path),
        "n_train": int(train_mask.sum()),
        "n_valid": int(valid_mask.sum()),
        "metrics": metrics,
        "top_features": dict(sorted(
            model.feature_importance().items(), key=lambda kv: kv[1], reverse=True,
        )[:5]),
    }


def run() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for ch in CHANNELS:
        out[ch] = train_channel(ch)
        m = out[ch]["metrics"]
        print(
            f"[{ch:9s}] mae={m['mae']:.3f}  mape={m['mape']:.3f}  bias={m['bias']:+.3f}  "
            f"r2={m['r2']:.3f}  n_train={out[ch]['n_train']}  n_valid={out[ch]['n_valid']}"
        )
        print(f"           top features: {out[ch]['top_features']}")
    return out


if __name__ == "__main__":
    run()
