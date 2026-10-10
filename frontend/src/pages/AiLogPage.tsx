import { Activity, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AICallLog } from "../api/types";
import DemoControls from "../components/DemoControls";
import { EmptyState, IconButton, Notice, PageHeader, SectionTitle, Skeleton } from "../components/ui";
import { TIMEZONE } from "../lib/format";

const time = (iso: string) =>
  new Intl.DateTimeFormat("en-IE", { timeZone: TIMEZONE, hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(iso));

export default function AiLogPage() {
  const [log, setLog] = useState<AICallLog | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    api
      .aiCalls()
      .then((l) => {
        setLog(l);
        setFailed(false);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div>
      <PageHeader
        kicker="Under the hood"
        title="AI log"
        description="Every model call, which model answered, how long it took, tokens and cost."
        actions={<IconButton icon={RefreshCw} label="Refresh" onClick={load} spinning={loading} />}
      />

      {failed && <Notice tone="error">Couldn't load the AI log.</Notice>}
      {!log && !failed && <Skeleton className="h-64" />}

      {log && (
        <div className="grid items-start gap-8 lg:grid-cols-[1fr_320px]">
          <div className="min-w-0 space-y-6">
            <dl className="grid grid-cols-2 divide-line border-y border-line sm:grid-cols-4 sm:divide-x">
              {[
                ["Calls", String(log.totals.count)],
                ["Failed", String(log.totals.failures)],
                ["Avg latency", `${log.totals.avg_latency_ms} ms`],
                ["Cost", `$${log.totals.cost.toFixed(4)}`],
              ].map(([label, value]) => (
                <div key={label} className="py-3 sm:px-4 sm:first:pl-0">
                  <dt className="kicker">{label}</dt>
                  <dd className="display mt-1 font-mono text-[24px] leading-none">{value}</dd>
                </div>
              ))}
            </dl>

            <section>
              <SectionTitle>Recent calls</SectionTitle>
              {log.calls.length === 0 ? (
                <EmptyState icon={Activity} title="No calls yet" body="Upload a photo or plan an outfit and calls will show up here." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-[13px]">
                    <thead>
                      <tr className="font-mono text-[10.5px] uppercase tracking-wide text-muted">
                        <th className="py-2 pr-3 font-normal">Time</th>
                        <th className="py-2 pr-3 font-normal">Task</th>
                        <th className="py-2 pr-3 font-normal">Model</th>
                        <th className="py-2 pr-3 text-right font-normal">ms</th>
                        <th className="py-2 pr-3 text-right font-normal">Tokens</th>
                        <th className="py-2 text-right font-normal">Result</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {log.calls.map((c) => (
                        <tr key={c.id} className="align-top">
                          <td className="py-2 pr-3 font-mono text-[12px] text-muted">{time(c.created_at)}</td>
                          <td className="py-2 pr-3 font-medium">{c.task}</td>
                          <td className="max-w-[220px] truncate py-2 pr-3 text-ink-2" title={c.model}>
                            {c.model}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono text-[12px]">{c.latency_ms}</td>
                          <td className="py-2 pr-3 text-right font-mono text-[12px] text-ink-2">
                            {c.prompt_tokens != null ? `${c.prompt_tokens}+${c.completion_tokens ?? 0}` : "–"}
                          </td>
                          <td className="py-2 text-right">
                            {c.success ? (
                              <span className="text-ok">ok</span>
                            ) : (
                              <span className="text-danger" title={c.error ?? ""}>
                                failed
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>

          <aside className="space-y-6">
            <section>
              <SectionTitle>Demo controls</SectionTitle>
              {log.mock_ai && <p className="mb-3 text-[13px] text-warn">Mock AI is on: calls are simulated and cost nothing.</p>}
              <DemoControls mockAi={log.mock_ai} />
            </section>
            <section>
              <SectionTitle>Models</SectionTitle>
              <dl className="space-y-3 text-[13px]">
                {Object.entries(log.models).map(([kind, [primary, fallbacks]]) => (
                  <div key={kind}>
                    <dt className="kicker">{kind}</dt>
                    <dd className="mt-0.5 break-all font-mono text-[12px]">{primary || "not set"}</dd>
                    {fallbacks.length > 0 && <dd className="break-all font-mono text-[11px] text-muted">then {fallbacks.join(", ")}</dd>}
                  </div>
                ))}
              </dl>
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}
