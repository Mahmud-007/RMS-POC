"""Correction endpoint. Drives the online learning loop (SGD partial_fit)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.eval.holdout import load_latest_base, load_latest_sgd
from app.features.feature_builder import (
    BASE_FEATURES,
    REASON_TAGS,
    append_residual_features,
    build_inference_window,
    residual_feature_names,
)

DB_PATH = Path("artifacts/rms.db")

router = APIRouter()

ReasonTag = Literal[
    "rain_heavy",
    "rain_light",
    "event_local",
    "event_holiday",
    "promo",
    "no_show_group",
    "normal",
    "other",
]


class Correction(BaseModel):
    ts: datetime
    channel: Literal["dine_in", "delivery", "takeaway"]
    actual: float = Field(ge=0)
    reason_tag: ReasonTag = "normal"


class CorrectionResult(BaseModel):
    base_pred: float
    residual_pred_before: float
    residual_pred_after: float
    actual: float
    target_residual: float
    target_residual_clipped: float
    n_updates: int
    model_version: str


def _sgd_path_and_version(channel: str, db_path: Path = DB_PATH) -> tuple[str, str]:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT version, path FROM model_registry WHERE type = ? "
            "ORDER BY trained_at DESC LIMIT 1",
            (f"sgd_residual_{channel}",),
        ).fetchone()
    if row is None:
        raise HTTPException(404, f"No SGD model registered for channel={channel}")
    return row[1], row[0]


def _log_correction(payload: Correction, predicted: float, db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO corrections "
            "(ts, channel, predicted, actual, reason_tag, weather_flag, event_flag) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payload.ts.isoformat(), payload.channel, float(predicted), float(payload.actual),
             payload.reason_tag, None, None),
        )
        conn.commit()


@router.post("", response_model=CorrectionResult)
def submit_correction(payload: Correction) -> CorrectionResult:
    if payload.reason_tag not in REASON_TAGS:
        raise HTTPException(400, f"unknown reason_tag: {payload.reason_tag}")

    base = load_latest_base(payload.channel)
    sgd = load_latest_sgd(payload.channel)
    if sgd is None or not sgd.fitted:
        raise HTTPException(409, "SGD residual not initialized — run app.train.init_sgd")

    # Build base features for the single ts
    frame = build_inference_window([payload.ts], payload.channel, DB_PATH, include_interactions=False)
    X_base = frame[BASE_FEATURES]
    base_pred = float(base.predict(X_base)[0])

    # SGD features with the manager-supplied reason tag
    X_sgd = append_residual_features(X_base, base_pred=np.array([base_pred]), reason_tag=payload.reason_tag)
    X_sgd = X_sgd[residual_feature_names(include_interactions=True)]

    res_before = float(sgd.predict(X_sgd)[0])

    # Compute residual target, clip to ±50% of base
    target = float(payload.actual) - base_pred
    cap = abs(base_pred) * sgd.clip_fraction
    target_clipped = float(np.clip(target, -cap, cap))

    # Online update + persist
    sgd.update(X_sgd, np.array([target_clipped]))
    path, version = _sgd_path_and_version(payload.channel)
    sgd.save(path)

    res_after = float(sgd.predict(X_sgd)[0])
    _log_correction(payload, base_pred + res_after, DB_PATH)

    return CorrectionResult(
        base_pred=base_pred,
        residual_pred_before=res_before,
        residual_pred_after=res_after,
        actual=float(payload.actual),
        target_residual=target,
        target_residual_clipped=target_clipped,
        n_updates=sgd.n_updates,
        model_version=version,
    )
