import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AICallLog } from "../api/types";
import { RefreshIcon } from "../components/Icons";
import { EmptyState, Notice, Skeleton } from "../components/ui";
import { formatDateTime } from "../lib/format";

export default function AiLogPage() {
  const [log, setLog] = useState<AICallLog | null>(null);
  const [failed, setFailed] = useState(false);

  const load = () =>
    api
      .aiCalls()
      .then((l) => {
        setLog(l);
        setFailed(false);
      })
      .catch(() => setFailed(true));

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI log</h1>
          <p className="text-sm text-slate-500">Every model call: which model, how long, tokens and cost.</p>
        </div>
        <button onClick={load} className="rounded-lg p-2 text-slate-500 hover:bg-slate-200" aria-label="Refresh">
          <RefreshIcon className="h-5 w-5" />
        </button>
      </div>

      {failed && <Notice tone="error">Couldn't load the AI log.</Notice>}
      {!log && !failed && <Skeleton className="h-64" />}

      {log && (
        <>
          {log.mock_ai && <Notice tone="warn">Mock AI is on: calls are simulated and cost nothing.</Notice>}
          <div className="grid grid-cols-4 gap-2 text-center">
            {[
              ["Calls", log.totals.count],
              ["Failed", log.totals.failures],
              ["Avg ms", log.totals.avg_latency_ms],
              ["Cost $", log.totals.cost.toFixed(4)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl bg-white p-2 ring-1 ring-slate-200">
                <p className="text-lg font-bold">{value}</p>
                <p className="text-[11px] text-slate-500">{label}</p>
              </div>
            ))}
          </div>

          <div className="rounded-2xl bg-white p-3 text-xs ring-1 ring-slate-200">
            <p className="mb-1 font-semibold text-slate-700">Configured models (primary → fallbacks)</p>
            {Object.entries(log.models).map(([kind, [primary, fallbacks]]) => (
              <p key={kind} className="truncate text-slate-600">
                <span className="font-semibold capitalize">{kind}:</span> {primary || "not set"}
                {fallbacks.length > 0 && <span className="text-slate-400"> → {fallbacks.join(", ")}</span>}
              </p>
            ))}
          </div>

          {log.calls.length === 0 ? (
            <EmptyState title="No AI calls yet" body="Upload a photo or plan an outfit and calls will show up here." />
          ) : (
            <ul className="space-y-2">
              {log.calls.map((c) => (
                <li key={c.id} className="rounded-2xl bg-white p-3 text-xs ring-1 ring-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">{c.task}</span>
                    <span className={c.success ? "font-semibold text-emerald-600" : "font-semibold text-rose-600"}>
                      {c.success ? "ok" : "failed"}
                    </span>
                  </div>
                  <p className="truncate text-slate-500">{c.model}</p>
                  <p className="text-slate-500">
                    {formatDateTime(c.created_at)} · {c.latency_ms} ms
                    {c.prompt_tokens != null && ` · ${c.prompt_tokens}+${c.completion_tokens ?? 0} tokens`}
                    {c.cost != null && ` · $${c.cost.toFixed(5)}`}
                  </p>
                  {c.error && <p className="mt-1 break-words text-rose-600">{c.error}</p>}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
