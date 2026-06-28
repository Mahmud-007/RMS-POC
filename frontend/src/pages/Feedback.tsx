import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { todayISO, n1 } from "../lib/format";
import { Card, ErrorBox, SectionTitle } from "../components/ui";
import {
  CHANNELS,
  CHANNEL_LABELS,
  REASON_LABELS,
  REASON_TAGS,
} from "../lib/types";
import type { Channel, CorrectionResult, ReasonTag } from "../lib/types";

const HOURS = Array.from({ length: 12 }, (_, i) => i + 11); // 11..22

export default function Feedback() {
  const qc = useQueryClient();
  const [date, setDate] = useState(todayISO());
  const [hour, setHour] = useState(19);
  const [channel, setChannel] = useState<Channel>("dine_in");
  const [actual, setActual] = useState<number>(10);
  const [reason, setReason] = useState<ReasonTag>("normal");
  const [result, setResult] = useState<CorrectionResult | null>(null);

  // Pull that day's forecast so the manager can see what we predicted while
  // they enter what actually happened.
  const day = useQuery({
    queryKey: ["day", date],
    queryFn: () => api.dayForecast(date),
  });

  const predicted = (() => {
    const rows = day.data?.covers?.[channel];
    if (!rows) return null;
    const match = rows.find((r) => r.hour === hour);
    return match ? match.final_pred : null;
  })();

  const mutation = useMutation({
    mutationFn: () =>
      api.submitCorrection({
        ts: `${date}T${String(hour).padStart(2, "0")}:00:00`,
        channel,
        actual,
        reason_tag: reason,
      }),
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["metrics"] });
      qc.invalidateQueries({ queryKey: ["day"] });
    },
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Report Results</h1>
        <p className="text-slate-500 text-sm mt-1">
          Enter how many customers actually came, so the system compares it to the
          forecast and gets more accurate over time.
        </p>
      </div>

      <Card className="p-5 max-w-2xl">
        <SectionTitle>Record actual customers</SectionTitle>
        <div className="grid sm:grid-cols-2 gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-500">Date</span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-500">Hour</span>
            <select
              value={hour}
              onChange={(e) => setHour(Number(e.target.value))}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
            >
              {HOURS.map((h) => (
                <option key={h} value={h}>
                  {h}:00
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-500">Channel</span>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value as Channel)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
            >
              {CHANNELS.map((c) => (
                <option key={c} value={c}>
                  {CHANNEL_LABELS[c]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-500">
              Actual customers
            </span>
            <input
              type="number"
              min={0}
              value={actual}
              onChange={(e) => setActual(Number(e.target.value))}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 sm:col-span-2">
            <span className="text-xs font-medium text-slate-500">Reason</span>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value as ReasonTag)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
            >
              {REASON_TAGS.map((t) => (
                <option key={t} value={t}>
                  {REASON_LABELS[t]}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* What the model predicted for this slot */}
        <div className="mt-4 flex items-center gap-3 rounded-lg bg-slate-50 border border-slate-200 px-4 py-3">
          <span className="text-sm text-slate-500">We predicted</span>
          <span className="text-xl font-bold text-slate-900">
            {day.isLoading
              ? "…"
              : predicted != null
                ? `${n1(predicted)} customers`
                : "—"}
          </span>
          <span className="text-xs text-slate-400">
            {CHANNEL_LABELS[channel]} · {hour}:00 · {date}
          </span>
          {predicted != null && actual > 0 && (
            <span
              className={`ml-auto text-sm font-medium ${
                actual - predicted >= 0 ? "text-green-600" : "text-red-600"
              }`}
            >
              {actual - predicted >= 0 ? "+" : ""}
              {n1(actual - predicted)} vs actual
            </span>
          )}
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="mt-5 bg-slate-900 text-white text-sm font-medium px-5 py-2.5 rounded-lg hover:bg-slate-800 disabled:opacity-50"
        >
          {mutation.isPending ? "Submitting…" : "Submit correction"}
        </button>

        {mutation.error && (
          <div className="mt-4">
            <ErrorBox message={(mutation.error as Error).message} />
          </div>
        )}

        {result && (
          <div className="mt-5 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="text-sm font-medium text-green-800 mb-2">
              ✓ Correction recorded — the model updated immediately.
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <Stat label="We predicted" value={result.base_pred.toFixed(1)} />
              <Stat label="You reported" value={result.actual.toFixed(1)} />
              <Stat
                label="Adjustment learned"
                value={result.target_residual_clipped.toFixed(1)}
              />
              <Stat label="Total corrections" value={String(result.n_updates)} />
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-bold text-slate-900">{value}</div>
    </div>
  );
}
