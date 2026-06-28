import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHANNELS, CHANNEL_COLORS, CHANNEL_LABELS } from "../lib/types";
import type { DayForecast } from "../lib/types";

export default function ChannelTotalsChart({
  forecast,
}: {
  forecast: DayForecast;
}) {
  const data = CHANNELS.map((ch) => ({
    name: CHANNEL_LABELS[ch],
    value: Math.round((forecast.totals[ch] ?? 0) * 10) / 10,
    fill: CHANNEL_COLORS[ch],
  }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <BarChart data={data} margin={{ top: 20, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#64748b" }} />
        <YAxis tick={{ fontSize: 12, fill: "#64748b" }} />
        <Tooltip
          contentStyle={{
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            fontSize: 13,
          }}
          formatter={(v: number) => [`${v} customers`, "Day total"]}
        />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={90}>
          {data.map((d) => (
            <Cell key={d.name} fill={d.fill} />
          ))}
          <LabelList
            dataKey="value"
            position="top"
            style={{ fontSize: 13, fontWeight: 600, fill: "#0f172a" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
