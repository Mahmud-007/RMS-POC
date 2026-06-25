"""LightGBM base model wrapper. One booster per channel."""

import lightgbm as lgb
import numpy as np


DEFAULT_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
}


class LgbmBase:
    def __init__(self, params: dict | None = None) -> None:
        self.params = params or DEFAULT_PARAMS
        self.booster: lgb.Booster | None = None

    def fit(self, X: np.ndarray, y: np.ndarray, valid_X: np.ndarray | None = None, valid_y: np.ndarray | None = None) -> None:
        raise NotImplementedError

    def predict(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def save(self, path: str) -> None:
        raise NotImplementedError

    def load(self, path: str) -> None:
        raise NotImplementedError

    def feature_importance(self) -> dict[str, float]:
        raise NotImplementedError
