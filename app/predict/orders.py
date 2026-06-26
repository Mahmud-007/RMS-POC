"""Ingredient order recommendations.

Algorithm (per `PLANNING.md §6.3`):

    horizon  = max(lead_time) + safety_days
    for day in horizon:
        forecast_covers[day] = sum across channels
        mix      = mix_history.last_28d_avg
        need[ing] += sum over items of forecast_covers[day] * mix[item] * recipe[item, ing]
    order[ing] = max(0, need[ing] - stock[ing] - incoming[ing])
    order[ing] = min(order[ing], shelf_life[ing] * usage_rate[ing])
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from app.predict import covers as covers_svc

DB_PATH = Path("artifacts/rms.db")
SAFETY_DAYS = 1
MIX_LOOKBACK_DAYS = 28


def _load_ingredients(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql(
            "SELECT id, name, unit, shelf_life_days, lead_time_days, stock FROM ingredients",
            conn,
        )


def _load_recipes(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql(
            "SELECT item_id, ingredient_id, qty_per_cover FROM recipes", conn,
        )


def _load_mix(db_path: Path) -> pd.DataFrame:
    """Last 28 days of dish-mix, averaged per item_id."""
    with sqlite3.connect(db_path) as conn:
        max_d = conn.execute("SELECT MAX(date) FROM mix_history").fetchone()[0]
    if not max_d:
        raise RuntimeError("mix_history is empty")
    cutoff = (pd.Timestamp(max_d) - pd.Timedelta(days=MIX_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(
            "SELECT item_id, AVG(share) AS share FROM mix_history "
            "WHERE date >= ? GROUP BY item_id",
            conn, params=(cutoff,),
        )
    # Renormalize defensively
    total = df["share"].sum()
    if total > 0:
        df["share"] = df["share"] / total
    return df


def predict_orders(start: date, end: date, db_path: Path = DB_PATH) -> list[dict]:
    """Per-ingredient order quantity for the window. End is inclusive."""
    if end < start:
        raise ValueError("end must be >= start")

    ingredients = _load_ingredients(db_path)
    recipes = _load_recipes(db_path)
    mix = _load_mix(db_path)

    # Total covers forecast per day across all channels
    daily = covers_svc.predict_daily_totals(start, end, db_path=db_path)
    by_day = (
        pd.DataFrame(daily).groupby("date", as_index=False)["covers"].sum()
        .rename(columns={"covers": "covers_total"})
    )
    horizon_covers = float(by_day["covers_total"].sum())

    # Per-item demand across horizon: covers × mix share
    item_demand = mix.copy()
    item_demand["item_covers"] = item_demand["share"] * horizon_covers

    # Per-ingredient need: sum over items of item_covers × qty_per_cover
    joined = recipes.merge(item_demand, on="item_id", how="inner")
    joined["needed"] = joined["item_covers"] * joined["qty_per_cover"]
    ingredient_need = joined.groupby("ingredient_id", as_index=False)["needed"].sum()

    # Combine with stock + shelf life
    result = ingredients.merge(
        ingredient_need, left_on="id", right_on="ingredient_id", how="left",
    ).fillna({"needed": 0.0})

    rows: list[dict] = []
    n_days = (end - start).days + 1
    daily_usage = {row["id"]: row["needed"] / n_days for _, row in result.iterrows()}

    for _, row in result.iterrows():
        ing_id = int(row["id"])
        raw_order = float(max(0.0, row["needed"] - row["stock"]))  # incoming not modeled in POC
        # Shelf-life cap: don't order more than what we can use before it goes bad
        shelf_cap = float(row["shelf_life_days"]) * daily_usage[ing_id]
        order = float(min(raw_order, shelf_cap)) if shelf_cap > 0 else raw_order
        rows.append({
            "ingredient_id": ing_id,
            "name": row["name"],
            "unit": row["unit"],
            "lead_time_days": int(row["lead_time_days"]),
            "shelf_life_days": int(row["shelf_life_days"]),
            "stock_on_hand": float(row["stock"]),
            "forecast_need": float(row["needed"]),
            "raw_order": raw_order,
            "shelf_cap": shelf_cap,
            "recommended_order": order,
            "horizon_start": start.isoformat(),
            "horizon_end": end.isoformat(),
            "horizon_days": n_days,
        })

    rows.sort(key=lambda r: r["recommended_order"], reverse=True)
    return rows


def horizon_for_ingredients(db_path: Path = DB_PATH) -> int:
    """Default order horizon = max(lead_time) + SAFETY_DAYS."""
    with sqlite3.connect(db_path) as conn:
        max_lead = conn.execute("SELECT MAX(lead_time_days) FROM ingredients").fetchone()[0]
    return int(max_lead or 1) + SAFETY_DAYS
