"""Train LightGBM base models — one per channel — and register them."""

from __future__ import annotations


CHANNELS = ("dine_in", "delivery", "takeaway")


def run() -> dict[str, dict]:
    """Train one LightGBM booster per channel, log metrics, persist artifacts.

    Returns a dict mapping channel -> {version, mae, r2, path}.
    """
    raise NotImplementedError


if __name__ == "__main__":
    run()
