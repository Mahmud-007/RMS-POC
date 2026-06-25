"""Feature builder.

Produces the feature vector consumed by both the LightGBM base and the SGD residual.
Keeping a single builder ensures the residual layer sees a strict superset of base inputs
(base_pred + reason-tag one-hots are appended on top).

Feature groups:
    calendar : dow, hour, month, is_weekend, is_holiday
    lags     : same_dow_4w_avg, same_hour_yesterday, rolling_7d_mean
    weather  : temp, rain_mm, condition_onehot
    events   : event_severity, promo_flag
    channel  : channel_onehot
    interactions (residual only): rain_x_channel, event_x_dinner, ...
"""

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class FeatureSpec:
    columns: list[str]
    categorical: list[str]


def build_features(
    ts: datetime,
    channel: str,
    history: pd.DataFrame,
    weather: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    """Build a single-row feature frame for the given (ts, channel)."""
    raise NotImplementedError


def build_training_frame(
    observations: pd.DataFrame,
    weather: pd.DataFrame,
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, FeatureSpec]:
    """Build the full (X, y, spec) tuple for base-model training."""
    raise NotImplementedError


def append_residual_features(
    base_features: pd.DataFrame,
    base_pred: float,
    reason_tag: str,
) -> pd.DataFrame:
    """Extend base feature row with base_pred + reason-tag one-hots for SGD input."""
    raise NotImplementedError
