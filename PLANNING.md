# Restaurant Management System (RMS) — Initial Project Planning

> This document captures the **initial planning phase** of the RMS POC: the problem, the constraints, the decisions made, and the rationale behind them. It is a frozen snapshot of how the project started. Day-to-day feature work and architectural changes that happen after this point live in `AGENTS.md`.

---

## 1. Problem Statement

Restaurants lose money in two directions:

- **Over-resourcing** — too many staff scheduled, too much food ordered, ingredients expiring before use.
- **Under-resourcing** — understaffed shifts, dishes going unavailable mid-service, frustrated customers.

The system must predict, for any upcoming day:

1. **Covers (customer count)** — broken down by hour and by channel (dine-in, delivery, takeaway).
2. **Staffing** — how many people to schedule, by role and station.
3. **Ingredient orders** — how much of each ingredient to procure, respecting shelf life and supplier lead times.

Predictions will be wrong. The system must accept manager corrections (e.g. *"you predicted 120 covers, we got 85 because of rain"*) and adjust its coefficients over time so predictions converge toward accuracy. This is a **feedback loop**, not a one-shot model.

---

## 2. Constraints

- **Time:** 3–4 working days for the POC.
- **Cost:** ~$0. Free tiers only.
- **Team:** Small / solo.
- **Data:** No real restaurant data available — synthetic dataset will be generated.
- **Scope:** Single restaurant, single tenant, demo-grade UI.

---

## 3. High-Level Approach

A **two-layer hybrid model**:

```
                 ┌─────────────────────────────┐
Features  ─────► │  LightGBM (base model)      │ ──► base_pred
                 │  Retrained weekly           │
                 └─────────────────────────────┘
                              │
                              ▼
              Features + base_pred + reason tags
                              │
                              ▼
                 ┌─────────────────────────────┐
                 │  SGDRegressor (residual)    │ ──► residual_pred
                 │  Updated per correction     │
                 │  via partial_fit()          │
                 └─────────────────────────────┘
                              │
                              ▼
                  final_pred = base + residual
                              │
                              ▼
                 ┌─────────────────────────────┐
                 │  Manager correction         │
                 │  residual_target =          │
                 │     actual − base_pred      │
                 │  sgd.partial_fit(X, res)    │
                 └─────────────────────────────┘
```

### Why this architecture

- **LightGBM base** captures the heavy non-linear structure: hour-of-day curves, weekday effects, weather × channel interactions, holiday spikes. Retrained weekly because restaurant demand drifts slowly.
- **SGDRegressor residual** absorbs short-horizon drift between weekly retrains and learns directly from manager corrections via true online updates (`partial_fit`).
- **Roles are clean:** the base owns long-range structure; the residual owns near-term, interpretable corrections.

### Why not LightGBM in both layers?

LightGBM has no true online learning — its "incremental" mode requires batches and adds trees rather than updating coefficients. For a demo that hinges on *"manager submits one correction → coefficients visibly shift → re-predict → number changes,"* a per-sample online learner is required. SGD provides this. It also produces an interpretable coefficient table that doubles as a stakeholder-facing explanation of *what the model learned this week*. The architecture treats the residual layer as a swappable module, so LightGBM can replace SGD post-POC if residuals turn out to be strongly non-linear.

### Why not pure LightGBM?

No feedback loop story. Demo dies on the convergence plot.

### Why not pure SGD?

Cannot capture interactions like `rain × channel × hour` without exhaustive hand-crafted features. Tree base does this for free.

---

## 4. Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Fast iteration, scikit-learn + LightGBM native |
| Base model | LightGBM | Best accuracy-to-effort ratio on tabular data |
| Residual model | `sklearn.linear_model.SGDRegressor` | True `partial_fit`, interpretable, cheap |
| API | FastAPI | Async, OpenAPI docs, low ceremony |
| Storage | SQLite | Zero-ops, sufficient for single restaurant |
| Dashboard | Streamlit | Fastest path to a working UI in 4 days |
| Scheduler | APScheduler (in-process) | No extra infra for weekly retrains |
| Containerization | Docker | Single artifact, easy deploy |
| Deploy target | Fly.io free tier (or local) | $0 cost |
| Charts | Plotly (via Streamlit) | Built-in, interactive |

---

## 5. Data Model

