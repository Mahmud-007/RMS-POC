"""Cover-prediction service. Combines base + clipped residual into the final forecast."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import numpy as np

from app.eval.holdout import load_latest_base, load_latest_sgd
from app.features.feature_builder import (
    BASE_FEATURES,
    CONDITION_CODES,
    append_residual_features,
    build_inference_window,
    derive_reason_tags,
    residual_feature_names,
)

CHANNELS = ("dine_in", "delivery", "takeaway")
SERVICE_HOURS = list(range(11, 23))  # 11..22 inclusive
DB_PATH = Path("artifacts/rms.db")

# Scenario → feature overrides applied to the base feature row before predicting.
# Without these, the dropdown only affects the SGD residual (tiny shifts). With
# them, base LightGBM sees a coherent counterfactual condition and applies its
# learned coefficients (e.g. rain_mm × -0.06 on dine_in), producing visible shifts.
SCENARIO_OVERRIDES: dict[str, dict[str, float | int]] = {
    "rain_heavy":    {"rain_mm": 6.0, "condition_code": CONDITION_CODES["rain_heavy"]},
    "rain_light":    {"rain_mm": 1.5, "condition_code": CONDITION_CODES["rain_light"]},
    "event_holiday": {"is_holiday": 1},
    "event_local":   {"is_local_event": 1, "event_severity": 0.8},
    "promo":         {"is_promo": 1},
    # normal / no_show_group / other → residual-only, no base override
}


def _apply_scenario(X_base, reason_tag: str):
    """Return a feature frame with weather/event overrides for the chosen scenario."""
    if reason_tag not in SCENARIO_OVERRIDES:
        return X_base
    X_over = X_base.copy()
    for col, val in SCENARIO_OVERRIDES[reason_tag].items():
        if col in X_over.columns:
            X_over[col] = val
    return X_over


def _condition_code_for(temp: float, rain: float) -> int:
    """Mirror the generator/Open-Meteo condition mapping so overridden weather is
    schema-consistent with what the model trained on."""
    if rain > 0 and temp < 2:
        return CONDITION_CODES["snow"]
    if rain > 4:
        return CONDITION_CODES["rain_heavy"]
    if rain > 0:
        return CONDITION_CODES["rain_light"]
    if temp > 28:
        return CONDITION_CODES["hot"]
    if temp < 5:
        return CONDITION_CODES["cold"]
    return CONDITION_CODES["clear"]


def _apply_overrides(
    X_base,
    *,
    rain_mm: float | None = None,
    temp: float | None = None,
    is_holiday: bool | None = None,
    is_promo: bool | None = None,
    is_local_event: bool | None = None,
    event_severity: float | None = None,
):
    """Apply explicit manager overrides to the base feature row.

    Each field is only touched when the caller provides a value (not None), so the
    manager edits exactly what they disagree with and the live forecast stands for
    everything else. When rain/temp is overridden, condition_code is recomputed to
    stay consistent. Unlike the legacy scenario buckets, the value supplied IS the
    value used — no hidden magnitude substitution.
    """
    has_weather = rain_mm is not None or temp is not None
    has_event = any(
        v is not None for v in (is_holiday, is_promo, is_local_event, event_severity)
    )
    if not (has_weather or has_event):
        return X_base, False

    X = X_base.copy()
    if rain_mm is not None and "rain_mm" in X.columns:
        X["rain_mm"] = float(rain_mm)
    if temp is not None and "temp" in X.columns:
        X["temp"] = float(temp)
    if has_weather and "condition_code" in X.columns:
        X["condition_code"] = [
            _condition_code_for(float(t), float(r))
            for t, r in zip(X["temp"], X["rain_mm"])
        ]
    if is_holiday is not None and "is_holiday" in X.columns:
        X["is_holiday"] = int(bool(is_holiday))
    if is_promo is not None and "is_promo" in X.columns:
        X["is_promo"] = int(bool(is_promo))
    if is_local_event is not None and "is_local_event" in X.columns:
        X["is_local_event"] = int(bool(is_local_event))
    if event_severity is not None and "event_severity" in X.columns:
        X["event_severity"] = float(event_severity)
    return X, True


def _apply_weather(X_base, frame, hourly_weather: dict[int, dict] | None):
    """Populate the base feature row with fetched hourly weather (per service hour).

    `frame` carries the `ts` column so we can align each row to its hour.
    """
    if not hourly_weather:
        return X_base
    X_w = X_base.copy()
    hours = [ts.hour for ts in frame["ts"]]
    for col in ("rain_mm", "temp", "condition_code"):
        if col not in X_w.columns:
            continue
        X_w[col] = [
            hourly_weather.get(h, {}).get(col, X_w.iloc[i][col])
            for i, h in enumerate(hours)
        ]
    return X_w


def predict_day(
    target: date,
    channel: str | None = None,
    reason_tag: str = "normal",
    use_weather: bool = True,
    *,
    rain_mm: float | None = None,
    temp: float | None = None,
    is_holiday: bool | None = None,
    is_promo: bool | None = None,
    is_local_event: bool | None = None,
    event_severity: float | None = None,
    db_path: Path = DB_PATH,
) -> dict[str, list[dict]]:
    """Hourly forecast for `target`. Returns {channel: [{ts, hour, base, residual, final}]}.

    Feature construction, in order (each later layer overrides the earlier):
      1. `use_weather`: populate the row with the live Open-Meteo hourly forecast.
      2. `reason_tag` scenario buckets (legacy what-if; used by the Streamlit admin).
      3. Explicit manager overrides (`rain_mm`, `temp`, event flags) — the React UI
         path. Only fields the manager actually supplies are touched; everything else
         keeps the live forecast. The supplied value is used verbatim (no bucket
         magnitude substitution).

    When explicit overrides are supplied, the SGD reason tag is *derived* per-row from
    the resulting features (so the residual layer applies the matching learned effect).
    Otherwise the caller's `reason_tag` drives the SGD one-hot.
    """
    channels = (channel,) if channel else CHANNELS
    out: dict[str, list[dict]] = {}
    timestamps = [datetime.combine(target, time(h)) for h in SERVICE_HOURS]
    feature_cols = residual_feature_names(include_interactions=True)

    hourly_weather = None
    if use_weather:
        try:
            from app.integrations.weather import get_hourly_weather
            hourly_weather = get_hourly_weather(target)
        except Exception:
            hourly_weather = None

    for ch in channels:
        base = load_latest_base(ch, db_path)
        sgd = load_latest_sgd(ch, db_path)
        frame = build_inference_window(timestamps, ch, db_path, include_interactions=False)
        X_base = _apply_weather(frame[BASE_FEATURES], frame, hourly_weather)
        X_base = _apply_scenario(X_base, reason_tag)
        X_base, has_overrides = _apply_overrides(
            X_base,
            rain_mm=rain_mm, temp=temp,
            is_holiday=is_holiday, is_promo=is_promo,
            is_local_event=is_local_event, event_severity=event_severity,
        )
        base_pred = np.asarray(base.predict(X_base), dtype=float)

        # SGD residual sees the same row. When the manager supplied explicit overrides,
        # derive the reason tag from the resulting features so the residual matches;
        # otherwise honour the caller's reason_tag.
        sgd_reason = derive_reason_tags(X_base) if has_overrides else reason_tag
        X_sgd = append_residual_features(X_base, base_pred=base_pred, reason_tag=sgd_reason)
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
