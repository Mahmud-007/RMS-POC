"""Backtest replay harness.

Walks chronologically through a held-out window, predicting then revealing actuals
and submitting corrections to the residual layer. Compares three variants:
    1. Naive same-dow-4w average
    2. LightGBM base only
    3. LightGBM + SGD residual (full system)

Outputs a rolling-MAE dataframe used by the dashboard's convergence chart.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def run(start: date, end: date) -> pd.DataFrame:
    """Replay predictions+corrections across the window, return per-day MAE per variant."""
    raise NotImplementedError


if __name__ == "__main__":
    from datetime import date
    df = run(date(2026, 4, 1), date(2026, 5, 31))
    print(df.tail())