### Synthetic dataset generation

12–18 months of hourly observations are generated with known ground-truth coefficients so the eval harness can measure how close the trained model gets to the true drivers.

Injected drivers:

- Day-of-week and hour-of-day curves (multiplicative)
- Weather: temperature, rain (mm), condition
- Holidays and local events
- Promo flags
- Channel mix (dine-in / delivery / takeaway) with different rain sensitivities
- Random noise (~10%)
- One scripted regime shift (e.g. a new delivery partner doubles delivery volume from day 200 onward) — used to demonstrate the residual layer adapting before the next weekly base retrain.

### Tables

```
observations(ts, channel, covers)
weather(date, hour, temp, rain_mm, condition)
events(date, type, severity)
predictions(ts, channel, base_pred, residual_pred, final_pred, model_version)
corrections(ts, channel, predicted, actual, reason_tag,
            weather_flag, event_flag, created_at)
ingredients(id, name, unit, shelf_life_days, lead_time_days, stock)
recipes(item_id, ingredient_id, qty_per_cover)
mix_history(date, item_id, share)
staff_throughput(role, covers_per_hour, floor_min)
model_registry(version, type, trained_at, mae, r2, path)
sgd_state(version, coef_blob, intercept, n_updates, last_reset_at)
```

---

## 6. Three Prediction Modules

### 6.1 Covers (hourly × channel)

Direct output of the two-layer model. One model per channel — separate LightGBM boosters for dine-in, delivery, and takeaway because rain (and other drivers) affect them differently. Hourly predictions are aggregated for daily views.

### 6.2 Staff

Rule-based, no ML — staffing is a deterministic function of covers once throughput per role is known.

```
needed[hour][role] = max(floor_min[role],
                          ceil(covers[hour] / throughput[role]))
shift_blocks      = greedy_pack(needed, block_sizes=[4h, 8h])
```

Throughput per role is stored in `staff_throughput` and editable from the dashboard, so managers can calibrate the rule without touching code.

### 6.3 Ingredient orders

```
horizon = max(lead_time) + safety_days
for day in horizon:
    forecast = predict_covers(day)
    mix      = mix_history.last_28d_avg()
    need[ing] += Σ forecast * mix[item] * recipe[item, ing]
order[ing] = max(0, need[ing] - stock[ing] - incoming[ing])
order[ing] = min(order[ing], shelf_life[ing] * usage_rate[ing])  # shelf-life clip
```

---

## 7. Feedback Loop

### Correction submission

```python
def on_correction(ts, channel, actual, reason_tag):
    base_pred = predictions_table.lookup(ts, channel).base_pred
    X         = build_features(ts, channel) + [base_pred] + onehot(reason_tag)
    residual  = actual - base_pred
    residual  = clip(residual, -0.5 * base_pred, 0.5 * base_pred)  # guardrail
    sgd.partial_fit([X], [residual])
    persist(sgd)
    log_correction(...)
```

### Reason-tag vocabulary

Fixed, small set so the one-hot dimension stays tight and the resulting coefficients are interpretable:

```
rain_heavy, rain_light, event_local, event_holiday,
promo, no_show_group, normal, other
```

### Reset policy

When the base LightGBM is retrained, the SGD residual is reset and warm-started from fresh residuals on the new base. Past corrections are already absorbed into the data the LightGBM saw during retraining, so the residual layer doesn't need to carry them forward.

### Guardrails

- Residual prediction clipped to ±50% of base.
- If `sgd.n_updates_since_retrain > 200`, dashboard surfaces a *"base model stale — retrain recommended"* warning.

---

## 8. Evaluation Harness

The convergence story is the demo. The eval harness exists to prove it works.

- **Backtest replay:** walk through the last 60 days chronologically, predict → reveal actual → submit correction → measure rolling MAE.
- **Comparisons plotted side-by-side:**
  1. Naive baseline (same day-of-week 4-week average)
  2. LightGBM only
  3. LightGBM + SGD residual (full system)
- **Regime-shift test:** inject the synthetic regime change at day 30 of the replay and show the SGD layer reducing MAE before the next weekly base retrain catches up.

---

## 9. API Surface

