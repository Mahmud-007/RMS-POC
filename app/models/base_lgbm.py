"""LightGBM base model wrapper. One booster per channel."""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

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
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.booster: lgb.Booster | None = None
        self._feature_names: list[str] = []
        self._categorical: list[str] = []

    def fit(
        self,
        X: pd.DataFrame,
        y: np.ndarray | pd.Series,
        valid_X: pd.DataFrame | None = None,
        valid_y: np.ndarray | pd.Series | None = None,
        categorical: list[str] | None = None,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 30,
    ) -> None:
        self._feature_names = list(X.columns)
        self._categorical = list(categorical or [])
        train_set = lgb.Dataset(
            X, label=y,
            feature_name=self._feature_names,
            categorical_feature=self._categorical or "auto",
            free_raw_data=False,
        )
        valid_sets = [train_set]
        valid_names = ["train"]
        callbacks = [lgb.log_evaluation(period=0)]
        if valid_X is not None and valid_y is not None:
            val_set = lgb.Dataset(
                valid_X, label=valid_y, reference=train_set,
                feature_name=self._feature_names,
                categorical_feature=self._categorical or "auto",
                free_raw_data=False,
            )
            valid_sets.append(val_set)
            valid_names.append("valid")
            callbacks.append(lgb.early_stopping(early_stopping_rounds, verbose=False))

        self.booster = lgb.train(
            self.params,
            train_set,
            num_boost_round=num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.booster is None:
            raise RuntimeError("Model not fitted")
        return self.booster.predict(X[self._feature_names], num_iteration=self.booster.best_iteration)

    def save(self, path: str | Path) -> None:
        if self.booster is None:
            raise RuntimeError("Model not fitted")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.booster.save_model(str(path))

    def load(self, path: str | Path) -> None:
        self.booster = lgb.Booster(model_file=str(path))
        self._feature_names = self.booster.feature_name()

    def feature_importance(self, importance_type: str = "gain") -> dict[str, float]:
        if self.booster is None:
            raise RuntimeError("Model not fitted")
        imps = self.booster.feature_importance(importance_type=importance_type)
        return dict(zip(self._feature_names, imps.tolist()))
