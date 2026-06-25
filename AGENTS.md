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

<!-- Add new entries below this line. -->
