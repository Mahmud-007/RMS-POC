"""SGDRegressor-based residual model. True online learning via partial_fit."""

import numpy as np
from sklearn.linear_model import SGDRegressor


class SgdResidual:
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
        )
        self.clip_fraction = clip_fraction
        self._feature_names: list[str] = []
        self._n_updates: int = 0

    def warm_start(self, X: np.ndarray, residual: np.ndarray) -> None:
        raise NotImplementedError

    def predict(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def update(self, X: np.ndarray, residual: np.ndarray) -> None:
        raise NotImplementedError

    def save(self, path: str) -> None:
        raise NotImplementedError

    def load(self, path: str) -> None:
        raise NotImplementedError

    @property
    def coefficients(self) -> dict[str, float]:
        if not self._feature_names or not hasattr(self.model, "coef_"):
            return {}
        return dict(zip(self._feature_names, self.model.coef_.tolist()))

    @property
    def n_updates(self) -> int:
        return self._n_updates
