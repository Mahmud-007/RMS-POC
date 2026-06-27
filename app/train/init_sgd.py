"""Warm-start the SGD residual layer from residuals against the latest base model.

Run from repo root:
    python -m app.train.init_sgd
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.eval.holdout import load_latest_base
from app.features.feature_builder import (
    append_residual_features,
    build_training_frame,
    derive_reason_tags,
    residual_feature_names,
)
from app.models.residual_sgd import SgdResidual

CHANNELS = ("dine_in", "delivery", "takeaway")
DB_PATH = Path("artifacts/rms.db")
MODEL_DIR = Path("artifacts/models")


def _register(version: str, channel: str, mae: float, path: Path, db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO model_registry(version, type, trained_at, mae, r2, path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (version, f"sgd_residual_{channel}", datetime.now(UTC).isoformat(),
             mae, None, str(path)),
        )
        conn.commit()


def init_for_channel(channel: str, db_path: Path = DB_PATH, model_dir: Path = MODEL_DIR) -> dict:
    X_base, y, ts, _spec = build_training_frame(channel, db_path)
    base_model = load_latest_base(channel, db_path)
    base_pred = base_model.predict(X_base)
    residual = y.to_numpy().astype(float) - np.asarray(base_pred, dtype=float)

    # Derive a reason tag per row from weather/events so each tag's coefficient
    # gets real signal during warm-start (otherwise non-"normal" tags stay at zero).
    derived_tags = derive_reason_tags(X_base)
    X_sgd = append_residual_features(X_base, base_pred=base_pred, reason_tag=derived_tags)
    feature_names = residual_feature_names(include_interactions=True)
    X_sgd = X_sgd[feature_names]

    sgd = SgdResidual()
    sgd.set_feature_names(feature_names)
    sgd.warm_start(X_sgd, residual)

    # Evaluate warm-start fit on the same data
    pred = sgd.predict(X_sgd)
    warm_mae = float(np.mean(np.abs(pred - residual)))

    version = f"v{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    path = model_dir / f"sgd_{version}_{channel}.pkl"
    sgd.save(path)
    _register(version, channel, warm_mae, path, db_path)

    tag_counts: dict[str, int] = {}
    for t in derived_tags:
        tag_counts[t] = tag_counts.get(t, 0) + 1

    return {
        "channel": channel,
        "version": version,
        "path": str(path),
        "n_train": int(len(X_sgd)),
        "warm_mae": warm_mae,
        "residual_mean": float(np.mean(residual)),
        "residual_std": float(np.std(residual)),
        "tag_distribution": tag_counts,
        "top_coefs": dict(sorted(
            sgd.coefficients.items(), key=lambda kv: abs(kv[1]), reverse=True,
        )[:5]),
        "reason_coefs": {
            k: v for k, v in sgd.coefficients.items() if k.startswith("reason_")
        },
    }


def run() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for ch in CHANNELS:
        out[ch] = init_for_channel(ch)
        r = out[ch]
        print(
            f"[{ch:9s}] warm_mae={r['warm_mae']:.3f}  res_mean={r['residual_mean']:+.3f}  "
            f"res_std={r['residual_std']:.3f}  n={r['n_train']}"
        )
        print(f"           top coefs: {r['top_coefs']}")
        print(f"           reason coefs: {r['reason_coefs']}")
        print(f"           tag dist: {r['tag_distribution']}")
    return out


if __name__ == "__main__":
    run()
