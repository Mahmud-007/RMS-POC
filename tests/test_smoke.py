"""End-to-end smoke tests for the RMS POC.

Assumes the synthetic dataset has been generated and both base + SGD models trained
(repo-root `python -m app.data.generator && python -m app.train.train_base && python -m app.train.init_sgd`).
The tests exercise the FastAPI surface and the prediction services.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

TODAY = date(2026, 6, 25)  # last data day per FEAT-002
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ---- Health -------------------------------------------------------------------------

def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---- Forecast endpoints ------------------------------------------------------------

def test_forecast_covers_all_channels(client: TestClient) -> None:
    r = client.get(f"/forecast/covers?target={TOMORROW.isoformat()}")
    assert r.status_code == 200
    payload = r.json()
    assert set(payload.keys()) == {"dine_in", "delivery", "takeaway"}
    for ch, rows in payload.items():
        assert len(rows) == 12  # 11..22
        for row in rows:
            for key in ("hour", "base_pred", "residual_raw", "residual_pred", "final_pred"):
                assert key in row
            assert row["final_pred"] >= 0
            # Residual clipped to ±clip_fraction × base
            assert abs(row["residual_pred"]) <= abs(row["base_pred"]) * 0.5 + 1e-6


def test_forecast_covers_channel_filter(client: TestClient) -> None:
    r = client.get(f"/forecast/covers?target={TOMORROW.isoformat()}&channel=delivery")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"delivery"}


def test_forecast_staff(client: TestClient) -> None:
    r = client.get(f"/forecast/staff?target={TOMORROW.isoformat()}")
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == TOMORROW.isoformat()
    assert len(body["hourly"]) == 12
    assert {"server", "host", "line_cook", "dishwasher"} <= set(body["person_hours"].keys())
    for h in body["hourly"]:
        assert h["headcount"]["server"] >= 1
        assert h["headcount"]["line_cook"] >= 1


def test_forecast_orders(client: TestClient) -> None:
    start = TOMORROW
    end = TOMORROW + timedelta(days=5)
    r = client.get(f"/forecast/orders?start={start.isoformat()}&end={end.isoformat()}")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    for row in rows:
        assert row["recommended_order"] >= 0
        # Shelf-life cap is the binding constraint
        assert row["recommended_order"] <= max(row["raw_order"], row["shelf_cap"]) + 1e-6


def test_forecast_orders_bad_range(client: TestClient) -> None:
    r = client.get(f"/forecast/orders?start={TOMORROW.isoformat()}&end={TOMORROW.isoformat()}")
    assert r.status_code == 200
    r = client.get(f"/forecast/orders?end={TOMORROW.isoformat()}&start={(TOMORROW + timedelta(days=2)).isoformat()}")
    assert r.status_code == 400


# ---- Corrections + metrics --------------------------------------------------------

def test_correction_roundtrip_shifts_residual(client: TestClient) -> None:
    """Submit a correction; verify the residual prediction moves toward it."""
    ts = datetime.combine(TODAY, datetime.min.time()).replace(hour=19)
    body = {
        "ts": ts.isoformat(),
        "channel": "delivery",
        "actual": 4.0,                # well below base prediction → residual should drop
        "reason_tag": "rain_heavy",
    }
    r = client.post("/corrections", json=body)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["actual"] == 4.0
    # Target residual is negative (actual < base_pred)
    assert result["target_residual"] < 0
    # Clipped target magnitude does not exceed 50% of |base|
    assert abs(result["target_residual_clipped"]) <= abs(result["base_pred"]) * 0.5 + 1e-6
    # n_updates ticked at least once
    assert result["n_updates"] > 0


def test_correction_rejects_unknown_tag(client: TestClient) -> None:
    body = {
        "ts": "2026-06-25T19:00:00",
        "channel": "delivery",
        "actual": 10.0,
        "reason_tag": "nonsense_tag",
    }
    r = client.post("/corrections", json=body)
    # Pydantic validates the Literal at request time
    assert r.status_code == 422


def test_metrics_endpoint(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"dine_in", "delivery", "takeaway"}
    for ch, payload in body.items():
        assert payload["sgd_fitted"] is True


def test_metrics_registry(client: TestClient) -> None:
    r = client.get("/metrics/registry")
    assert r.status_code == 200
    rows = r.json()
    types = {row["type"] for row in rows}
    assert {f"lgbm_base_{ch}" for ch in ("dine_in", "delivery", "takeaway")} <= types
    assert {f"sgd_residual_{ch}" for ch in ("dine_in", "delivery", "takeaway")} <= types


def test_metrics_coefficients(client: TestClient) -> None:
    r = client.get("/metrics/coefficients?channel=delivery")
    assert r.status_code == 200
    payload = r.json()["delivery"]
    assert payload["fitted"] is True
    coefs = payload["coefficients"]
    assert "base_pred" in coefs
    # Sorted by absolute magnitude — base_pred should be near the top
    top_keys = list(coefs.keys())[:3]
    assert "base_pred" in top_keys


# ---- Service-level checks ---------------------------------------------------------

def test_predict_day_shapes() -> None:
    from app.predict.covers import predict_day
    result = predict_day(TOMORROW)
    assert set(result.keys()) == {"dine_in", "delivery", "takeaway"}
    assert all(len(rows) == 12 for rows in result.values())


def test_predict_orders_horizon() -> None:
    from app.predict.orders import horizon_for_ingredients, predict_orders
    h = horizon_for_ingredients()
    assert h >= 1
    rows = predict_orders(TOMORROW, TOMORROW + timedelta(days=h - 1))
    df = pd.DataFrame(rows)
    assert "recommended_order" in df.columns
    assert (df["recommended_order"] >= 0).all()
