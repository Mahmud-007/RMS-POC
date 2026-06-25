# Restaurant Management System (RMS)

POC for a forecasting + feedback-loop system that predicts daily covers, staffing, and ingredient orders for a single restaurant. See [PLANNING.md](PLANNING.md) for the initial plan and [AGENTS.md](AGENTS.md) for the living change log.

## Quick start

```bash
python -m venv .venv
source .venv/Scripts/activate   # or .venv/bin/activate on Linux/macOS
pip install -r requirements.txt

# Generate synthetic data + initial DB
python -m app.data.generator

# Train base model
python -m app.train.train_base

# Warm-start residual layer
python -m app.train.init_sgd

# Run API
uvicorn app.main:app --reload

# Run dashboard (separate terminal)
streamlit run dashboard/streamlit_app.py
```

## Docker

```bash
docker build -t rms .
docker run -p 8000:8000 -p 8501:8501 -v $(pwd)/artifacts:/srv/artifacts rms
```

## Layout

See [PLANNING.md §12](PLANNING.md).

## Status

POC — see `AGENTS.md` Feature Log for current progress.
