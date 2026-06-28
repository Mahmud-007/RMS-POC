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
    reason_tag: str = Query("normal", description="What-if scenario override"),
    use_weather: bool = Query(True),
) -> dict:
    """Aggregated payload for the manager dashboard: covers + staff + weather in one call.

    Returns:
        {
          date, reason_tag, weather,
          covers: {channel: [hourly...]},
          totals: {channel: float, all: float},
          staff:  {hourly, person_hours, peak_headcount},
        }
    """
    covers = covers_svc.predict_day(
        target=target, reason_tag=reason_tag, use_weather=use_weather,
    )
    staff = staff_svc.predict_day(target)

    totals = {ch: sum(r["final_pred"] for r in rows) for ch, rows in covers.items()}
    totals["all"] = sum(totals.values())

    weather = None
    try:
        from app.integrations.weather import get_day_summary
        weather = get_day_summary(target)
    except Exception:
        weather = None

    return {
        "date": target.isoformat(),
        "reason_tag": reason_tag,
        "weather": weather,
        "covers": covers,
        "totals": totals,
        "staff": staff,
    }
