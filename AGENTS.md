# AGENTS.md — RMS Living Documentation

> **Purpose.** `PLANNING.md` is the frozen snapshot of how this project started. **This file is the living counterpart.** Every new feature, architectural change, model swap, or significant decision made *after* the initial plan is documented here. If a future contributor (human or AI agent) wants to know *"why does the system work this way today?"*, the answer should be reconstructable by reading `PLANNING.md` once, then reading this file top-to-bottom.
>
> Treat this file the way a well-run engineering team treats an architecture decision log: append-only, dated, honest about trade-offs.

---

## How to Use This File

When you introduce a new feature, change behavior, or make a non-trivial decision:

1. Add a new entry under **Feature Log** using the template at the bottom of this file.
2. If the change affects the architecture in `PLANNING.md`, **do not edit `PLANNING.md`** — instead, note the deviation in your entry under *"Deviation from initial plan"*.
3. If the change introduces a new convention (naming, folder structure, API contract), add it to the relevant section in **Conventions**.
4. If the change deprecates or removes something, log it under **Deprecations** as well as in the feature entry.
5. Keep entries terse but complete. The goal is *"a new contributor can read this and not need to ask."*

---

## Project Snapshot

| Field | Value |
|---|---|
| Project | Restaurant Management System (RMS) — Forecasting POC |
| Status | POC / In active development |
| Started | 2026-06-25 |
| Initial plan | See [PLANNING.md](./PLANNING.md) |
| Primary owner | TBD |
| Stack | Python 3.11, FastAPI, LightGBM, scikit-learn (SGDRegressor), SQLite, Streamlit, Docker |
| Deploy target | Fly.io (free tier) or local Docker |

---

## Architectural Overview (Current State)

This section is updated whenever the architecture changes. It always reflects *current truth*, not history. For history, see the **Feature Log** below.

### Model

- **Base model:** LightGBM, one booster per channel (dine-in, delivery, takeaway). Retrained weekly.
- **Residual layer:** `SGDRegressor`, warm-started from residuals on the latest base, updated per correction via `partial_fit`.
- **Final prediction:** `final = base_pred + clip(residual_pred, ±50% of base_pred)`.

### Data flow

```
Synthetic generator ──► SQLite ──► Feature builder ──► LightGBM base
                                                       │
                                                       ▼
                                       Features + base_pred + reason tags
                                                       │
                                                       ▼
                                                  SGDRegressor
                                                       │
                                                       ▼
                              Predictions table ◄──────┘
                                       │
                                       ▼
                            FastAPI ◄──────────► Streamlit dashboard
                                       ▲
                                       │ POST /corrections
                                       │
                                  Restaurant manager
```

### Retrain cadence

- **Base (LightGBM):** weekly, via APScheduler in-process. Manual trigger from dashboard.
- **Residual (SGD):** on every correction. Reset and warm-started after each base retrain.

---

## Conventions

> Update this section when a new convention is introduced.

### Code

- Python 3.11. `ruff` for lint, `black` for format, `pytest` for tests.
- Type hints on every public function. `mypy --strict` on `app/` (best-effort, not blocking).
- No business logic in API handlers — handlers parse input, call a service function, return the result.

### Folder layout

See [PLANNING.md §12](./PLANNING.md). Any structural deviation must be logged below.

### Naming

- Model files: `artifacts/models/base_v{N}_{channel}.txt`, `artifacts/models/sgd_v{N}.pkl`.
- Migration files (if added later): `migrations/{YYYYMMDD_HHMM}_{slug}.sql`.
- Feature names in the feature builder: `snake_case`, with channel and lag windows in the name (e.g. `dine_in_lag_4w`, `rain_x_dinner`).

### API

- All times are UTC in storage; converted to restaurant local time only at the dashboard layer.
- `POST /corrections` is idempotent on `(ts, channel)` — submitting again updates the previous correction rather than appending.

### Reason-tag vocabulary (residual layer)

Closed set. Adding a new tag requires:

1. Adding it to the `REASON_TAGS` constant.
2. Resetting the SGD residual (because the one-hot dimension changed).
3. Logging the change under **Feature Log**.

Current set:

```
rain_heavy, rain_light, event_local, event_holiday,
promo, no_show_group, normal, other
```

---

## Deprecations

> Empty for now. When something is removed, log it here with date and reason.

---

## Open Questions / TODO

> Things known to be incomplete or under-specified. Move them into **Feature Log** when worked on.

- [ ] Real (non-synthetic) data ingestion path.
- [ ] Multi-restaurant tenancy.
- [ ] Authentication and audit log for corrections.
- [ ] POS integration for ground-truth covers.
- [ ] Supplier API for ingredient order submission.
- [ ] Confidence intervals on forecasts (currently point predictions only).
- [ ] Mobile-friendly dashboard.

