"""Backtest replay harness.

Replays the last `n_days` of the dataset chronologically. For each hour we compute
three forecast variants:

    naive   = same-DOW 4-week average      (no model)
    base    = LightGBM base prediction     (no online correction)
    hybrid  = base + clipped SGD residual  (online corrected each step)

A fresh SgdResidual is warm-started on data *before* the backtest window so the
replay genuinely measures the online layer's ability to adapt. After every hour we
"reveal" the actual cover count and feed it back via `sgd.update`, mirroring the
production correction loop.

The returned DataFrame drives the convergence chart on the dashboard's Model Health
page and the FEAT-013 demo.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.eval.holdout import load_latest_base
from app.features.feature_builder import (
    append_residual_features,
    build_training_frame,
    residual_feature_names,
)
from app.models.residual_sgd import SgdResidual

CHANNELS = ("dine_in", "delivery", "takeaway")
DB_PATH = Path("artifacts/rms.db")
DEFAULT_DAYS = 60
ROLLING_WINDOW_DAYS = 7


def _replay_channel(channel: str, n_days: int, db_path: Path) -> pd.DataFrame:
    X, y, ts, _spec = build_training_frame(channel, db_path)
    ts = ts.reset_index(drop=True)
    X = X.reset_index(drop=True)
    y = y.reset_index(drop=True)

    cutoff = ts.max() - timedelta(days=n_days)
    pre_mask = (ts <= cutoff).to_numpy()
    bt_mask = (ts > cutoff).to_numpy()
    if not bt_mask.any():
        return pd.DataFrame()

    base = load_latest_base(channel, db_path)
    base_pred_all = np.asarray(base.predict(X), dtype=float)

    # Warm-start a FRESH SGD on pre-backtest data only.
    X_pre = X[pre_mask]
    y_pre = y[pre_mask].to_numpy()
    base_pre = base_pred_all[pre_mask]
    X_sgd_pre = append_residual_features(X_pre, base_pred=base_pre, reason_tag="normal")
    feature_cols = residual_feature_names(include_interactions=True)
    X_sgd_pre = X_sgd_pre[feature_cols]

    sgd = SgdResidual()
    sgd.set_feature_names(feature_cols)
    sgd.warm_start(X_sgd_pre, y_pre - base_pre)

    # Backtest window
    X_bt = X[bt_mask].reset_index(drop=True)
    ts_bt = ts[bt_mask].reset_index(drop=True)
    y_bt = y[bt_mask].reset_index(drop=True).to_numpy()
    base_bt = base_pred_all[bt_mask]

    hybrid_preds = np.zeros(len(X_bt), dtype=float)
    for i in range(len(X_bt)):
        X_one = X_bt.iloc[[i]]
        bp = float(base_bt[i])
        X_sgd_one = append_residual_features(X_one, base_pred=np.array([bp]), reason_tag="normal")
        X_sgd_one = X_sgd_one[feature_cols]

        res_raw = float(sgd.predict(X_sgd_one)[0])
        cap = abs(bp) * sgd.clip_fraction
        res_clipped = float(np.clip(res_raw, -cap, cap))
        hybrid_preds[i] = max(0.0, bp + res_clipped)

        # Reveal + online update
        actual = float(y_bt[i])
        target = actual - bp
        target_clipped = float(np.clip(target, -cap, cap))
        sgd.update(X_sgd_one, np.array([target_clipped]))

    df = pd.DataFrame({
        "ts": ts_bt,
        "date": ts_bt.dt.date,
        "actual": y_bt,
        "naive_pred": X_bt["dow_4w_mean"].to_numpy(),
        "base_pred": base_bt,
        "hybrid_pred": hybrid_preds,
    })
    df["channel"] = channel
    return df


def run(n_days: int = DEFAULT_DAYS, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return long-form DataFrame: date, channel, variant, mae, rolling_mae."""
    frames = []
    for ch in CHANNELS:
        df = _replay_channel(ch, n_days, db_path)
        if df.empty:
            continue
        for variant in ("naive", "base", "hybrid"):
            df[f"{variant}_abs_err"] = (df[f"{variant}_pred"] - df["actual"]).abs()
        daily = df.groupby("date", as_index=False)[
            ["naive_abs_err", "base_abs_err", "hybrid_abs_err"]
        ].mean()
        for variant in ("naive", "base", "hybrid"):
            sub = pd.DataFrame({
                "date": daily["date"],
                "channel": ch,
                "variant": variant,
                "mae": daily[f"{variant}_abs_err"],
            })
            sub["rolling_mae"] = sub["mae"].rolling(window=ROLLING_WINDOW_DAYS, min_periods=1).mean()
            frames.append(sub)
    return pd.concat(frames, ignore_index=True)


def summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate MAE per (channel, variant) over the whole backtest window."""
    return (
        df.groupby(["channel", "variant"], as_index=False)["mae"]
          .mean()
          .pivot(index="channel", columns="variant", values="mae")
          [["naive", "base", "hybrid"]]
    )


if __name__ == "__main__":
    df = run()
    print(summary(df))
