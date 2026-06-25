"""Forecast endpoints: covers, staff, ingredient orders."""

from datetime import date

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/covers")
def get_covers_forecast(
    target: date = Query(..., description="Date to forecast"),
    channel: str | None = Query(None, description="dine_in | delivery | takeaway | None for all"),
) -> dict:
    raise NotImplementedError


@router.get("/staff")
def get_staff_forecast(target: date = Query(...)) -> dict:
    raise NotImplementedError


@router.get("/orders")
def get_orders_forecast(
    start: date = Query(...),
    end: date = Query(...),
) -> dict:
    raise NotImplementedError
