import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { tomorrowISO, prettyDate, n0, pct, addDays, isoDate } from "../lib/format";
import { Card, ErrorBox, MetricCard, SectionTitle, Spinner } from "../components/ui";
import WeatherCard from "../components/WeatherCard";
import { CHANNELS, CHANNEL_LABELS } from "../lib/types";

export default function Home() {
  const date = tomorrowISO();

  const day = useQuery({
    queryKey: ["day", date],
    queryFn: () => api.dayForecast(date),
  });

  const accuracy = useQuery({
    queryKey: ["accuracy", 28],
    queryFn: () => api.accuracy(28),
  });

  const orders = useQuery({
    queryKey: ["orders-home"],
    queryFn: () => api.orders(tomorrowISO(), isoDate(addDays(new Date(), 8))),
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Good day 👋</h1>
        <p className="text-slate-500 text-sm mt-1">
          Here is what to expect for {prettyDate(date)}.
        </p>
      </div>

      {day.isLoading && <Spinner label="Loading tomorrow's outlook…" />}
      {day.error && <ErrorBox message={(day.error as Error).message} />}

      {day.data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <MetricCard
              label="Expected customers"
              value={n0(day.data.totals.all)}
              sub={prettyDate(date)}
              accent="blue"
            />
            <MetricCard
              label="Cooks at peak"
              value={n0(day.data.staff.peak_headcount["line_cook"])}
              sub={`${n0(day.data.staff.person_hours["line_cook"])} cook-hours total`}
              accent="orange"
            />
            <MetricCard
              label="Servers at peak"
              value={n0(day.data.staff.peak_headcount["server"])}
              sub={`${n0(day.data.staff.person_hours["server"])} server-hours total`}
              accent="green"
            />
            <MetricCard
              label="Forecast accuracy"
              value={
                accuracy.data ? pct(accuracy.data.overall_accuracy) : "—"
              }
              sub={
                accuracy.data
                  ? `measured on last ${accuracy.data.n_days} days`
                  : "measuring…"
              }
              accent="slate"
            />
          </div>

          <div className="grid md:grid-cols-3 gap-3 mb-6 items-stretch">
            <WeatherCard weather={day.data.weather} className="md:col-span-1" />
            <Card className="md:col-span-2 p-4 flex flex-col">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Channel breakdown
              </div>
              <div className="grid grid-cols-3 gap-3 flex-1 items-center">
                {CHANNELS.map((ch) => (
                  <div key={ch}>
                    <div className="text-sm text-slate-500">
                      {CHANNEL_LABELS[ch]}
                    </div>
                    <div className="text-2xl font-bold text-slate-900">
                      {n0(day.data!.totals[ch])}
                    </div>
                  </div>
                ))}
              </div>
              <Link
                to="/forecast"
                className="text-sm font-medium text-blue-600 hover:underline"
              >
                See hourly forecast →
              </Link>
            </Card>
          </div>
        </>
      )}

      <SectionTitle>Orders due soon</SectionTitle>
      {orders.isLoading && <Spinner />}
      {orders.data && (
        <Card className="p-4">
          <div className="divide-y divide-slate-100">
            {orders.data
              .filter((o) => o.recommended_order > 0)
              .slice(0, 5)
              .map((o) => (
                <div
                  key={o.ingredient_id}
                  className="flex items-center justify-between py-2"
                >
                  <span className="text-sm text-slate-700">{o.name}</span>
                  <span className="text-sm font-medium text-slate-900">
                    {o.recommended_order.toFixed(1)} {o.unit}
                  </span>
                </div>
              ))}
          </div>
          <Link
            to="/orders"
            className="inline-block mt-3 text-sm font-medium text-blue-600 hover:underline"
          >
            View full order sheet →
          </Link>
        </Card>
      )}
    </div>
  );
}
