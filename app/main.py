"""FastAPI entrypoint. Wires routers and starts the background scheduler."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import corrections, forecast, metrics, training
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="RRPS Forecasting", version="0.1.0", lifespan=lifespan)

# CORS — allow the React frontend (local dev + deployed origins).
# Configure deployed origins via RMS_CORS_ORIGINS (comma-separated). Local Vite
# dev/preview ports are always allowed.
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
]
_extra_origins = [o.strip() for o in os.getenv("RMS_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    # Dev: any localhost port (Vite drifts to 5174/5175 when 5173 is busy).
    # Prod: any onrender.com / netlify.app subdomain, so the frontend works
    # without hardcoding its exact URL. Tighten via RMS_CORS_ORIGINS if needed.
    allow_origin_regex=(
        r"http://(localhost|127\.0\.0\.1):\d+"
        r"|https://([a-z0-9-]+\.)*(onrender\.com|netlify\.app)"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forecast.router, prefix="/forecast", tags=["forecast"])
app.include_router(corrections.router, prefix="/corrections", tags=["corrections"])
app.include_router(training.router, prefix="/train", tags=["training"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])


@app.exception_handler(RuntimeError)
async def _runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    """Surface the model-warmup window cleanly.

    On a fresh boot the models train in the background (see start.sh). Until they
    exist, the prediction services raise RuntimeError ("No base model registered…").
    Return 503 with a friendly message so the frontend shows "warming up" rather
    than a raw 500.
    """
    msg = str(exc)
    if any(s in msg for s in ("No base model", "No SGD", "not initialized", "not fitted")):
        return JSONResponse(
            status_code=503,
            content={"detail": "Models are still warming up — try again in a minute."},
        )
    return JSONResponse(status_code=500, content={"detail": msg})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
