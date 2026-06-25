"""Synthetic data generator.

Produces ~12–18 months of hourly observations with known ground-truth drivers
(dow/hour curves, weather sensitivity per channel, holidays, events, promos).
Includes one scripted regime shift (e.g. delivery doubles from day 200) for the
demo's MAE-convergence story.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("artifacts/rms.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text())


def generate(months: int = 15, seed: int = 42, db_path: Path = DB_PATH) -> None:
    """Generate synthetic observations, weather, events, ingredients, recipes."""
    raise NotImplementedError


if __name__ == "__main__":
    init_db()
    generate()
