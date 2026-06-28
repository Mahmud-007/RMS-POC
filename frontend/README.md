# RMS Frontend (React)

Manager-facing dashboard for the RMS forecasting system. Vite + React + TypeScript + Tailwind v4 + TanStack Query + Recharts. Consumes the FastAPI backend.

## Pages

| Route | Page | What it shows |
|---|---|---|
| `/` | Home | KPI cards (tomorrow's customers, peak staff, accuracy), weather, top orders |
| `/forecast` | Forecast | Date + scenario picker, weather card, hourly stacked covers chart, staffing table |
| `/orders` | Orders | Horizon slider, ingredient cards with stock-vs-need bars + shelf-life flags |
| `/feedback` | Feedback | Submit actual covers + reason; shows the model's immediate adjustment |

## Local development

The frontend needs the backend running. From the repo root, in one terminal:

```bash
uvicorn app.main:app --reload          # → http://localhost:8000
```

Then in this folder:

```bash
npm install
cp .env.example .env                    # VITE_API_BASE=http://localhost:8000
npm run dev                             # → http://localhost:5173
```

Open <http://localhost:5173>.

## Configuration

`VITE_API_BASE` points the app at the backend. Local default is `http://localhost:8000`. For a deployed build (Netlify), set it to the Render API URL:

```
VITE_API_BASE=https://your-api.onrender.com
```

## Build

```bash
npm run build      # type-check + production build → dist/
npm run preview    # preview the production build locally
```

## Deploy (Netlify)

- Base directory: `frontend`
- Build command: `npm run build`
- Publish directory: `frontend/dist`
- Environment variable: `VITE_API_BASE` = your Render API URL
- SPA redirect: add a `_redirects` file or Netlify rule sending `/*` → `/index.html` (200) so client-side routes work on refresh.
