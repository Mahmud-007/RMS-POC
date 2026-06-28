#!/usr/bin/env bash
# Render backend start script.
#
# CRITICAL: bind the HTTP port immediately so Render's health check (which scans
# for an open port within ~90s) passes. If the dataset/models are missing, run
# the bootstrap (generate data + train) in the BACKGROUND — it must NOT block
# the port from opening. /health responds right away; forecast endpoints return
# an error until training finishes (~1-2 min on a fresh boot), then work normally.
#
# With a persistent disk, this bootstrap runs once and the trained state
# (including accumulated corrections) survives restarts. Without a disk (free
# tier) it re-runs on each cold start.
set -e

if [ ! -f artifacts/rms.db ]; then
  echo "[start] artifacts missing — bootstrapping in the background"
  (
    python -m app.data.generator \
      && python -m app.train.train_base \
      && python -m app.train.init_sgd \
      && echo "[start] bootstrap complete"
  ) &
else
  echo "[start] artifacts present — skipping bootstrap"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