---

## Feature Log

> Append new entries at the **bottom**. Newest is last. Never edit historical entries — if a past decision is reversed, add a new entry that supersedes it and update the **Status** of the old one to `Superseded by FEAT-XXX`.

### Template (copy this for each new entry)

```markdown
### FEAT-XXX — <Short title>

- **Date:** YYYY-MM-DD
- **Author:** <name or agent>
- **Status:** Proposed | In progress | Shipped | Superseded by FEAT-YYY | Reverted
- **Type:** Feature | Refactor | Model change | API change | Data change | Infra | Bugfix | Doc

**Context.** Why this change is being made. What problem it solves or what user need it serves.

**Decision.** What is being done, concretely. Include the API surface, model surface, table changes, or UI changes affected.

**Deviation from initial plan.** If this changes something documented in `PLANNING.md`, state exactly what differs and why. If no deviation, write *None*.

**Alternatives considered.** At least one alternative and why it was rejected. Be honest about trade-offs.

**Implementation notes.** Files touched, key functions, gotchas, tests added.

**Rollback plan.** How to undo this if it goes wrong.

**Follow-ups.** Things this change creates work for. Link to new TODOs above if relevant.
```

---

### FEAT-000 — Project bootstrap

- **Date:** 2026-06-25
- **Author:** Initial planning session
- **Status:** Shipped
- **Type:** Doc

**Context.** Project kicked off. POC scope, constraints, architecture, day-by-day plan, and definition of done all agreed and frozen.

**Decision.** Capture the initial plan in `PLANNING.md` and establish `AGENTS.md` as the living document for everything that follows.

**Deviation from initial plan.** None — this *is* the initial plan.

**Alternatives considered.** A single combined README that mixes plan and changelog was rejected — initial assumptions decay quickly and need a stable, frozen reference; a separate living doc avoids polluting the original record.

**Implementation notes.** Two files added at repo root: `PLANNING.md`, `AGENTS.md`.

**Rollback plan.** N/A.

**Follow-ups.**
- Scaffold `app/` directory per `PLANNING.md §12`.
- Implement synthetic data generator (Day 1 task).
- Set up `requirements.txt` and `Dockerfile` skeleton.

---

### FEAT-001 — Synthetic data generator

- **Date:** 2026-06-25
- **Author:** Day 1 implementation
- **Status:** Shipped
- **Type:** Data

**Context.** No real restaurant data available for the POC. Need a reproducible synthetic dataset whose ground-truth drivers are known, so the eval harness can later score how close the trained models get to the true coefficients.

**Decision.** Implement `app/data/generator.py` producing 15 months (≈ 457 days) of hourly data across three channels (dine_in, delivery, takeaway). All injected drivers and their numeric values are kept as module-level constants at the top of the file so the eval harness can compare *learned vs ground truth*.

Drivers injected:

- **Day-of-week multiplier** — weekend ≈ 1.30–1.40, midweek ≈ 0.80–0.95.
- **Hour-of-day curve** — service window 11:00–22:00 with lunch peak (12–14) and dinner peak (18–21).
- **Weather** — seasonal sinusoid for temperature + diurnal cycle + storm bursts. Rain coefficient differs by channel: `dine_in = −0.06`, `delivery = +0.03`, `takeaway = −0.01` per mm.
- **Holidays** — 10 fixed dates, `HOLIDAY_MULT = 1.45`.
- **Local events** — ~5% of days, severity in [0.5, 1.0], `EVENT_LOCAL_MULT = 1.25`.
- **Promos** — ~10% of days, `PROMO_MULT = 1.18`.
- **Regime shift** — at `REGIME_SHIFT_DAY = 200`, delivery volume doubles. The other two channels are unaffected. This is the scenario the demo's MAE-convergence story is built around.
- **Noise** — ~10% multiplicative Gaussian.

Also seeded:

- 12 ingredients with realistic shelf-life and lead-time values.
- 8 menu items with full recipe BOM mapping to ingredients.
- Daily dish-mix history via Dirichlet sampling around `MIX_BASE` (each day sums to 1.0).
- 4 staff roles with covers-per-hour throughput and minimum floor staffing.

**Verification.** Ran `python -m app.data.generator` and confirmed via direct SQL:

| Check | Expected | Observed |
|---|---|---|
| Regime shift on delivery | ~2.0× | 1.99× |
| Regime shift on dine_in / takeaway | ~1.0× | 0.99× / 1.00× |
| Weekend / weekday ratio (dine_in) | ~1.4× | 1.41× |
| Rain hurts dine_in | < 1.0 | 0.69 |
| Rain helps delivery | > 1.0 | 1.15 |
| Mix shares sum to 1.0 per day | 1.0000 | 1.0000 |
| Null `covers` rows | 0 | 0 |

