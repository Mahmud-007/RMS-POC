#!/usr/bin/env bash
# Render backend start script.
#
# Idempotent bootstrap: if the artifacts directory has no database yet (first
# boot, or an ephemeral free-tier cold start), generate the dataset and train
# the models. With a persistent disk mounted at artifacts/, this runs exactly
# once and the trained state — including accumulated corrections — survives
# restarts. Without a disk (free tier), it re-runs on every cold start and the
# learning from corrections resets to the warm-start baseline.
set -e

if [ ! -f artifacts/rms.db ]; then
  echo "[start] no artifacts/rms.db — bootstrapping dataset + models"
  python -m app.data.generator
  python -m app.train.train_base
  python -m app.train.init_sgd
  echo "[start] bootstrap complete"
else
  echo "[start] existing artifacts/rms.db found — skipping bootstrap"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
