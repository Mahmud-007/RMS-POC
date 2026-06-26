"""SGDRegressor-based residual model. True online learning via partial_fit."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import SGDRegressor
from sklearn.preprocessing import StandardScaler


class SgdResidual:
    """Online linear residual learner.

    Lifecycle:
        1. `warm_start(X, residual)` — initial fit on historical residuals after each
           base retrain. Resets coefficients and resets `n_updates` to that batch size.
        2. `update(X, residual)` — per-correction `partial_fit` (one or more rows).
        3. `predict(X)` — returns the residual prediction (uncapped). Callers cap.

    A StandardScaler is fit during warm_start and reused for every later predict/update,
    because SGD is scale-sensitive.
    """

    def __init__(
        self,
        learning_rate: str = "invscaling",
        eta0: float = 0.01,
        alpha: float = 1e-4,
        clip_fraction: float = 0.5,
    ) -> None:
        self.model = SGDRegressor(
            loss="squared_error",
            penalty="l2",
            learning_rate=learning_rate,
            eta0=eta0,
            alpha=alpha,
            warm_start=True,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.clip_fraction = clip_fraction
        self._feature_names: list[str] = []
        self._n_updates: int = 0
        self._fitted: bool = False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def set_feature_names(self, names: list[str]) -> None:
        self._feature_names = list(names)

    # ------------------------------------------------------------------
    # Core ops
    # ------------------------------------------------------------------

    def warm_start(self, X: pd.DataFrame | np.ndarray, residual: np.ndarray | pd.Series) -> None:
        X_arr = self._to_array(X)
        if not self._feature_names and isinstance(X, pd.DataFrame):
            self._feature_names = list(X.columns)
        res = np.asarray(residual, dtype=float).ravel()
        self.scaler = StandardScaler().fit(X_arr)
        Xs = self.scaler.transform(X_arr)
        # Re-init model to wipe any prior fit, then run fit() for an OLS-like warm start.
        self.model = SGDRegressor(
            loss="squared_error", penalty="l2",
            learning_rate=self.model.learning_rate, eta0=self.model.eta0,
            alpha=self.model.alpha, warm_start=True, random_state=42,
            max_iter=200, tol=1e-4,
        )
        self.model.fit(Xs, res)
        self._n_updates = len(X_arr)
        self._fitted = True

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if not self._fitted:
            return np.zeros(len(X), dtype=float)
        X_arr = self._to_array(X)
        Xs = self.scaler.transform(X_arr)
        return self.model.predict(Xs)

    def update(self, X: pd.DataFrame | np.ndarray, residual: np.ndarray | pd.Series) -> None:
        if not self._fitted:
            raise RuntimeError("warm_start must be called before update")
        X_arr = self._to_array(X)
        res = np.asarray(residual, dtype=float).ravel()
        Xs = self.scaler.transform(X_arr)
        self.model.partial_fit(Xs, res)
        self._n_updates += len(X_arr)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self._feature_names,
                "n_updates": self._n_updates,
                "clip_fraction": self.clip_fraction,
                "fitted": self._fitted,
            },
            path,
        )

    def load(self, path: str | Path) -> None:
        state = joblib.load(path)
        self.model = state["model"]
        self.scaler = state["scaler"]
        self._feature_names = state["feature_names"]
        self._n_updates = int(state["n_updates"])
        self.clip_fraction = float(state["clip_fraction"])
        self._fitted = bool(state.get("fitted", True))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def coefficients(self) -> dict[str, float]:
        if not self._feature_names or not hasattr(self.model, "coef_"):
            return {}
        return dict(zip(self._feature_names, self.model.coef_.tolist()))

    @property
    def intercept(self) -> float:
        if not hasattr(self.model, "intercept_"):
            return 0.0
        ic = self.model.intercept_
        return float(ic[0] if hasattr(ic, "__len__") else ic)

    @property
    def n_updates(self) -> int:
        return self._n_updates

    @property
    def fitted(self) -> bool:
        return self._fitted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_array(X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            return X.to_numpy(dtype=float)
        return np.asarray(X, dtype=float)
