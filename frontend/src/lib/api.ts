import type {
  AccuracyResponse,
  ChannelMetrics,
  CorrectionResult,
  DayForecast,
  ForecastOverrides,
  OrderLine,
  ReasonTag,
  WeatherSummary,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${detail}`);
  }
  return res.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  base: BASE,

  health: () => getJSON<{ status: string }>("/health"),

  dayForecast: (date: string, overrides: ForecastOverrides = {}) => {
    const p = new URLSearchParams({ target: date });
    p.set("use_weather", String(overrides.use_weather ?? true));
    if (overrides.rain_mm != null) p.set("rain_mm", String(overrides.rain_mm));
    if (overrides.temp != null) p.set("temp", String(overrides.temp));
    if (overrides.is_holiday != null) p.set("is_holiday", String(overrides.is_holiday));
    if (overrides.is_promo != null) p.set("is_promo", String(overrides.is_promo));
    if (overrides.is_local_event != null)
      p.set("is_local_event", String(overrides.is_local_event));
    return getJSON<DayForecast>(`/forecast/day?${p.toString()}`);
  },

  weather: (date: string) =>
    getJSON<{ available: boolean } & Partial<WeatherSummary>>(
      `/forecast/weather?target=${date}`,
    ),

  orders: (start: string, end: string) =>
    getJSON<OrderLine[]>(`/forecast/orders?start=${start}&end=${end}`),

  metrics: (rollingDays = 30) =>
    getJSON<Record<string, ChannelMetrics>>(`/metrics?rolling_days=${rollingDays}`),

  accuracy: (nDays = 28) =>
    getJSON<AccuracyResponse>(`/metrics/accuracy?n_days=${nDays}`),

  submitCorrection: (body: {
    ts: string;
    channel: string;
    actual: number;
    reason_tag: ReasonTag;
  }) => postJSON<CorrectionResult>("/corrections", body),
};
