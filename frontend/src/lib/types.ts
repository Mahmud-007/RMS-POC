// Types mirroring the FastAPI response shapes.

export type Channel = "dine_in" | "delivery" | "takeaway";

export const CHANNELS: Channel[] = ["dine_in", "delivery", "takeaway"];

export const CHANNEL_LABELS: Record<Channel, string> = {
  dine_in: "Dine-in",
  delivery: "Delivery",
  takeaway: "Takeaway",
};

export const CHANNEL_COLORS: Record<Channel, string> = {
  dine_in: "#2563eb",
  delivery: "#f97316",
  takeaway: "#16a34a",
};

export const REASON_TAGS = [
  "normal",
  "rain_light",
  "rain_heavy",
  "event_holiday",
  "event_local",
  "promo",
  "no_show_group",
  "other",
] as const;
export type ReasonTag = (typeof REASON_TAGS)[number];

export interface HourCover {
  ts: string;
  hour: number;
  base_pred: number;
  residual_raw: number;
  residual_pred: number;
  final_pred: number;
}

export interface WeatherSummary {
  date: string;
  avg_temp: number;
  total_rain_mm: number;
  peak_rain_mm: number;
  label: string;
  source: string;
  lat: number;
  lon: number;
}

export interface StaffHour {
  hour: number;
  covers: Record<Channel, number>;
  covers_total: number;
  headcount: Record<string, number>;
}

export interface StaffPlan {
  target: string;
  hourly: StaffHour[];
  person_hours: Record<string, number>;
  peak_headcount: Record<string, number>;
}

export interface DayForecast {
  date: string;
  reason_tag: string;
  weather: WeatherSummary | null;
  covers: Record<Channel, HourCover[]>;
  totals: Record<Channel, number> & { all: number };
  staff: StaffPlan;
}

export interface OrderLine {
  ingredient_id: number;
  name: string;
  unit: string;
  lead_time_days: number;
  shelf_life_days: number;
  stock_on_hand: number;
  forecast_need: number;
  raw_order: number;
  shelf_cap: number;
  recommended_order: number;
  horizon_start: string;
  horizon_end: string;
  horizon_days: number;
}

export interface CorrectionResult {
  base_pred: number;
  residual_pred_before: number;
  residual_pred_after: number;
  actual: number;
  target_residual: number;
  target_residual_clipped: number;
  n_updates: number;
  model_version: string;
}

export interface AccuracyChannel {
  mae: number;
  mape: number;
  bias: number;
  r2: number;
  n: number;
  accuracy: number;
}

export interface AccuracyResponse {
  n_days: number;
  overall_accuracy: number;
  overall_mape: number;
  channels: Record<string, AccuracyChannel>;
}

export interface ChannelMetrics {
  rolling: {
    n: number;
    mae: number | null;
    mape: number | null;
    bias: number | null;
    r2: number | null;
  };
  rolling_days: number;
  n_corrections: number;
  sgd_n_updates: number;
  sgd_fitted: boolean;
}
