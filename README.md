# Restaurant Management System (RMS) — Forecasting POC

A forecasting + feedback-loop system for a single restaurant. Predicts hourly **covers**, **staffing**, and **ingredient orders**, then learns online from manager corrections. Built in 3–4 working days as a POC.

- Architecture overview, day-by-day plan, definition of done → [PLANNING.md](PLANNING.md)
- Every feature shipped, decision made, and trade-off considered → [AGENTS.md](AGENTS.md)
- Customer-behaviour analysis of the synthetic dataset → [docs/DATA_INSIGHTS.md](docs/DATA_INSIGHTS.md)

---

## Two-layer model

```
LightGBM (base, retrained weekly) ──► base_pred
                                          │
SGDRegressor (residual, partial_fit) ─────┤
                                          ▼
                final = base + clip(residual, ±50% base)
                                          │
                                Manager correction
                                          │
                                  partial_fit(SGD)
```

- **Base** captures the heavy non-linear structure (day-of-week, hour, weather × channel, holidays).
- **Residual** absorbs structural drift and reason-tagged manager corrections via true online `partial_fit`.
- One model of each per channel: `dine_in`, `delivery`, `takeaway`.

## Quick start

```bash
python -m venv .venv
source .venv/Scripts/activate         # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1. Generate the synthetic dataset (15 months, capped at 2026-06-25)
python -m app.data.generator

# 2. Train the LightGBM base (one booster per channel)
python -m app.train.train_base

# 3. Warm-start the SGD residual layer
python -m app.train.init_sgd

# 4a. Launch the dashboard (7 pages)
streamlit run dashboard/streamlit_app.py
#  → http://localhost:8501

# 4b. (Optional) Launch the API in another terminal
uvicorn app.main:app --reload
#  → http://localhost:8000/docs
```

## Demo flow

1. **Dataset Explorer** — see the data the model trains on.
2. **Validation (last 28d)** — base-model accuracy on the holdout.
3. **Today / Tomorrow** — hourly cover forecast + recommended staffing. Pick a date, pick a what-if `reason_tag`.
4. **Order Sheet** — ingredient orders, shelf-life capped.
5. **Corrections** — submit `(ts, channel, actual, reason_tag)`. Watch the residual prediction move and `n_updates` tick up.
6. **Model Health** — rolling MAE, daily MAE chart, backtest replay (`naive` vs `base` vs `hybrid`), retrain controls, full model registry.
7. **Coefficient Inspector** — LightGBM feature importance (gain) and live SGD coefficients side-by-side.

## API surface

```
GET  /health
GET  /forecast/covers?target=YYYY-MM-DD[&channel=…][&reason_tag=…]
GET  /forecast/staff?target=YYYY-MM-DD
GET  /forecast/orders?start=YYYY-MM-DD&end=YYYY-MM-DD
POST /corrections                 # body: {ts, channel, actual, reason_tag}
POST /train/base                  # background base retrain
POST /train/sgd/reset             # warm-start SGD
GET  /metrics[?rolling_days=30]
GET  /metrics/registry
GET  /metrics/coefficients[?channel=…]
```

Full OpenAPI docs at `http://localhost:8000/docs` once `uvicorn` is running.

## Docker

```bash
docker build -t rms .
docker run -p 8000:8000 -p 8501:8501 -v $(pwd)/artifacts:/srv/artifacts rms
```

The image starts both the API (8000) and the dashboard (8501) in a single container. `artifacts/` is mounted so the SQLite DB and persisted models survive container restarts.

## Tests

```bash
python -m pytest tests/ -v
```

13 smoke tests cover the API surface, the prediction services, the correction round trip, and the model registry.

## Layout

See [PLANNING.md §12](PLANNING.md) — repository structure is documented there; current state matches the plan.

## Status

POC. Definition of done — all checked:

- [x] Synthetic dataset (15 months, 3 channels, known ground-truth drivers, regime shift)
- [x] LightGBM base trains per channel; metrics logged to `model_registry`
- [x] SGD residual `partial_fit` on corrections; state persists between restarts
- [x] Dashboard renders 7 pages with live data
- [x] Backtest replay producing a rolling-MAE chart for naive / base / hybrid
- [x] Docker build runs the API + dashboard from a single image
- [x] Smoke tests
- [x] README explains how to run, retrain, submit a correction

See the **Feature Log** in [AGENTS.md](AGENTS.md) for the full delivery sequence (FEAT-000 through FEAT-014).
