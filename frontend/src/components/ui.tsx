import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Status } from "../api/types";
import { STATUS_LABELS, STATUS_STYLES, colourCss } from "../lib/format";
import { LockIcon } from "./Icons";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300",
  secondary: "bg-white text-slate-800 ring-1 ring-slate-300 hover:bg-slate-50 disabled:text-slate-400",
  ghost: "text-slate-600 hover:bg-slate-100 disabled:text-slate-300",
  danger: "bg-white text-rose-600 ring-1 ring-rose-200 hover:bg-rose-50 disabled:text-rose-300",
};

export function Button({
  variant = "primary",
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}

export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-label="Loading">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-slate-200/80 ${className}`} />;
}

export function Chip({
  active = false,
  children,
  onClick,
  className = "",
}: {
  active?: boolean;
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium ring-1 transition ${
        active ? "bg-indigo-600 text-white ring-indigo-600" : "bg-white text-slate-700 ring-slate-200 hover:ring-slate-300"
      } ${className}`}
    >
      {children}
    </button>
  );
}

export function StatusChip({ status }: { status: Status }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

export function ColourDots({ colours, size = "h-3.5 w-3.5" }: { colours: string[]; size?: string }) {
  return (
    <span className="inline-flex items-center gap-1" title={colours.join(", ")}>
      {colours.map((c) => {
        const css = colourCss(c);
        return css ? (
          <span key={c} className={`${size} rounded-full ring-1 ring-black/10`} style={{ backgroundColor: css }} />
        ) : (
          <span key={c} className={`${size} rounded-full border border-dashed border-slate-400`} />
        );
      })}
    </span>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
      <div className="mb-2 text-4xl">👕</div>
      <h3 className="font-semibold text-slate-800">{title}</h3>
      {body && <p className="mt-1 max-w-xs text-sm text-slate-500">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "error" | "success"; children: ReactNode }) {
  const tones = {
    info: "bg-sky-50 text-sky-800 ring-sky-200",
    warn: "bg-amber-50 text-amber-900 ring-amber-200",
    error: "bg-rose-50 text-rose-800 ring-rose-200",
    success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  };
  return <div className={`rounded-xl px-3 py-2.5 text-sm ring-1 ${tones[tone]}`}>{children}</div>;
}

export function UpgradeBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 p-4 text-white shadow-sm">
      <LockIcon className="h-6 w-6 shrink-0" />
      <div className="flex-1 text-sm">
        <p className="font-semibold">{message}</p>
        <p className="text-indigo-100">StripeFit Pro is a one-off €2.99. No subscription.</p>
      </div>
      <Link to="/pro" className="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-indigo-700">
        Get Pro
      </Link>
    </div>
  );
}

/** Picker for 1-5 scales (formality, warmth). `highlight` marks a field the user must fill in. */
export function ScalePicker({
  value,
  onChange,
  labels,
  highlight = false,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  labels: string[];
  highlight?: boolean;
}) {
  return (
    <div className={`rounded-xl ${highlight ? "ring-2 ring-amber-300 ring-offset-2" : ""}`}>
      <div className="grid grid-cols-5 gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            title={labels[n]}
            onClick={() => onChange(value === n ? null : n)}
            className={`rounded-lg py-1.5 text-sm font-semibold ring-1 ${
              value === n ? "bg-indigo-600 text-white ring-indigo-600" : "bg-white text-slate-600 ring-slate-200"
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      <p className="mt-1 text-xs text-slate-500">{value ? labels[value] : "Not set"}</p>
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
        {hint}
      </span>
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-xl border-0 bg-white px-3 py-2 text-sm text-slate-900 ring-1 ring-slate-300 focus:ring-2 focus:ring-indigo-500 focus:outline-none";

export function Sheet({ open, onClose, children, title }: { open: boolean; onClose: () => void; children: ReactNode; title: string }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} />
      <div className="relative max-h-[92vh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-slate-50 p-5 pb-8 shadow-xl sm:rounded-3xl">
        {children}
      </div>
    </div>
  );
}
