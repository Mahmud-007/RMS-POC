"""Correction endpoint. Drives the online learning loop (SGD partial_fit)."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

ReasonTag = Literal[
    "rain_heavy",
    "rain_light",
    "event_local",
    "event_holiday",
    "promo",
    "no_show_group",
    "normal",
    "other",
]


class Correction(BaseModel):
    ts: datetime
    channel: Literal["dine_in", "delivery", "takeaway"]
    actual: float = Field(ge=0)
    reason_tag: ReasonTag = "normal"


class CorrectionResult(BaseModel):
    predicted: float
    actual: float
    residual: float
    n_updates: int
    model_version: str


@router.post("", response_model=CorrectionResult)
def submit_correction(payload: Correction) -> CorrectionResult:
    raise NotImplementedError
