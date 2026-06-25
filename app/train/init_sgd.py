"""Warm-start the SGD residual layer from residuals against the latest base model."""

from __future__ import annotations


def run() -> dict:
    """Compute residuals on training data, fit SGD as a warm start, persist state."""
    raise NotImplementedError


if __name__ == "__main__":
    run()
