"""Model health and metric endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
def get_metrics() -> dict:
    """Rolling MAE, MAPE, bias, correction count."""
    raise NotImplementedError


@router.get("/registry")
def get_model_registry() -> list[dict]:
    raise NotImplementedError


@router.get("/coefficients")
def get_sgd_coefficients() -> dict:
    """Current SGD residual coefficients — for the dashboard's coefficient inspector."""
    raise NotImplementedError
