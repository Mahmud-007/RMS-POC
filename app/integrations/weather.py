"""Open-Meteo weather integration.

Fetches an hourly forecast for the restaurant's location and maps it into the same
weather schema the model trained on (`temp`, `rain_mm`, `condition_code`).

Open-Meteo is free and key-less. Forecast horizon is ~16 days, which comfortably
covers the ingredient-order lead-time window. For dates outside the forecast
horizon (or when the API is unreachable) callers fall back to neutral weather.

Environment configuration:
    RMS_LAT   default latitude  (defaults to a placeholder city)
    RMS_LON   default longitude
    RMS_TZ    IANA timezone string for the forecast (defaults to auto)
"""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache

import httpx

from app.features.feature_builder import CONDITION_CODES

DEFAULT_LAT = float(os.getenv("RMS_LAT", "23.9999"))
DEFAULT_LON = float(os.getenv("RMS_LON", "90.4203"))
DEFAULT_TZ = os.getenv("RMS_TZ", "Asia/Dhaka")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
SERVICE_HOURS = list(range(11, 23))
_TIMEOUT = 8.0


def _condition_code(temp: float, rain_mm: float) -> int:
    """Map (temp, rain) to the model's condition_code, matching the generator's rules."""
    if rain_mm > 0 and temp < 2:
        return CONDITION_CODES["snow"]
    if rain_mm > 4:
        return CONDITION_CODES["rain_heavy"]
    if rain_mm > 0:
        return CONDITION_CODES["rain_light"]
    if temp > 28:
        return CONDITION_CODES["hot"]
    if temp < 5:
        return CONDITION_CODES["cold"]
    return CONDITION_CODES["clear"]


@lru_cache(maxsize=256)
def _fetch_raw(target_iso: str, lat: float, lon: float, tz: str) -> dict[int, dict] | None:
    """Fetch hourly forecast for one date. Cached per (date, location).

    Returns {hour: {"temp", "rain_mm", "condition_code"}} for service hours,
    or None if the date is outside the forecast horizon / the API failed.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation",
        "start_date": target_iso,
        "end_date": target_iso,
        "timezone": tz,
    }
    try:
        resp = httpx.get(OPEN_METEO_URL, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    rains = hourly.get("precipitation") or []
    if not times:
        return None

    out: dict[int, dict] = {}
    for t, temp, rain in zip(times, temps, rains):
        # t is like "2026-06-29T19:00"
        hour = int(t[11:13])
        if hour in SERVICE_HOURS:
            temp_f = float(temp) if temp is not None else 18.0
            rain_f = float(rain) if rain is not None else 0.0
            out[hour] = {
                "temp": round(temp_f, 2),
                "rain_mm": round(rain_f, 2),
                "condition_code": _condition_code(temp_f, rain_f),
            }
    return out or None


def get_hourly_weather(
    target: date,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    tz: str = DEFAULT_TZ,
) -> dict[int, dict] | None:
    """Public accessor. Returns per-service-hour weather, or None if unavailable."""
    return _fetch_raw(target.isoformat(), lat, lon, tz)


def get_day_summary(
    target: date,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    tz: str = DEFAULT_TZ,
) -> dict | None:
    """Aggregate the hourly forecast into a single day summary for UI display."""
    hourly = get_hourly_weather(target, lat, lon, tz)
    if not hourly:
        return None
    temps = [h["temp"] for h in hourly.values()]
    rains = [h["rain_mm"] for h in hourly.values()]
    total_rain = round(sum(rains), 2)
    avg_temp = round(sum(temps) / len(temps), 1)
    peak_rain = max(rains)
    if peak_rain > 4:
        label = "Heavy rain"
    elif peak_rain > 0:
        label = "Light rain"
    elif avg_temp > 28:
        label = "Hot"
    elif avg_temp < 5:
        label = "Cold"
    else:
        label = "Clear"
    return {
        "date": target.isoformat(),
        "avg_temp": avg_temp,
        "total_rain_mm": total_rain,
        "peak_rain_mm": round(peak_rain, 2),
        "label": label,
        "source": "open-meteo",
        "lat": lat,
        "lon": lon,
    }


def clear_cache() -> None:
    _fetch_raw.cache_clear()
