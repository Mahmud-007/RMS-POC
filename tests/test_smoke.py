"""Smoke tests — verify package imports and FastAPI app boots."""

from fastapi.testclient import TestClient


def test_app_imports() -> None:
    from app.main import app
    assert app is not None


def test_health_endpoint() -> None:
    from app.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
