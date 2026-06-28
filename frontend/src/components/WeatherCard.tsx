import type { WeatherSummary } from "../lib/types";
import { Card } from "./ui";

const ICONS: Record<string, string> = {
  Clear: "☀️",
  "Light rain": "🌦️",
  "Heavy rain": "🌧️",
  Hot: "🔥",
  Cold: "❄️",
};

export default function WeatherCard({
  weather,
}: {
  weather: WeatherSummary | null;
}) {
  if (!weather) {
    return (
      <Card className="p-4">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Weather
        </div>
        <div className="mt-1 text-sm text-slate-500">
          No forecast available for this date (outside the ~16-day horizon).
        </div>
      </Card>
    );
  }
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Weather forecast
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {weather.label}
          </div>
          <div className="mt-0.5 text-xs text-slate-500">
            {weather.avg_temp}°C avg · {weather.total_rain_mm} mm rain
          </div>
        </div>
        <div className="text-4xl">{ICONS[weather.label] ?? "🌤️"}</div>
      </div>
    </Card>
  );
}
