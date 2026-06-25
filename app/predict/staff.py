"""Staffing derivation. Rule-based, driven by predicted covers and per-role throughput."""

from __future__ import annotations

from datetime import date


def predict_day(target: date) -> dict:
    """Per-hour, per-role staffing recommendation + packed shift blocks."""
    raise NotImplementedError


def pack_shifts(needed_by_hour: dict[int, dict[str, int]], block_sizes: tuple[int, ...] = (4, 8)) -> list[dict]:
    """Greedy packing of hourly headcount into shift blocks."""
    raise NotImplementedError
