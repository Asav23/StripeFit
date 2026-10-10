import { Link } from "react-router-dom";
import type { IngestSummary } from "../api/types";

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
  return (
    <div className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <p className="font-semibold text-slate-800">{summary.summary}</p>
      <ul className="divide-y divide-slate-100 text-sm">
        {summary.files.map((f, i) => (
          <li key={`${f.filename}-${i}`} className="flex items-start justify-between gap-2 py-2">
            <div className="min-w-0">
              <p className="truncate font-medium text-slate-700">{f.retailer ? `${f.retailer} · ${f.filename}` : f.filename}</p>
              {f.notes.length > 0 && <p className="text-xs text-slate-500">{[...new Set(f.notes)].join(", ")}</p>}
            </div>
            <div className="shrink-0 text-right">
              {f.email_type && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                  {TYPE_LABELS[f.email_type] ?? f.email_type}
                </span>
              )}
              <p className="mt-0.5 text-xs text-slate-500">
                {f.items_created > 0 && <span className="font-semibold text-emerald-700">+{f.items_created} new </span>}
                {f.items_updated > 0 && <span>{f.items_updated} updated</span>}
                {f.items_created === 0 && f.items_updated === 0 && (f.email_type || f.notes.length ? "no changes" : "")}
              </p>
            </div>
          </li>
        ))}
      </ul>
      {summary.items_created > 0 && (
        <Link to="/review" className="block rounded-xl bg-indigo-600 py-2.5 text-center text-sm font-semibold text-white">
          Review {summary.items_created} new item{summary.items_created > 1 ? "s" : ""} →
        </Link>
      )}
    </div>
  );
}
