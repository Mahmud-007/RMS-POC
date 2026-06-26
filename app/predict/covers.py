"""Cover-prediction service. Combines base + clipped residual into the final forecast."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import numpy as np

from app.eval.holdout import load_latest_base, load_latest_sgd
from app.features.feature_builder import (
    BASE_FEATURES,
    append_residual_features,
    build_inference_window,
    residual_feature_names,
)

CHANNELS = ("dine_in", "delivery", "takeaway")
SERVICE_HOURS = list(range(11, 23))  # 11..22 inclusive
DB_PATH = Path("artifacts/rms.db")


def predict_day(
    target: date,
    channel: str | None = None,
    reason_tag: str = "normal",
    db_path: Path = DB_PATH,
) -> dict[str, list[dict]]:
    """Hourly forecast for `target`. Returns {channel: [{ts, hour, base, residual, final}]}.

    `reason_tag` lets callers explore conditional forecasts (e.g. what does the model
    predict if we tell it tomorrow will be `rain_heavy`?). Defaults to `normal`.
    """
    channels = (channel,) if channel else CHANNELS
    out: dict[str, list[dict]] = {}
    timestamps = [datetime.combine(target, time(h)) for h in SERVICE_HOURS]
    feature_cols = residual_feature_names(include_interactions=True)

    for ch in channels:
        base = load_latest_base(ch, db_path)
        sgd = load_latest_sgd(ch, db_path)
        frame = build_inference_window(timestamps, ch, db_path, include_interactions=False)
        X_base = frame[BASE_FEATURES]
        base_pred = np.asarray(base.predict(X_base), dtype=float)

        X_sgd = append_residual_features(X_base, base_pred=base_pred, reason_tag=reason_tag)
        X_sgd = X_sgd[feature_cols]

        if sgd is not None and sgd.fitted:
            res_raw = np.asarray(sgd.predict(X_sgd), dtype=float)
            cap = np.abs(base_pred) * sgd.clip_fraction
            res_pred = np.clip(res_raw, -cap, cap)
        else:
            res_raw = np.zeros_like(base_pred)
            res_pred = res_raw

        final = np.maximum(0.0, base_pred + res_pred)

        out[ch] = [
            {
                "ts": ts.isoformat(),
                "hour": int(h),
                "base_pred": float(bp),
                "residual_raw": float(rr),
                "residual_pred": float(rp),
                "final_pred": float(fp),
            }
            for ts, h, bp, rr, rp, fp in zip(
                frame["ts"].tolist(), SERVICE_HOURS,
                base_pred, res_raw, res_pred, final,
            )
        ]
    return out


def predict_daily_totals(
    start: date,
    end: date,
    channel: str | None = None,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Daily total covers per channel across [start, end]. Used by the orders module."""
    from datetime import timedelta
    rows: list[dict] = []
    d = start
    while d <= end:
        day = predict_day(d, channel=channel, db_path=db_path)
        for ch, hours in day.items():
            rows.append({
                "date": d.isoformat(),
                "channel": ch,
                "covers": float(sum(h["final_pred"] for h in hours)),
            })
        d += timedelta(days=1)
    return rows
