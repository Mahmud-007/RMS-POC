import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { tomorrowISO, prettyDate, n0, n1 } from "../lib/format";
import { Card, ErrorBox, SectionTitle, Spinner, Badge } from "../components/ui";
import WeatherCard from "../components/WeatherCard";
import CoversChart from "../components/CoversChart";
import { CHANNELS, CHANNEL_LABELS, REASON_TAGS } from "../lib/types";
import type { ReasonTag } from "../lib/types";

const SCENARIO_LABELS: Record<string, string> = {
  normal: "Use live forecast",
  rain_light: "What if: light rain",
  rain_heavy: "What if: heavy rain",
  event_holiday: "What if: holiday",
  event_local: "What if: local event",
  promo: "What if: promo running",
  no_show_group: "What if: no-show group",
  other: "What if: other",
};

const ROLES = ["server", "line_cook", "dishwasher", "host"];
const ROLE_LABELS: Record<string, string> = {
  server: "Servers",
  line_cook: "Cooks",
  dishwasher: "Dish",
  host: "Host",
};

export default function Forecast() {
  const [date, setDate] = useState(tomorrowISO());
  const [scenario, setScenario] = useState<ReasonTag>("normal");

  const day = useQuery({
    queryKey: ["day", date, scenario],
    queryFn: () => api.dayForecast(date, scenario, true),
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Forecast</h1>
        <p className="text-slate-500 text-sm mt-1">
          Hourly customer forecast and staffing plan for {prettyDate(date)}.
        </p>
      </div>

      {/* Controls */}
      <Card className="p-4 mb-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-500">Date</span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 flex-1">
            <span className="text-xs font-medium text-slate-500">
              Scenario
            </span>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value as ReasonTag)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
            >
              {REASON_TAGS.map((t) => (
                <option key={t} value={t}>
                  {SCENARIO_LABELS[t] ?? t}
                </option>
              ))}
            </select>
          </label>
        </div>
        {scenario !== "normal" && (
          <div className="mt-3">
            <Badge tone="amber">
              What-if mode — overriding the live forecast with “{scenario}”
            </Badge>
          </div>
        )}
      </Card>

      {day.isLoading && <Spinner label="Crunching the forecast…" />}
      {day.error && <ErrorBox message={(day.error as Error).message} />}

      {day.data && (
        <>
          {/* Totals + weather */}
          <div className="grid md:grid-cols-4 gap-3 mb-4">
            <Card className="p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Total customers
              </div>
              <div className="mt-1 text-3xl font-bold text-slate-900">
                {n0(day.data.totals.all)}
              </div>
            </Card>
            {CHANNELS.map((ch) => (
              <Card key={ch} className="p-4">
                <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {CHANNEL_LABELS[ch]}
                </div>
                <div className="mt-1 text-3xl font-bold text-slate-900">
                  {n0(day.data!.totals[ch])}
                </div>
              </Card>
            ))}
          </div>

          <div className="grid md:grid-cols-3 gap-3 mb-6">
            <div className="md:col-span-1">
              <WeatherCard weather={day.data.weather} />
            </div>
            <Card className="md:col-span-2 p-4">
              <SectionTitle>Hourly customer forecast</SectionTitle>
              <CoversChart forecast={day.data} />
            </Card>
          </div>

          {/* Staffing */}
          <SectionTitle>Recommended staffing</SectionTitle>
          <Card className="p-0 overflow-x-auto mb-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="px-4 py-2 font-medium">Hour</th>
                  <th className="px-4 py-2 font-medium">Customers</th>
                  {ROLES.map((r) => (
                    <th key={r} className="px-4 py-2 font-medium">
                      {ROLE_LABELS[r]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {day.data.staff.hourly.map((h) => (
                  <tr key={h.hour} className="border-b border-slate-50">
                    <td className="px-4 py-2 text-slate-700">{h.hour}:00</td>
                    <td className="px-4 py-2 text-slate-700">
                      {n1(h.covers_total)}
                    </td>
                    {ROLES.map((r) => (
                      <td key={r} className="px-4 py-2 font-medium text-slate-900">
                        {h.headcount[r]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {ROLES.map((r) => (
              <Card key={r} className="p-4">
                <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {ROLE_LABELS[r]} · person-hours
                </div>
                <div className="mt-1 text-2xl font-bold text-slate-900">
                  {n0(day.data!.staff.person_hours[r])}
                </div>
                <div className="text-xs text-slate-500">
                  peak {day.data!.staff.peak_headcount[r]}
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
