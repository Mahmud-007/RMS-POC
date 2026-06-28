import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { tomorrowISO, prettyDate, n0, n1 } from "../lib/format";
import { Card, ErrorBox, SectionTitle, Spinner, Badge } from "../components/ui";
import WeatherCard from "../components/WeatherCard";
import CoversChart from "../components/CoversChart";
import ChannelTotalsChart from "../components/ChannelTotalsChart";
import { CHANNELS, CHANNEL_LABELS } from "../lib/types";
import type { ForecastOverrides } from "../lib/types";

const ROLES = ["server", "line_cook", "dishwasher", "host"];
const ROLE_LABELS: Record<string, string> = {
  server: "Servers",
  line_cook: "Cooks",
  dishwasher: "Dish",
  host: "Host",
};

export default function Forecast() {
  const [date, setDate] = useState(tomorrowISO());

  // Weather override state
  const [overrideWeather, setOverrideWeather] = useState(false);
  const [rain, setRain] = useState(0);
  const [temp, setTemp] = useState(18);

  // Event toggles (the system can't know these from any API)
  const [holiday, setHoliday] = useState(false);
  const [promo, setPromo] = useState(false);
  const [localEvent, setLocalEvent] = useState(false);

  // Live weather, used to pre-fill the editable fields.
  const weather = useQuery({
    queryKey: ["weather", date],
    queryFn: () => api.weather(date),
  });

  // When the live forecast loads (and the manager hasn't taken manual control),
  // pre-fill the editable fields with the real values.
  useEffect(() => {
    if (weather.data?.available && !overrideWeather) {
      if (weather.data.peak_rain_mm != null) setRain(weather.data.peak_rain_mm);
      if (weather.data.avg_temp != null) setTemp(weather.data.avg_temp);
    }
  }, [weather.data, overrideWeather]);

  const overrides: ForecastOverrides = {
    use_weather: !overrideWeather, // when overriding, ignore the live baseline for weather
    rain_mm: overrideWeather ? rain : null,
    temp: overrideWeather ? temp : null,
    is_holiday: holiday ? true : null,
    is_promo: promo ? true : null,
    is_local_event: localEvent ? true : null,
  };

  const day = useQuery({
    queryKey: ["day", date, overrides],
    queryFn: () => api.dayForecast(date, overrides),
  });

  const anyEvent = holiday || promo || localEvent;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Customer &amp; Staff Forecast
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Expected customers and the staffing it calls for on {prettyDate(date)}.
        </p>
      </div>

      {/* Controls */}
      <div className="grid md:grid-cols-3 gap-3 mb-4">
        {/* Date */}
        <Card className="p-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-500">Date</span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
          </label>
        </Card>

        {/* Weather — live, editable if the manager disagrees */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-slate-500">Weather</span>
            <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={overrideWeather}
                onChange={(e) => setOverrideWeather(e.target.checked)}
              />
              Override forecast
            </label>
          </div>

          {!overrideWeather ? (
            <div className="text-sm text-slate-700">
              {weather.data?.available ? (
                <>
                  <span className="font-semibold">{weather.data.label}</span>{" "}
                  <span className="text-slate-500">
                    · {weather.data.avg_temp}°C · {weather.data.total_rain_mm}mm
                  </span>
                  <div className="text-xs text-slate-400 mt-1">
                    From live forecast — tick “Override” to adjust.
                  </div>
                </>
              ) : (
                <span className="text-slate-400">
                  No live forecast for this date.
                </span>
              )}
            </div>
          ) : (
            <div className="flex gap-3">
              <label className="flex flex-col gap-1 flex-1">
                <span className="text-xs text-slate-500">Rain (mm)</span>
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  value={rain}
                  onChange={(e) => setRain(Number(e.target.value))}
                  className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 flex-1">
                <span className="text-xs text-slate-500">Temp (°C)</span>
                <input
                  type="number"
                  step={1}
                  value={temp}
                  onChange={(e) => setTemp(Number(e.target.value))}
                  className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm"
                />
              </label>
            </div>
          )}
        </Card>

        {/* Events — manual, the system can't know these */}
        <Card className="p-4">
          <span className="text-xs font-medium text-slate-500">
            Known events
          </span>
          <div className="mt-2 flex flex-col gap-1.5">
            <Toggle label="Public holiday" checked={holiday} onChange={setHoliday} />
            <Toggle label="Promo running" checked={promo} onChange={setPromo} />
            <Toggle label="Local event" checked={localEvent} onChange={setLocalEvent} />
          </div>
        </Card>
      </div>

      {(overrideWeather || anyEvent) && (
        <div className="mb-4 flex gap-2 flex-wrap">
          {overrideWeather && (
            <Badge tone="amber">
              Manual weather: {rain}mm · {temp}°C
            </Badge>
          )}
          {holiday && <Badge tone="blue">Holiday</Badge>}
          {promo && <Badge tone="blue">Promo</Badge>}
          {localEvent && <Badge tone="blue">Local event</Badge>}
        </div>
      )}

      {day.isLoading && <Spinner label="Crunching the forecast…" />}
      {day.error && <ErrorBox message={(day.error as Error).message} />}

      {day.data && (
        <>
          {/* Totals */}
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

          {/* Weather summary card + two charts */}
          <div className="grid md:grid-cols-3 gap-3 mb-3">
            <WeatherCard weather={day.data.weather} />
          </div>
          <div className="grid lg:grid-cols-2 gap-3 mb-6">
            <Card className="p-4">
              <SectionTitle>Hourly customer forecast</SectionTitle>
              <CoversChart forecast={day.data} />
            </Card>
            <Card className="p-4">
              <SectionTitle>Whole day by channel</SectionTitle>
              <ChannelTotalsChart forecast={day.data} />
            </Card>
          </div>

          {/* Staffing */}
          <SectionTitle>Recommended staffing</SectionTitle>
          <Card className="p-0 overflow-x-auto mb-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="px-4 py-2 font-medium">Hour</th>
                  <th
                    className="px-2 py-2 font-medium text-center border-l border-slate-100"
                    colSpan={CHANNELS.length + 1}
                  >
                    Customers
                  </th>
                  <th
                    className="px-2 py-2 font-medium text-center border-l border-slate-100"
                    colSpan={ROLES.length}
                  >
                    Staff needed
                  </th>
                </tr>
                <tr className="text-left text-slate-400 border-b border-slate-200 text-xs">
                  <th className="px-4 py-1.5 font-medium"></th>
                  {CHANNELS.map((ch, i) => (
                    <th
                      key={ch}
                      className={`px-2 py-1.5 font-medium ${i === 0 ? "border-l border-slate-100" : ""}`}
                    >
                      {CHANNEL_LABELS[ch]}
                    </th>
                  ))}
                  <th className="px-2 py-1.5 font-medium">Total</th>
                  {ROLES.map((r, i) => (
                    <th
                      key={r}
                      className={`px-2 py-1.5 font-medium ${i === 0 ? "border-l border-slate-100" : ""}`}
                    >
                      {ROLE_LABELS[r]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {day.data.staff.hourly.map((h) => (
                  <tr key={h.hour} className="border-b border-slate-50">
                    <td className="px-4 py-2 text-slate-700">{h.hour}:00</td>
                    {CHANNELS.map((ch, i) => (
                      <td
                        key={ch}
                        className={`px-2 py-2 text-slate-600 ${i === 0 ? "border-l border-slate-100" : ""}`}
                      >
                        {n1(h.covers[ch])}
                      </td>
                    ))}
                    <td className="px-2 py-2 font-medium text-slate-800">
                      {n1(h.covers_total)}
                    </td>
                    {ROLES.map((r, i) => (
                      <td
                        key={r}
                        className={`px-2 py-2 font-medium text-slate-900 ${i === 0 ? "border-l border-slate-100" : ""}`}
                      >
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

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}