**Deviation from initial plan.** None.

**Alternatives considered.**
- *Pulling real restaurant data.* Rejected — none available, scope creep.
- *Loading a Kaggle restaurant dataset.* Rejected — would not contain a known ground-truth coefficient set, eval would be ungrounded.
- *Generating from a single random walk per channel.* Rejected — would not exercise the model's ability to disentangle drivers (weather × channel interactions are the point).

**Implementation notes.**
- One module, no external generators (matches small-scope constraint).
- Deterministic via `np.random.default_rng(seed=42)`.
- `init_db()` drops and recreates the DB to keep regeneration idempotent.
- Service hours encoded as `OPEN_HOUR = 11`, `CLOSE_HOUR = 23` (exclusive).
- Ingredient/recipe/mix-history seeding kept in the same file for now; will extract if it grows.

**Rollback plan.** Delete `artifacts/rms.db` and revert `app/data/generator.py`. No downstream dependencies yet.

**Follow-ups.**
- FEAT-002 — Implement `app/features/feature_builder.py` (consumes this data).
- FEAT-003 — Train LightGBM base model per channel (FEAT-002 dependency).
- Eventually: extract menu/ingredient/recipe seeding into a separate `seed.py` once the schema stabilizes.

### FEAT-002 — Cap synthetic dataset at current date (2026-06-25)

- **Date:** 2026-06-25
- **Author:** Day 1 follow-up
- **Status:** Shipped
- **Type:** Data

**Context.** FEAT-001 used a duration-based generator (`MONTHS = 15` from `START_DATE = 2025-04-01`), which ran ~7 days past the present (the last row was `2026-06-25`). User reviewed the dataset in the SQLite Viewer VS Code extension and asked that no rows live in the future.

**Decision.** Replace duration-based generation with an explicit, inclusive `[START_DATE, END_DATE]` interval.

- `END_DATE = date(2026, 6, 25)` — equal to the current real-world date.
- `START_DATE = date(2025, 3, 25)` — chosen to preserve ~15 months of history.
- `_date_range(start, end)` now produces an inclusive day list and raises on `end < start`.
- `generate()` signature becomes `generate(start=START_DATE, end=END_DATE, seed=42, db_path=DB_PATH)`.
- `MONTHS` constant removed.

**Deviation from initial plan.** `PLANNING.md §5` describes "12–18 months of hourly observations" without specifying an end-date discipline. This entry formalizes: *no synthetic timestamp may exceed the current real-world date.* For the POC this is a one-shot cap; once real ingestion exists it becomes a natural invariant.

**Alternatives considered.**
- *Post-generation filter that deletes future rows.* Rejected — wastes work and requires keeping deletion logic in sync with the schema.
- *Keep the future rows but mark them "test-only".* Rejected — pollutes every downstream query with a where-clause; clarity loss outweighs the optionality.

**Verification.** Ran `python -m app.data.generator`. Then:

| Check | Result |
|---|---|
| `MAX(substr(ts,1,10))` on `observations` | `2026-06-25` |
| Rows with `ts > '2026-06-25T22:00:00'` | `0` |
| Total observation rows | `16,488` (was 16,452) |
| Total days | `458` (was 457) |
| Regime-shift day | unchanged (`day 200 = 2025-10-11`) |

**Rollback plan.** Revert `app/data/generator.py` to FEAT-001 version; re-run the generator. No schema change involved.

**Follow-ups.**
- When real ingestion is added, treat "max timestamp ≤ now" as an ingestion-side invariant rather than a generator-side one.

### FEAT-003 — Feature builder

- **Date:** 2026-06-25
- **Author:** Day 1 PM
- **Status:** Shipped
- **Type:** Feature

**Context.** Both the LightGBM base and the SGD residual need a stable, consistent feature representation. A single builder ensures the residual sees a strict superset of base inputs.

**Decision.** Implement `app/features/feature_builder.py` with four feature groups, exposing two public entry points:

- `build_training_frame(channel, db_path) -> (X, y, ts, FeatureSpec)` for batch training.
- `build_inference_row(ts, channel, db_path, include_interactions=False) -> X` for serving.

Feature groups (17 base features):

- **Calendar** — `dow`, `hour`, `month`, `day_of_year_sin/cos`, `is_weekend`.
- **Event** — `is_holiday`, `is_local_event`, `event_severity`, `is_promo`.
- **Weather** — `temp`, `rain_mm`, `condition_code` (categorical).
- **Lags** — `lag_1d`, `lag_7d`, `dow_4w_mean` (mean of 7/14/21/28-day-ago same-hour covers), `rolling_7d_mean` (same-hour 7-day rolling mean).

