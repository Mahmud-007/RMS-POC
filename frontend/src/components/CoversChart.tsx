import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHANNELS, CHANNEL_COLORS, CHANNEL_LABELS } from "../lib/types";
import type { DayForecast } from "../lib/types";

export default function CoversChart({ forecast }: { forecast: DayForecast }) {
  // Build per-hour rows: { hour, dine_in, delivery, takeaway }
  const hours = forecast.covers.dine_in.map((r) => r.hour);
  const data = hours.map((hour, i) => {
    const row: Record<string, number | string> = { hour: `${hour}:00` };
    for (const ch of CHANNELS) {
      row[ch] = Math.round((forecast.covers[ch][i]?.final_pred ?? 0) * 10) / 10;
    }
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={340}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
        <XAxis dataKey="hour" tick={{ fontSize: 12, fill: "#64748b" }} />
        <YAxis tick={{ fontSize: 12, fill: "#64748b" }} />
        <Tooltip
          contentStyle={{
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            fontSize: 13,
          }}
        />
        <Legend
          formatter={(v) => CHANNEL_LABELS[v as keyof typeof CHANNEL_LABELS] ?? v}
        />
        {CHANNELS.map((ch) => (
          <Bar key={ch} dataKey={ch} stackId="covers" fill={CHANNEL_COLORS[ch]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
