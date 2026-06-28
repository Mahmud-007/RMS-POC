"""Forecast endpoints: covers, staff, ingredient orders, aggregated day, weather."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.predict import covers as covers_svc
from app.predict import orders as orders_svc
from app.predict import staff as staff_svc

router = APIRouter()


@router.get("/covers")
def get_covers_forecast(
    target: date = Query(..., description="Date to forecast"),
    channel: str | None = Query(None, description="dine_in | delivery | takeaway | None for all"),
    reason_tag: str = Query("normal", description="What-if reason tag / scenario override"),
    use_weather: bool = Query(True, description="Populate features with the live forecast"),
) -> dict:
    return covers_svc.predict_day(
        target=target, channel=channel, reason_tag=reason_tag, use_weather=use_weather,
    )


@router.get("/staff")
def get_staff_forecast(target: date = Query(...)) -> dict:
    return staff_svc.predict_day(target)


@router.get("/orders")
def get_orders_forecast(
    start: date = Query(..., description="Inclusive start date"),
    end: date = Query(..., description="Inclusive end date"),
) -> list[dict]:
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")
    return orders_svc.predict_orders(start, end)


@router.get("/weather")
def get_weather(target: date = Query(..., description="Date to fetch forecast weather")) -> dict:
    """Day-summary weather for the target date (Open-Meteo). Null fields if unavailable."""
    from app.integrations.weather import get_day_summary
    summary = get_day_summary(target)
    if summary is None:
        return {"date": target.isoformat(), "available": False}
    return {"available": True, **summary}


@router.get("/day")
def get_day_forecast(
    target: date = Query(..., description="Date to forecast"),
    use_weather: bool = Query(True, description="Use the live forecast as the weather baseline"),
    rain_mm: float | None = Query(None, description="Override rain (mm) for all hours"),
    temp: float | None = Query(None, description="Override temperature (°C) for all hours"),
    is_holiday: bool | None = Query(None, description="Mark the day as a public holiday"),
    is_promo: bool | None = Query(None, description="Mark a promo as running"),
    is_local_event: bool | None = Query(None, description="Mark a local event"),
    event_severity: float | None = Query(None, description="Local-event severity 0..1"),
) -> dict:
    """Aggregated payload for the manager dashboard: covers + staff + weather in one call.

    Weather defaults to the live Open-Meteo forecast. Any explicit override
    (rain_mm / temp / event flags) is the manager correcting or stress-testing that
    baseline — only supplied fields are changed, and the value is used as given.

    Returns: { date, weather, overrides_applied, covers, totals, staff }.
    """
    overrides = dict(
        rain_mm=rain_mm, temp=temp,
        is_holiday=is_holiday, is_promo=is_promo,
        is_local_event=is_local_event, event_severity=event_severity,
    )
    covers = covers_svc.predict_day(target=target, use_weather=use_weather, **overrides)
    staff = staff_svc.predict_day(target, use_weather=use_weather, **overrides)

    totals = {ch: sum(r["final_pred"] for r in rows) for ch, rows in covers.items()}
    totals["all"] = sum(totals.values())

    weather = None
    try:
        from app.integrations.weather import get_day_summary
        weather = get_day_summary(target)
    except Exception:
        weather = None

    applied = {k: v for k, v in overrides.items() if v is not None}

    return {
        "date": target.isoformat(),
        "weather": weather,
        "overrides_applied": applied,
        "covers": covers,
        "totals": totals,
        "staff": staff,
    }