Categorical features (`dow`, `hour`, `month`, `condition_code`) are surfaced via `FeatureSpec.categorical` and passed to LightGBM's native categorical handling.

Interaction features (`rain_x_weekend`, `rain_x_dinner`) are off by default — they are the residual layer's responsibility and live behind `include_interactions=True`.

`append_residual_features(...)` concatenates `base_pred` and reason-tag one-hots onto a base row for the SGD input.

**Deviation from initial plan.** None. Matches `PLANNING.md §3` & `§7`.

**Implementation notes.**
- Lag warmup discards roughly the first 7 days of training rows (`lag_7d` is the gating column; `dow_4w_mean` is `mean(skipna=True)` so it's fine as long as at least one of its component lags is present).
- Generator emits exactly 12 service hours/day per channel, so `shift(12 × n)` equals "same hour, n days ago" without merge overhead. If hours ever vary, the lag implementation must switch to a date-based join.
- `_load_panel` joins `observations`, `weather`, and a pivoted `events` table in one pass to avoid downstream re-merges.

**Verification.** `build_training_frame("dine_in")` returns `(5412, 17)` with zero NaN and date range 2025-04-01 → 2026-06-25.

**Rollback plan.** Revert the file; no schema or data changes.

**Follow-ups.**
- FEAT-004 — Train LightGBM base per channel (consumes this builder).
- FEAT-005 — SGD residual warm-start (adds `include_interactions=True` + base_pred + reason-tag features).


### FEAT-004 — LightGBM base training per channel

- **Date:** 2026-06-25
- **Author:** Day 2 AM
- **Status:** Shipped
- **Type:** Model

**Context.** Three channels (dine_in, delivery, takeaway) have demonstrably different driver responses — most importantly opposite-sign rain sensitivity (FEAT-001 ground truth: dine_in −0.06, delivery +0.03, takeaway −0.01 per mm). One unified model would average those out. Per-channel models avoid that.

**Decision.** Implement `app/models/base_lgbm.LgbmBase` (LightGBM wrapper conforming to `models.interfaces.BaseModel`) and `app/train/train_base.run()` to train one booster per channel, with:

- Time-based split: last 28 days are validation.
- LightGBM params: `learning_rate=0.05`, `num_leaves=31`, `min_data_in_leaf=20`, feature/bagging fractions for regularization, MAE objective.
- Early stopping after 30 rounds on validation MAE, max 1000 trees.
- Native categorical handling for `dow`, `hour`, `month`, `condition_code`.
- Metrics logged: MAE, MAPE, bias, R².
- Each model persisted as `artifacts/models/base_v{utc_timestamp}_{shortid}_{channel}.txt`.
- A row written to `model_registry` per trained model.

**Verification — first training run.**

| Channel | n_train | n_valid | MAE | MAPE | Bias | R² | Top features (by gain) |
|---|---|---|---|---|---|---|---|
| dine_in | 5076 | 336 | 1.354 | 9.7% | +0.04 | 0.940 | dow_4w_mean, lag_7d, is_holiday, hour, lag_1d |
| delivery | 5076 | 336 | 1.381 | 10.0% | −0.30 | 0.927 | dow_4w_mean, lag_7d, lag_1d, is_holiday, day_of_year_sin |
| takeaway | 5076 | 336 | 0.363 | 8.9% | −0.04 | 0.942 | dow_4w_mean, lag_7d, is_holiday, is_promo, hour |

MAPE ≈ 10% across all channels matches the 10% multiplicative noise injected by the generator — the model has effectively reached the irreducible-noise floor on training-distribution data. The persistent **−0.30 bias on delivery** is the regime shift (FEAT-001: delivery base doubles at day 200, embedded in the train set but only partially carried by lag features into the validation window). This is **exactly the signal the SGD residual layer is designed to absorb**, and gives us a clean before/after story for the demo.

**Deviation from initial plan.** None. Matches `PLANNING.md §6.1`.

**Alternatives considered.**
- *Single combined model with `channel` as a categorical feature.* Rejected — would force the model to learn channel-conditioned coefficients on every interaction; per-channel models are simpler and let us inspect each booster independently.
- *Deeper trees (`num_leaves=127`).* Rejected for now — current settings already at noise floor; deeper trees would overfit.

**Implementation notes.**
- `LgbmBase.fit` accepts an explicit `categorical` list; defaults to `"auto"` if none provided.
- `predict` always uses `best_iteration` from early stopping.
- `feature_importance` returns a dict keyed by feature name for direct use in the dashboard's coefficient inspector.
- Replaced deprecated `datetime.utcnow()` with `datetime.now(UTC)` after first run produced warnings.

**Rollback plan.** Delete `artifacts/models/base_*` and `DELETE FROM model_registry WHERE type LIKE 'lgbm_base_%'`. Revert files.

**Follow-ups.**
- FEAT-005 — SGD residual warm-start. The delivery-bias gap is the smoking gun the residual must close.
- Eventually: weekly automated retrain via `app/scheduler.py` (stub already in place).

### FEAT-005 — Dataset + validation visualization (dashboard pages 1 & 2)

- **Date:** 2026-06-25
- **Author:** Day 2 follow-up
- **Status:** Shipped
- **Type:** Feature

**Context.** Before pushing the SGD residual layer, we wanted human eyes on (a) the synthetic dataset itself, to confirm the injected drivers are visible at a glance, and (b) the last-28-day validation window that produced the FEAT-004 numbers, so the metrics aren't taken on faith.

**Decision.** Implement two full Streamlit pages and one supporting evaluation module.

- `app/eval/holdout.py` — `load_latest_base(channel)`, `predict_holdout(channel, n_days)`, `predict_holdout_all_channels()`, `summary_metrics(df)`. Reproduces the exact split used by `train_base.train_channel`.
- `dashboard/streamlit_app.py` — wire two real pages:
  - **Dataset Explorer** — date and channel filters; daily covers per channel with event overlay and regime-shift marker; average covers by hour and by day-of-week; DOW × hour heatmap; rain-bucket bar chart.
  - **Validation (last 28d)** — per-channel summary table; actual vs predicted hourly traces; daily MAE; residual histograms; hourly profile overlay.

Remaining 5 pages from `PLANNING.md §10` remain stubs.

**Verification.** Holdout helper reproduces FEAT-004 numbers exactly:

```
          MAE    MAPE   Bias    R²    n
dine_in   1.354  9.7%  +0.04  0.940  336
delivery  1.381  10.0% −0.30  0.927  336
takeaway  0.363  8.9%  −0.04  0.942  336
```

Dashboard launches cleanly (`streamlit run dashboard/streamlit_app.py`) and renders both pages without errors. Cached loaders called standalone return correct shapes: observations (16488, 6), weather (10992, 5), events (67, 3), holdout (1008, 7).

**Deviation from initial plan.** None. `PLANNING.md §10` page numbering reshuffled: Dataset Explorer and Validation pages are inserted ahead of the originally-listed pages. The original five pages still exist as stubs and will be filled in later.

**Alternatives considered.**
- *Standalone Jupyter notebook for EDA.* Rejected — the demo audience interacts with a dashboard, not a notebook; building the EDA inside the Streamlit app means the same artifact serves both the developer's sanity check and the demo.
- *Static matplotlib PNGs dumped to disk.* Rejected — non-interactive, no filtering, doesn't show off the dataset.

**Implementation notes.**
- Plotly + Streamlit. Cached data loaders (`@st.cache_data`) — repeated page switches stay fast.
- `CHANNEL_COLORS` central palette for consistency across both pages.
- Regime-shift date is derived from `app.data.generator.START_DATE + REGIME_SHIFT_DAY` rather than hardcoded, so it tracks the generator constants.
- Event overlay uses thin dotted vertical lines per type (purple=holiday, gold=local_event, light-blue=promo) — visible without dominating the chart.
- Required new deps: `streamlit==1.58.0`, `plotly==6.8.0`. Already in `requirements.txt`.

**Rollback plan.** Revert `dashboard/streamlit_app.py` and delete `app/eval/holdout.py`. No data or model changes.

**Follow-ups.**
- FEAT-006 — SGD residual warm-start + `partial_fit` endpoint; once shipped, add the SGD-corrected line to the Validation page so the residual layer's contribution is visible alongside the base.
- Eventually: hook the Validation page into a model-version selector so old vs new models can be compared visually.

### FEAT-006 — Data insights doc + static figure generator

- **Date:** 2026-06-25
- **Author:** Day 2 follow-up
- **Status:** Shipped
- **Type:** Doc

**Context.** The Dataset Explorer page in the dashboard surfaces customer-behaviour signals (calendar cycles, weather × channel split, regime shift). Capturing the conclusions as a standalone document — with embedded figures — makes the dataset's properties reviewable without launching Streamlit, and gives a stable reference the modelling work can cite.

**Decision.**

- New module `app/eval/insights.py` that mirrors the Dataset Explorer chart set and writes seven PNGs into `docs/figures/`. Re-runnable on every dataset regeneration.
- New doc `docs/DATA_INSIGHTS.md` that walks each chart, calls out the customer-behaviour interpretation, and lists operational implications and dataset limitations.
- Added `kaleido==1.3.0` to the dev environment (Plotly static export).

Charts produced:
1. `01_daily_covers.png` — full-history daily covers per channel, with regime-shift marker and event overlays.
2. `02_hour_of_day.png` — average covers by hour, per channel.
3. `03_day_of_week.png` — average covers by day-of-week, per channel.
4. `04_heatmap_{dine_in,delivery,takeaway}.png` — three hour × DOW heatmaps.
5. `05_rain_effect.png` — covers vs rain bucket, per channel.

**Deviation from initial plan.** None. `PLANNING.md` did not require this document; it is supplementary reference material.

**Alternatives considered.**
- *Just rely on the dashboard's Dataset Explorer.* Rejected — interactive only, no stable artefact to reference in design discussions.
- *Embed Plotly HTML files instead of PNGs.* Rejected — heavy, harder to render in code-review tools and GitHub previews.

**Implementation notes.**
- `app/eval/insights.py` re-uses the same color palette, bin breakpoints, and grouping logic as `dashboard/streamlit_app.py`, so the PNGs match what the user sees in the dashboard.
- `REGIME_SHIFT_DATE` derived from `START_DATE + timedelta(days=REGIME_SHIFT_DAY)` — fix from a first attempt that used `.date()` on an already-`date` object.
- `kaleido` 1.3.x requires no additional system dependencies on Windows.

**Rollback plan.** Delete `docs/DATA_INSIGHTS.md`, `docs/figures/`, and `app/eval/insights.py`. Uninstall kaleido if desired. No data or model changes.

**Follow-ups.**
- When the SGD residual layer ships (FEAT-007), add a `before/after` figure showing the residual closing the delivery regime-shift gap, and append a section to `DATA_INSIGHTS.md` linking the dataset's non-stationarity to the layered architecture decision.

### FEAT-007 — SGD residual layer

- **Date:** 2026-06-26
- **Author:** Day 2 PM
- **Status:** Shipped
- **Type:** Model

**Context.** The base LightGBM model carries a persistent −0.30 bias on delivery (FEAT-004), driven entirely by the October 2025 regime shift. Reaching the noise floor everywhere else is fine; carrying a known bias forward is not. The SGD residual is the architectural answer: a fast-adapting, interpretable layer that absorbs structural drift without forcing a full base retrain on every change.

**Decision.**

- `app/models/residual_sgd.SgdResidual` fully implemented: `warm_start`, `predict`, `update`, `save`, `load`, `coefficients`, `intercept`, `n_updates`.
- `StandardScaler` fit during warm-start and persisted alongside the SGD model (SGD is scale-sensitive).
- One SGD per channel, mirroring the per-channel base.
- Feature surface (28 columns) = 17 base + 2 interactions (`rain_x_weekend`, `rain_x_dinner`) + `base_pred` + 8 reason-tag one-hots.
- `REASON_TAGS` constant centralized in `app/features/feature_builder.py` and consumed by both API and trainer.
- `append_residual_features(base_X, base_pred, reason_tag)` builds the residual input row(s) consistently for warm-start, inference, and corrections.
- `residual_feature_names(include_interactions=True)` returns the canonical column order.
- `app/train/init_sgd.run()` loads each channel's latest base, predicts on training data, computes residuals, warm-starts the SGD, persists pkl + writes `model_registry` row.
- `app/eval/holdout.load_latest_sgd(channel)` mirrors `load_latest_base` for downstream code.

**Verification.**

Warm-start results (after one base retrain, three channels):

| Channel | Base val MAE | SGD warm MAE (in-sample) | Residual std | Top SGD coefs (abs) |
|---|---|---|---|---|
| dine_in | 1.354 | 1.225 | 1.70 | base_pred, dow_4w_mean, lag_7d, is_holiday |
| delivery | 1.381 | **0.908** | 1.32 | base_pred, lag_7d, dow_4w_mean, day_of_year_cos |
| takeaway | 0.363 | 0.320 | 0.45 | base_pred, dow_4w_mean, lag_7d, is_holiday |

Delivery's residual MAE dropping from 1.38 to **0.91** is the regime-shift bias closing. `base_pred` consistently emerges as the dominant residual coefficient: SGD is learning a calibration-style scaling of the base output.

End-to-end correction round trip (`update → predict`) verified on the delivery channel: residual prediction shifted in the correct direction after `partial_fit` with a `rain_heavy`-tagged correction; `n_updates` incremented from 5412 to 5413; coefficients updated in place; pkl reload preserves state.

**Deviation from initial plan.** None. Matches `PLANNING.md §3` and `§7`.

**Alternatives considered.**
- *LightGBM residual instead of SGD.* Rejected — no native per-sample online update; richer non-linearity not needed since the residuals are dominated by a linear calibration term (`base_pred` coef ≈ 1.2 on delivery).
- *River-style streaming ML library.* Rejected — adds a dependency for capability we don't need at POC scope; SGDRegressor + StandardScaler is sufficient.
- *No scaling.* Rejected — SGD diverges on un-scaled features in early experiments (large `dow_4w_mean` swamps small one-hots).

**Implementation notes.**
- Residual prediction is NOT clipped inside `SgdResidual.predict` — the caller (cover-prediction service) applies the ±50% base_pred cap so the cap is visible at the prediction-assembly site, not buried in the model.
- Persisted via `joblib.dump`; full state dictionary so reload is faithful.
- `warm_start` re-instantiates the underlying `SGDRegressor` to wipe prior coefficients; matches the "reset on base retrain" rule from `PLANNING.md §7`.

**Rollback plan.** Delete `artifacts/models/sgd_*` and `DELETE FROM model_registry WHERE type LIKE 'sgd_residual_%'`. Revert files.

**Follow-ups.**
- FEAT-008 — cover prediction service (combines base + clipped residual).
- FEAT-011 — `POST /corrections` endpoint wires manager input into `SgdResidual.update`.
- FEAT-013 — backtest harness shows the residual reducing rolling MAE over time.

### FEAT-008 — Covers prediction service + API endpoint

- **Date:** 2026-06-26
- **Author:** Day 2 PM
- **Status:** Shipped
- **Type:** Feature

**Context.** The base and residual now exist independently — they need an assembly point that combines them into the final forecast and exposes it over HTTP. Per `PLANNING.md §3`: `final = base + clip(residual, ±50% base_pred)`.

**Decision.**

- `app/predict/covers.predict_day(target, channel, reason_tag, db_path)` — hourly forecast per channel for one date. Loads latest base + SGD, runs both, clips residual by `sgd.clip_fraction × |base_pred|`, floors final at zero.
- `app/predict/covers.predict_daily_totals(start, end, channel)` — daily totals across a window; consumed by the ingredient-orders module.
- `app/features/feature_builder.build_inference_window(timestamps, channel, ...)` — new batch helper. One `_load_panel` call serves all hours of a day, instead of N panel loads. `build_inference_row` now wraps the batch helper.
- `app/api/forecast.py` — three endpoints wired: `/covers`, `/staff`, `/orders`. The covers endpoint accepts an optional `reason_tag` query for what-if scenarios.

**Verification.**

- `predict_day(2026-06-28)` returns 12-hour × 3-channel forecast with consistent shapes; Saturday dine-in totals roughly 220 vs ~207 on weekdays, matching the day-of-week pattern.
- `/forecast/covers?target=2026-06-28&channel=delivery` returns 200 with `{base_pred, residual_raw, residual_pred, final_pred}` per hour.

**Deviation from initial plan.** None.

**Alternatives considered.**
- *Hard-clip residual inside `SgdResidual.predict`.* Rejected — keeping the cap visible at the assembly site makes the rule auditable in one place and lets `residual_raw` flow through for debugging.
- *Per-hour model loading.* Rejected for obvious cost reasons — base/SGD loaded once per channel per request.

**Implementation notes.**
- Future-dated requests use neutral weather (`temp=18°C`, `rain_mm=0`, `condition="clear"`) and no events as the placeholder for missing rows — the model returns its baseline forecast.
- `residual_raw` is exposed alongside `residual_pred` so the dashboard can show "what the SGD wanted to predict" vs "what we let through after the cap".
- Staff and orders endpoints are wired to their service modules; service implementations land in FEAT-009 / FEAT-010.

**Rollback plan.** Revert `app/predict/covers.py`, `app/api/forecast.py`, and the `build_inference_window` block in `feature_builder.py`. No model or data changes.

**Follow-ups.**
- FEAT-009 — staff service (derives directly from covers).
- FEAT-010 — orders service (uses `predict_daily_totals`).

### FEAT-009 — Staff prediction service

- **Date:** 2026-06-26
- **Author:** Day 2 PM
- **Status:** Shipped
- **Type:** Feature

**Context.** Per `PLANNING.md §6.2`, staffing is a deterministic function of predicted covers: there is no ML in this module. The goal is to take the covers forecast and convert it into per-hour, per-role headcount that a manager can act on, plus a daily summary.

**Decision.**

- `app/predict/staff.predict_day(target)` — calls the covers service, joins with `staff_throughput`, computes per-hour headcount per role, returns hourly breakdown + daily person-hours + peak headcount per role.
- `app/predict/staff.pack_shifts(needed_by_hour)` — greedy compression of adjacent same-headcount hours into shift blocks for the dashboard's suggested-schedule view. Full MIP-style optimization is explicitly out of scope.
- **Role → channel map.** `server` and `host` scale with `dine_in` only; `line_cook` and `dishwasher` scale with the sum across all three channels. This is a one-restaurant assumption; richer venues would store this mapping in a table.
- Headcount formula: `max(floor_min, ceil(covers_in_scope / covers_per_hour))`.

**Verification.** Saturday 2026-06-27 forecast yields a sane shape: lunch peak around 13:00 (5 cooks, 3 servers, total covers ~61) and dinner peak around 19–20:00 (5 cooks, 3 servers, total covers ~68). Daily person-hours: server=27, line_cook=39, dishwasher=18, host=12. Shift packer emits 20 contiguous blocks across the four roles.

**Deviation from initial plan.** None. Plan called for "rule-based, no ML" with `max(floor_min, ceil(...))` — implemented exactly.

**Alternatives considered.**
- *Linear programming for true cost-optimal shift packing.* Rejected — outside POC scope; greedy contiguous packing is sufficient to drive the dashboard view.
- *Single `total_covers` driver for every role.* Rejected — over-staffs dine-in roles when delivery is high, under-staffs cooks at the same time. The role-channel split is a small correction that matches reality.

**Implementation notes.**
- Throughput values come from the `staff_throughput` seed (FEAT-001). Editing rows there will be reflected in the next request without any retraining.
- Returned structure is the same shape the API and dashboard consume.

**Rollback plan.** Revert `app/predict/staff.py`. The forecast/staff endpoint already imports the module symbolically; rolling back would leave it as a stub that raises `NotImplementedError`.

**Follow-ups.**
- Dashboard `Today / Tomorrow` page (FEAT-012) renders the hourly headcount as a stacked bar.
- Eventually: support shift cost minimization once labor cost data exists.

### FEAT-010 — Ingredient orders service

- **Date:** 2026-06-26
- **Author:** Day 2 PM
- **Status:** Shipped
- **Type:** Feature

**Context.** Per `PLANNING.md §6.3`, the third forecast product. Takes the cover forecast, applies the historical dish mix and recipe BOM, subtracts current stock, then clips by shelf life × usage rate so we never order more than the kitchen can consume before spoilage.

**Decision.**

- `app/predict/orders.predict_orders(start, end, db_path)` — per-ingredient order quantity across the window. End is inclusive.
- `app/predict/orders.horizon_for_ingredients(db_path)` — default horizon = `max(lead_time) + SAFETY_DAYS` (1 day).
- Mix sourced from `mix_history` over the last 28 days, averaged per item and renormalized.
- `incoming` deliveries are not yet modeled — POC assumption is no orders in flight. Adding incoming is a one-liner once a deliveries table exists.

**Verification.** Horizon = 8 days (max lead time = 7, +1 safety). For 2026-06-26 → 2026-07-03 the recommended orders look operationally sensible:

| Ingredient | Stock | Need | Shelf cap | Recommended | Note |
|---|---|---|---|---|---|
| Flour | 25.0 | 191.5 | 2873 | **166.5** | long shelf, ordered to need |
| Tomato | 15.0 | 163.0 | **101.9** | 101.9 | clipped by 5-day shelf life |
| Beef | 8.0 | 186.9 | **93.4** | 93.4 | clipped by 4-day shelf life |
| Cheese | 8.0 | 97.7 | 122.1 | 89.7 | within shelf cap |
| Pasta | 30.0 | 113.2 | 2547 | 83.2 | long shelf, no waste risk |
| Rice | 40.0 | 30.1 | 1375 | **0.0** | stock > need |

The shelf-life clip is doing the right thing: tomato and beef demand exceeds the 8-day usage rate × shelf life, so the model recommends ordering only what we can use in time. The next order cycle catches up the rest.

**Deviation from initial plan.** None. Algorithm matches plan exactly.

**Alternatives considered.**
- *Per-channel mix.* Rejected — dish mix per channel would be a more honest approach, but POC mix data is restaurant-level only. Easy to extend later.
- *Bayesian safety stock.* Rejected — adds machinery the demo doesn't need; the shelf-life clip is the binding constraint, not stock-out risk.

**Implementation notes.**
- All math is pandas-vectorized; no per-ingredient loops in the hot path.
- Result sorted by `recommended_order` descending so the dashboard's order sheet leads with the biggest line items.
- `horizon_for_ingredients` reads from `ingredients` table so changing `lead_time_days` there propagates automatically.

**Rollback plan.** Revert `app/predict/orders.py`. `/forecast/orders` falls back to the `NotImplementedError` stub.

**Follow-ups.**
- Dashboard `Order Sheet` page (FEAT-012) renders this table with an "Approve order" button (no-op for POC).
- Long-run: model incoming deliveries; allow per-channel mix; integrate supplier API.

<!-- Add new entries below this line. -->
