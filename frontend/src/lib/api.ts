import type {
  AccuracyResponse,
  ChannelMetrics,
  CorrectionResult,
  DayForecast,
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

  dayForecast: (date: string, reasonTag: ReasonTag = "normal", useWeather = true) =>
    getJSON<DayForecast>(
      `/forecast/day?target=${date}&reason_tag=${reasonTag}&use_weather=${useWeather}`,
    ),

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
