# Deploying RRPS on Render

The whole system deploys from one `render.yaml` Blueprint: a stateful **backend**
(FastAPI + models + a persistent disk) and a stateless **frontend** (React static
site on Render's CDN).

> **Why a persistent disk?** Every manager correction calls `sgd.partial_fit()` and
> rewrites `artifacts/models/sgd_*.pkl`. That file IS the accumulated learning. On an
> ephemeral filesystem it's wiped on every restart and the model forgets all
> corrections. The disk is what makes the feedback loop real. See the cost note below.

---

## Cost

| Path | Backend plan | Disk | Cost | Learning persists? |
|---|---|---|---|---|
| **Real pilot** (recommended) | Starter | 1 GB | ~$7/mo | ✅ yes |
| **Demo only** | Free | none | $0 | ❌ resets when the service sleeps |

The frontend static site is **free** on either path.

To switch to the free/demo path: in `render.yaml`, set the backend `plan: free` and
delete the `disk:` block.

---

## One-time deploy (Blueprint)

1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. Render Dashboard → **New** → **Blueprint**.
3. Connect the repo. Render reads `render.yaml` and shows two services:
   `rrps-backend` and `rrps-frontend`.
4. For the **paid path**, confirm the Starter plan + disk when prompted (needs a card).
5. Click **Apply**. Render builds both. The backend's first boot runs `start.sh`,
   which generates the dataset and trains the models onto the disk (~1–2 min).

## Wire the two together (after first deploy)

The frontend needs the backend's URL baked in at build time:

1. Copy the backend URL from Render, e.g. `https://rrps-backend.onrender.com`.
2. Frontend service → **Environment** → set `VITE_API_BASE` to that URL.
3. Frontend → **Manual Deploy** → **Clear build cache & deploy** (so Vite re-bakes it).

CORS needs no manual step — the backend already allows any `*.onrender.com` origin.
(If you later move the frontend to a custom domain, add it to `RMS_CORS_ORIGINS` on
the backend.)

## Verify

- Backend: open `https://rrps-backend.onrender.com/health` → `{"status":"ok"}`.
  API docs at `/docs`.
- Frontend: open the static-site URL → Home loads tomorrow's forecast.
- Feedback page → submit a correction → it persists (on the paid/disk path) across a
  manual restart of the backend.

---

## Notes & gotchas

- **`--workers 1`** (set in `start.sh`): corrections rewrite a file on disk; a single
  worker avoids two requests racing on it. Fine for a single restaurant.
- **Free tier sleep:** free backends sleep after 15 min idle; the first request after
  wake takes ~60 s (cold start + bootstrap). The Starter plan does not sleep.
- **Weekly auto-retrain** (APScheduler) only fires while the backend is awake — i.e.
  reliably only on the always-on Starter plan. The manual retrain endpoint works
  regardless.
- **LightGBM needs OpenMP.** Render's native Python runtime includes `libgomp`, so the
  native build works. If a build ever fails on a missing OpenMP library, switch the
  backend service to a Docker runtime (the repo's `Dockerfile` already installs
  `libgomp1`).
- **Location:** `RMS_LAT` / `RMS_LON` / `RMS_TZ` env vars set the weather-forecast
  location. Defaults point at Dhaka.
- **Weather API limits (Open-Meteo):** free, key-less, ~10,000 calls/day (the app
  caches per date, so real usage is a handful/day — well within limits). The free
  tier is **non-commercial**; a paying production restaurant should switch to
  Open-Meteo's commercial endpoint + API key (one-line change in
  `app/integrations/weather.py`) or self-host their open-source server.

---

## Frontend on Netlify instead (alternative)

If you prefer Netlify for the frontend, the repo already has `frontend/netlify.toml`
and `frontend/public/_redirects`:

1. Netlify → Add new site → import the repo.
2. Base directory `frontend`, build `npm run build`, publish `frontend/dist`.
3. Set `VITE_API_BASE` to the Render backend URL.
4. Deploy. (The backend already allows `*.netlify.app` via CORS.)
