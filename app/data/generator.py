"""Synthetic data generator.

Produces ~12–18 months of hourly observations with known ground-truth drivers:
    - Day-of-week and hour-of-day curves (multiplicative)
    - Weather sensitivity that differs by channel (rain hurts dine-in, helps delivery)
    - Holidays and local events
    - Promo flags
    - One scripted regime shift (delivery base volume doubles from REGIME_SHIFT_DAY)
    - ~10% multiplicative noise

Ground-truth coefficients are kept at the top of the file so the eval harness
(`app/eval/backtest.py`) can later compare what the model learned against the
real drivers we injected.

Run from repo root:
    python -m app.data.generator
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

DB_PATH = Path("artifacts/rms.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# --------------------------------------------------------------------------------------
# Ground-truth coefficients (the values we want the trained model to recover)
# --------------------------------------------------------------------------------------

START_DATE = date(2025, 3, 25)
END_DATE = date(2026, 6, 25)  # inclusive — no synthetic data beyond "today"
OPEN_HOUR = 11
CLOSE_HOUR = 23  # exclusive — service hours are 11..22

CHANNELS = ("dine_in", "delivery", "takeaway")

# Base hourly covers per channel (peak-hour reference, before any multipliers)
CHANNEL_BASE = {"dine_in": 22.0, "delivery": 10.0, "takeaway": 6.0}

# Per-channel sensitivity to 1mm of rain (multiplicative offset per mm)
RAIN_COEF = {"dine_in": -0.06, "delivery": +0.03, "takeaway": -0.01}

# Day-of-week multiplier (Mon=0 ... Sun=6)
DOW_MULT = np.array([0.85, 0.80, 0.85, 0.95, 1.20, 1.40, 1.25])

# Hour-of-day curve — two-peak service (lunch + dinner)
HOUR_CURVE = {
    11: 0.35, 12: 0.85, 13: 1.00, 14: 0.60, 15: 0.30, 16: 0.25,
    17: 0.45, 18: 0.85, 19: 1.10, 20: 1.05, 21: 0.75, 22: 0.40,
}

# Holiday and event multipliers
HOLIDAY_MULT = 1.45
EVENT_LOCAL_MULT = 1.25
PROMO_MULT = 1.18

# Regime shift: delivery volume doubles from this day onward
REGIME_SHIFT_DAY = 200
REGIME_SHIFT_FACTOR = {"dine_in": 1.0, "delivery": 2.0, "takeaway": 1.0}

NOISE_SIGMA = 0.10  # multiplicative noise

# Static seeds
INGREDIENTS = [
    # (name, unit, shelf_life_days, lead_time_days, stock)
    ("Tomato",       "kg",   5,  1, 15.0),
    ("Onion",        "kg",  14,  2, 20.0),
    ("Garlic",       "kg",  21,  3,  4.0),
    ("Chicken",      "kg",   3,  1, 12.0),
    ("Beef",         "kg",   4,  2,  8.0),
    ("Pasta",        "kg",  180, 7, 30.0),
    ("Rice",         "kg",  365, 7, 40.0),
    ("Olive Oil",    "L",   365, 5, 10.0),
    ("Cheese",       "kg",  10,  2,  8.0),
    ("Basil",        "kg",   3,  1,  0.5),
    ("Flour",        "kg",  120, 7, 25.0),
    ("Lemon",        "kg",  14,  2,  3.0),
]

MENU_ITEMS = [
    # item_id, name, recipe = {ingredient_name: qty_per_cover}
    (1, "Margherita Pizza",   {"Flour": 0.18, "Tomato": 0.10, "Cheese": 0.08, "Basil": 0.005, "Olive Oil": 0.01}),
    (2, "Spaghetti Bolognese",{"Pasta": 0.12, "Beef": 0.12, "Tomato": 0.10, "Onion": 0.03, "Garlic": 0.005}),
    (3, "Chicken Caesar",     {"Chicken": 0.15, "Cheese": 0.03, "Lemon": 0.02, "Olive Oil": 0.01}),
    (4, "Risotto",            {"Rice": 0.10, "Onion": 0.04, "Cheese": 0.04, "Olive Oil": 0.01}),
    (5, "Burger",             {"Beef": 0.18, "Onion": 0.02, "Cheese": 0.03, "Flour": 0.08}),
    (6, "Garlic Bread",       {"Flour": 0.08, "Garlic": 0.01, "Olive Oil": 0.01}),
    (7, "Lemon Chicken",      {"Chicken": 0.18, "Lemon": 0.04, "Garlic": 0.005, "Olive Oil": 0.01}),
    (8, "Penne Arrabbiata",   {"Pasta": 0.12, "Tomato": 0.10, "Garlic": 0.005, "Olive Oil": 0.01}),
]

MIX_BASE = {1: 0.20, 2: 0.18, 3: 0.14, 4: 0.10, 5: 0.16, 6: 0.08, 7: 0.08, 8: 0.06}

STAFF_THROUGHPUT = [
    # (role, covers_per_hour, floor_min)
    ("server",      12, 2),
    ("line_cook",   15, 2),
    ("dishwasher",  40, 1),
    ("host",        60, 1),
]

# Holidays we'll inject (month, day)
HOLIDAYS = [
    (1, 1), (2, 14), (3, 17), (5, 1), (7, 4), (10, 31),
    (11, 28), (12, 24), (12, 25), (12, 31),
]


# --------------------------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------------------------

def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text())


def _date_range(start: date, end: date) -> list[date]:
    """Inclusive day list from `start` to `end`."""
    if end < start:
        raise ValueError(f"end ({end}) precedes start ({start})")
    n = (end - start).days + 1
    return [start + timedelta(days=i) for i in range(n)]


# --------------------------------------------------------------------------------------
# Weather + events
# --------------------------------------------------------------------------------------

def _generate_weather(days: list[date], rng: np.random.Generator) -> list[tuple]:
    """Hourly weather: seasonal temp sinusoid + daily cycle + storm bursts."""
    rows: list[tuple] = []
    for d in days:
        # Seasonal: peak temp around day 200 (mid-summer for a northern-hemisphere start)
        day_of_year = d.timetuple().tm_yday
        seasonal_temp = 15 + 12 * math.sin(2 * math.pi * (day_of_year - 110) / 365)

        # Decide if it's a rainy day (~25% baseline, higher in winter)
        rain_prob = 0.18 + 0.20 * max(0.0, -math.sin(2 * math.pi * (day_of_year - 110) / 365))
        is_rainy = rng.random() < rain_prob
        rain_hours = set()
        if is_rainy:
            n_rain_hours = int(rng.integers(2, 8))
            start_h = int(rng.integers(0, 24 - n_rain_hours))
            rain_hours = set(range(start_h, start_h + n_rain_hours))

        for h in range(24):
            # Daily cycle: cooler at night, warmer mid-afternoon
            diurnal = 5 * math.sin(2 * math.pi * (h - 9) / 24)
            temp = seasonal_temp + diurnal + float(rng.normal(0, 1.5))
            rain_mm = float(rng.gamma(2.0, 1.5)) if h in rain_hours else 0.0
            if rain_mm > 0 and temp < 2:
                condition = "snow"
            elif rain_mm > 4:
                condition = "rain_heavy"
            elif rain_mm > 0:
                condition = "rain_light"
            elif temp > 28:
                condition = "hot"
            elif temp < 5:
                condition = "cold"
            else:
                condition = "clear"
            rows.append((d.isoformat(), h, round(temp, 2), round(rain_mm, 2), condition))
    return rows


def _generate_events(days: list[date], rng: np.random.Generator) -> list[tuple]:
    rows: list[tuple] = []
    for d in days:
        # Fixed holidays
        if (d.month, d.day) in HOLIDAYS:
            rows.append((d.isoformat(), "holiday", 1.0))
        # Random local events ~5% of days
        if rng.random() < 0.05:
            severity = float(rng.uniform(0.5, 1.0))
            rows.append((d.isoformat(), "local_event", round(severity, 2)))
        # Promo days ~10%
        if rng.random() < 0.10:
            rows.append((d.isoformat(), "promo", 1.0))
    return rows


# --------------------------------------------------------------------------------------
# Observations (hourly × channel)
# --------------------------------------------------------------------------------------

def _build_event_lookup(events: list[tuple]) -> dict[str, dict[str, float]]:
    """date -> {event_type: severity}."""
    out: dict[str, dict[str, float]] = {}
    for d, t, sev in events:
        out.setdefault(d, {})[t] = sev
    return out


def _build_weather_lookup(weather: list[tuple]) -> dict[tuple[str, int], dict]:
    return {(d, h): {"temp": t, "rain_mm": r, "condition": c} for d, h, t, r, c in weather}


def _generate_observations(
    days: list[date],
    weather_lookup: dict[tuple[str, int], dict],
    event_lookup: dict[str, dict[str, float]],
    rng: np.random.Generator,
) -> list[tuple]:
    rows: list[tuple] = []
    for day_idx, d in enumerate(days):
        dow = d.weekday()
        dow_mult = DOW_MULT[dow]
        ev = event_lookup.get(d.isoformat(), {})
        is_holiday = "holiday" in ev
        local_ev_sev = ev.get("local_event", 0.0)
        has_promo = "promo" in ev

        for h in range(OPEN_HOUR, CLOSE_HOUR):
            hour_mult = HOUR_CURVE.get(h, 0.0)
            if hour_mult == 0.0:
                continue
            w = weather_lookup[(d.isoformat(), h)]
            rain_mm = w["rain_mm"]

            for channel in CHANNELS:
                base = CHANNEL_BASE[channel]
                rain_factor = max(0.1, 1.0 + RAIN_COEF[channel] * rain_mm)
                holiday_factor = HOLIDAY_MULT if is_holiday else 1.0
                event_factor = 1.0 + (EVENT_LOCAL_MULT - 1.0) * local_ev_sev
                promo_factor = PROMO_MULT if has_promo else 1.0
                regime_factor = REGIME_SHIFT_FACTOR[channel] if day_idx >= REGIME_SHIFT_DAY else 1.0

                expected = (
                    base
                    * hour_mult
                    * dow_mult
                    * rain_factor
                    * holiday_factor
                    * event_factor
                    * promo_factor
                    * regime_factor
                )
                noise = float(rng.normal(1.0, NOISE_SIGMA))
                covers = max(0.0, expected * noise)

                ts = datetime(d.year, d.month, d.day, h).isoformat()
                rows.append((ts, channel, round(covers, 2)))
    return rows


# --------------------------------------------------------------------------------------
# Static seeds
# --------------------------------------------------------------------------------------

def _seed_ingredients(conn: sqlite3.Connection) -> dict[str, int]:
    name_to_id: dict[str, int] = {}
    for i, (name, unit, shelf, lead, stock) in enumerate(INGREDIENTS, start=1):
        conn.execute(
            "INSERT INTO ingredients(id, name, unit, shelf_life_days, lead_time_days, stock) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (i, name, unit, shelf, lead, stock),
        )
        name_to_id[name] = i
    return name_to_id


def _seed_recipes(conn: sqlite3.Connection, name_to_id: dict[str, int]) -> None:
    for item_id, _name, recipe in MENU_ITEMS:
        for ing_name, qty in recipe.items():
            conn.execute(
                "INSERT INTO recipes(item_id, ingredient_id, qty_per_cover) VALUES (?, ?, ?)",
                (item_id, name_to_id[ing_name], qty),
            )


def _seed_mix_history(conn: sqlite3.Connection, days: list[date], rng: np.random.Generator) -> None:
    """Daily dish-mix shares — Dirichlet-jittered around MIX_BASE so each day sums to 1.0."""
    base = np.array([MIX_BASE[i] for i, _, _ in MENU_ITEMS])
    base = base / base.sum()
    alpha = base * 80.0  # concentration — higher = closer to base mix
    for d in days:
        sample = rng.dirichlet(alpha)
        for (item_id, _, _), share in zip(MENU_ITEMS, sample):
            conn.execute(
                "INSERT INTO mix_history(date, item_id, share) VALUES (?, ?, ?)",
                (d.isoformat(), item_id, round(float(share), 4)),
            )


def _seed_staff_throughput(conn: sqlite3.Connection) -> None:
    for role, cph, floor in STAFF_THROUGHPUT:
        conn.execute(
            "INSERT INTO staff_throughput(role, covers_per_hour, floor_min) VALUES (?, ?, ?)",
            (role, cph, floor),
        )


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------

def generate(
    start: date = START_DATE,
    end: date = END_DATE,
    seed: int = 42,
    db_path: Path = DB_PATH,
) -> None:
    rng = np.random.default_rng(seed)
    init_db(db_path)
    days = _date_range(start, end)

    weather_rows = _generate_weather(days, rng)
    event_rows = _generate_events(days, rng)
    weather_lookup = _build_weather_lookup(weather_rows)
    event_lookup = _build_event_lookup(event_rows)
    obs_rows = _generate_observations(days, weather_lookup, event_lookup, rng)

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO weather(date, hour, temp, rain_mm, condition) VALUES (?,?,?,?,?)",
            weather_rows,
        )
        conn.executemany(
            "INSERT INTO events(date, type, severity) VALUES (?,?,?)",
            event_rows,
        )
        conn.executemany(
            "INSERT INTO observations(ts, channel, covers) VALUES (?,?,?)",
            obs_rows,
        )
        name_to_id = _seed_ingredients(conn)
        _seed_recipes(conn, name_to_id)
        _seed_mix_history(conn, days, rng)
        _seed_staff_throughput(conn)
        conn.commit()

    print(f"Generated {len(days)} days into {db_path}")
    print(f"  weather rows      : {len(weather_rows):,}")
    print(f"  event rows        : {len(event_rows):,}")
    print(f"  observation rows  : {len(obs_rows):,}")
    print(f"  ingredients       : {len(INGREDIENTS)}")
    print(f"  menu items        : {len(MENU_ITEMS)}")
    print(f"  staff roles       : {len(STAFF_THROUGHPUT)}")
    print(f"  regime shift at   : day {REGIME_SHIFT_DAY} = {days[REGIME_SHIFT_DAY].isoformat()}")


if __name__ == "__main__":
    generate()
