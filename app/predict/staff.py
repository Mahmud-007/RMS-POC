"""Staffing derivation. Rule-based, driven by predicted covers and per-role throughput."""

from __future__ import annotations

import math
import sqlite3
from datetime import date
from pathlib import Path

from app.predict import covers as covers_svc

DB_PATH = Path("artifacts/rms.db")
CHANNELS = ("dine_in", "delivery", "takeaway")
SERVICE_HOURS = list(range(11, 23))

# Which channels each role's workload depends on.
ROLE_CHANNEL_MAP: dict[str, list[str]] = {
    "server":     ["dine_in"],
    "host":       ["dine_in"],
    "line_cook":  ["dine_in", "delivery", "takeaway"],
    "dishwasher": ["dine_in", "delivery", "takeaway"],
}


def _load_throughput(db_path: Path) -> dict[str, dict]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT role, covers_per_hour, floor_min FROM staff_throughput"
        ).fetchall()
    return {r[0]: {"cph": float(r[1]), "floor": int(r[2])} for r in rows}


def predict_day(target: date, db_path: Path = DB_PATH) -> dict:
    """Per-hour headcount per role + daily totals."""
    forecast = covers_svc.predict_day(target, db_path=db_path)
    throughput = _load_throughput(db_path)

    # Index covers by (hour, channel) for quick lookup
    by_hour_channel: dict[int, dict[str, float]] = {h: {} for h in SERVICE_HOURS}
    for ch, rows in forecast.items():
        for row in rows:
            by_hour_channel[row["hour"]][ch] = row["final_pred"]

    hourly: list[dict] = []
    role_totals = {role: 0 for role in throughput}
    for h in SERVICE_HOURS:
        covers_h = by_hour_channel.get(h, {})
        hour_block = {
            "hour": h,
            "covers": {ch: float(covers_h.get(ch, 0.0)) for ch in CHANNELS},
            "covers_total": float(sum(covers_h.values())),
            "headcount": {},
        }
        for role, info in throughput.items():
            scope = ROLE_CHANNEL_MAP.get(role, list(CHANNELS))
            covers_in_scope = sum(covers_h.get(ch, 0.0) for ch in scope)
            need = math.ceil(covers_in_scope / info["cph"])
            hc = max(info["floor"], int(need))
            hour_block["headcount"][role] = hc
            role_totals[role] += hc
        hourly.append(hour_block)

    return {
        "target": target.isoformat(),
        "hourly": hourly,
        "person_hours": role_totals,
        "peak_headcount": {
            role: max(h["headcount"][role] for h in hourly) for role in throughput
        },
    }


def pack_shifts(
    needed_by_hour: dict[int, dict[str, int]],
    block_sizes: tuple[int, ...] = (4, 8),
) -> list[dict]:
    """Greedy shift packing — currently a forward-fill placeholder.

    Returns a list of shifts: {role, start_hour, end_hour, count}. Each shift covers
    a contiguous block of hours during which the role's required headcount is constant.
    Real optimization (mixed integer programming) is future work; this packer is
    enough to drive the dashboard's "suggested schedule" view.
    """
    out: list[dict] = []
    if not needed_by_hour:
        return out
    hours = sorted(needed_by_hour.keys())
    roles = sorted({r for h in needed_by_hour.values() for r in h.keys()})
    for role in roles:
        current_count = None
        block_start = None
        for h in hours:
            count = needed_by_hour[h].get(role, 0)
            if count != current_count:
                if current_count is not None and current_count > 0:
                    out.append({
                        "role": role,
                        "start_hour": block_start,
                        "end_hour": h - 1,
                        "count": current_count,
                    })
                current_count = count
                block_start = h
        if current_count is not None and current_count > 0:
            out.append({
                "role": role,
                "start_hour": block_start,
                "end_hour": hours[-1],
                "count": current_count,
            })
    return out
