import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { tomorrowISO, addDays, isoDate, prettyDate, n1 } from "../lib/format";
import { Card, ErrorBox, Spinner, Badge } from "../components/ui";

export default function Orders() {
  const [horizon, setHorizon] = useState(8);
  const start = tomorrowISO();
  const end = isoDate(addDays(new Date(start + "T00:00:00"), horizon - 1));

  const orders = useQuery({
    queryKey: ["orders", start, end],
    queryFn: () => api.orders(start, end),
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Supplies to Order</h1>
        <p className="text-slate-500 text-sm mt-1">
          Ingredients to buy for {prettyDate(start)} – {prettyDate(end)}, based on the
          forecast, what's in stock, and each item's shelf life.
        </p>
      </div>

      <Card className="p-4 mb-4">
        <label className="flex flex-col gap-1 max-w-xs">
          <span className="text-xs font-medium text-slate-500">
            Order horizon: {horizon} days
          </span>
          <input
            type="range"
            min={1}
            max={21}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
          />
        </label>
      </Card>

      {orders.isLoading && <Spinner label="Calculating orders…" />}
      {orders.error && <ErrorBox message={(orders.error as Error).message} />}

      {orders.data && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {orders.data.map((o) => {
            const capped = o.shelf_cap < o.raw_order - 1e-6;
            const fillPct = Math.min(
              100,
              (o.stock_on_hand / Math.max(o.forecast_need, 1)) * 100,
            );
            return (
              <Card key={o.ingredient_id} className="p-4">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900">{o.name}</span>
                  {capped && <Badge tone="amber">shelf-life capped</Badge>}
                </div>

                <div className="mt-3 text-3xl font-bold text-slate-900">
                  {o.recommended_order.toFixed(1)}
                  <span className="text-base font-medium text-slate-400">
                    {" "}
                    {o.unit}
                  </span>
                </div>
                <div className="text-xs text-slate-500">recommended order</div>

                {/* stock vs need bar */}
                <div className="mt-3">
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: `${fillPct}%` }}
                    />
                  </div>
                  <div className="mt-1 flex justify-between text-xs text-slate-500">
                    <span>stock {n1(o.stock_on_hand)}</span>
                    <span>need {n1(o.forecast_need)}</span>
                  </div>
                </div>

                <div className="mt-3 flex gap-3 text-xs text-slate-500">
                  <span>shelf {o.shelf_life_days}d</span>
                  <span>lead {o.lead_time_days}d</span>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <p className="mt-4 text-xs text-slate-400">
        Approve-order integration with suppliers is not wired in this POC.
      </p>
    </div>
  );
}
