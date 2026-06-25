"""Ingredient order recommendations.

Forecasts covers across the lead-time horizon, applies historical dish mix via the
recipe BOM, subtracts current stock and incoming deliveries, and clips each line
by shelf-life × usage rate.
"""

from __future__ import annotations

from datetime import date


def predict_orders(start: date, end: date) -> list[dict]:
    """Per-ingredient order quantity for the given window."""
    raise NotImplementedError
