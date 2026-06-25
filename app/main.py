"""FastAPI entrypoint. Wires routers and starts the background scheduler."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import corrections, forecast, metrics, training
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="RMS Forecasting", version="0.1.0", lifespan=lifespan)

app.include_router(forecast.router, prefix="/forecast", tags=["forecast"])
app.include_router(corrections.router, prefix="/corrections", tags=["corrections"])
app.include_router(training.router, prefix="/train", tags=["training"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