```
GET  /forecast/covers?date=&channel=
GET  /forecast/staff?date=
GET  /forecast/orders?from=&to=
POST /corrections                  body: {ts, channel, actual, reason_tag}
POST /train/base                   triggers background retrain
GET  /metrics                      rolling MAE / MAPE / bias / n_corrections
GET  /model/registry               list of versions
GET  /model/coefficients           current SGD coefficients (for dashboard)
```

---

## 10. Dashboard Pages

1. **Today / Tomorrow** — hourly covers chart, channel split, staffing table, confidence band.
2. **Order Sheet** — ingredient table with quantity, supplier, deadline, *Approve order* button.
3. **Corrections** — date picker → predicted vs actual form → reason dropdown → submit. Shows the diff and a *"model updated"* toast.
4. **Model Health** — MAE trend over the last 90 days, bias plot, base model version + last retrain timestamp, *Retrain now* button.
5. **Coefficient Inspector** — table joining LightGBM feature importance (gain) with current SGD residual coefficients, sorted by magnitude. This is the *"what the model learned this week"* page.

---

## 11. Day-by-Day Plan

| Day | Deliverable |
|---|---|
| **1** | Synthetic data generator, SQLite schema, feature builder, LightGBM base trained per channel, metrics logged. |
| **2** | SGD residual warm-start + `partial_fit` endpoint, FastAPI skeleton, unit tests demonstrating convergence on injected biased corrections. |
| **3** | Streamlit dashboard (5 pages), backtest harness, MAE convergence plots, ingredient module. |
| **4** | Dockerization, Fly.io deploy, demo script, README, edge-case polish, stretch items. |

---

## 12. Repository Layout

```
RMS/
├── app/
│   ├── api/                FastAPI routers
│   │   ├── forecast.py
│   │   ├── corrections.py
│   │   ├── training.py
│   │   └── metrics.py
│   ├── features/           feature_builder.py
│   ├── models/
│   │   ├── base_lgbm.py
│   │   ├── residual_sgd.py
│   │   └── interfaces.py   ResidualModel protocol (swappable)
│   ├── train/
│   │   ├── train_base.py
│   │   └── init_sgd.py
│   ├── predict/
│   │   ├── covers.py
│   │   ├── staff.py
│   │   └── orders.py
│   ├── data/
│   │   ├── generator.py    synthetic data
│   │   └── schema.sql
│   ├── eval/
│   │   └── backtest.py
│   ├── scheduler.py        APScheduler weekly retrain
│   └── main.py
├── dashboard/
│   └── streamlit_app.py
├── artifacts/
│   ├── models/             persisted LGBM + SGD
│   └── rms.db              SQLite
├── tests/
├── Dockerfile
├── requirements.txt
├── PLANNING.md             (this file — frozen initial plan)
├── AGENTS.md               (living doc — feature additions, decisions)
└── README.md
```

---

## 13. Risks and Cut Lines

| Risk | Mitigation / Cut |
|---|---|
| Synthetic data not realistic enough to sell the demo | Bake the regime-shift scenario in; tune noise; calibrate against published restaurant industry benchmarks |
| Ingredient module slips | Cut to Day 5 / stretch — keep covers + staff as the core demo |
| Streamlit feels too rough | Acceptable for POC; React + Recharts post-POC if needed |
| SGD residuals show non-linear bias | Add hand-crafted interaction features (`rain_x_channel`, `event_x_dinner`); residual layer is swappable to LightGBM if needed |
| Deploy issues on Fly.io | Fall back to local Docker for the demo |

---

## 14. Out of Scope (POC)

- Multi-tenant / multi-restaurant
- Authentication and role-based access
- Mobile app
- POS / supplier API integrations
- Real-time event streams
- Production-grade observability (Datadog, Sentry)
- A/B testing of model variants in production

These are explicitly deferred. They live as future-work items and graduate into `AGENTS.md` when work on them actually begins.

---

## 15. Definition of Done (POC)

- Synthetic dataset generated and loaded into SQLite.
- LightGBM base trains end-to-end with metrics logged to `model_registry`.
- SGD residual updates on `POST /corrections` and persists between restarts.
- Dashboard renders all five pages with live data.
- Backtest replay produces a visibly downward-trending MAE curve, with the hybrid model beating LightGBM-only and the naive baseline.
- One-click Docker run reproduces the demo locally.
- README explains how to run, retrain, and submit a correction.
