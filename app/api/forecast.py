"""Forecast endpoints: covers, staff, ingredient orders."""

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
    reason_tag: str = Query("normal", description="What-if reason tag for the residual layer"),
) -> dict:
    return covers_svc.predict_day(target=target, channel=channel, reason_tag=reason_tag)


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
