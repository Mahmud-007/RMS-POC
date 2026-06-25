"""Cover-prediction service. Combines base + residual into the final forecast."""

from __future__ import annotations

from datetime import date


def predict_day(target: date, channel: str | None = None) -> dict:
    """Return hourly covers for the target date.

    If channel is None, returns predictions for all channels.
    Each entry contains: base_pred, residual_pred, final_pred.
    """
    raise NotImplementedError
