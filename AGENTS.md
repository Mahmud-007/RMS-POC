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

**Context.** FEAT-001 used a duration-based generator (`MONTHS = 15` from `START_DATE = 2025-04-01`), which ran ~7 days past the present (the last row was `2026-07-02`). User reviewed the dataset in the SQLite Viewer VS Code extension and asked that no rows live in the future.

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

<!-- Add new entries below this line. -->
