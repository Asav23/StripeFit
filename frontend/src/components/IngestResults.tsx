import { ArrowRight } from "lucide-react";
import type { IngestSummary } from "../api/types";
import { LinkButton } from "./ui";

const TYPE_LABELS: Record<string, string> = {
  order_confirmation: "Order",
  dispatch: "Dispatched",
  delivery: "Delivered",
  refund: "Refund",
  return: "Return",
  cancellation: "Cancelled",
  exchange: "Exchange",
  marketing: "Marketing",
  other: "Not an order",
};

export default function IngestResults({ summary }: { summary: IngestSummary }) {
  const skipped = Object.values(summary.skipped).reduce((a, b) => a + b, 0);
  return (
    <section className="animate-rise overflow-hidden rounded-xl border border-line bg-card shadow-[var(--shadow-card)]">
      <div className="grid grid-cols-3 divide-x divide-line border-b border-line">
        {[
          ["New", summary.items_created],
          ["Updated", summary.items_updated],
          ["Skipped", skipped],
        ].map(([label, n]) => (
          <div key={label} className="px-4 py-3">
            <p className="display font-mono text-[26px] leading-none">{n}</p>
            <p className="kicker mt-1">{label}</p>
          </div>
        ))}
      </div>
      <ul className="divide-y divide-line text-sm">
        {summary.files.map((f, i) => (
          <li key={`${f.filename}-${i}`} className="flex items-start gap-3 px-4 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{f.retailer ?? f.filename}</p>
              <p className="truncate text-xs text-muted">
                {f.retailer ? f.filename : ""}
                {f.notes.length > 0 && <span className="text-warn">{f.retailer ? " · " : ""}{[...new Set(f.notes)].join(", ")}</span>}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {f.items_created > 0 && <span className="font-mono text-xs text-ok">+{f.items_created}</span>}
              {f.items_updated > 0 && <span className="font-mono text-xs text-ink-2">~{f.items_updated}</span>}
              {f.email_type && <span className="tag">{TYPE_LABELS[f.email_type] ?? f.email_type}</span>}
            </div>
          </li>
        ))}
      </ul>
      {summary.items_created > 0 && (
        <div className="border-t border-line bg-[#fafbfd] px-4 py-3">
          <LinkButton to="/review">
            Review {summary.items_created} new item{summary.items_created > 1 ? "s" : ""} <ArrowRight className="h-4 w-4" />
          </LinkButton>
        </div>
      )}
    </section>
  );
}
