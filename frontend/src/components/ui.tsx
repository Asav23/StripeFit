import { AlertTriangle, CheckCircle2, Info, Lock, X, XCircle, type LucideIcon } from "lucide-react";
import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import type { Status } from "../api/types";
import { STATUS_LABELS, colourCss } from "../lib/format";

// ---------------------------------------------------------------- buttons

type Variant = "primary" | "secondary" | "ghost" | "danger" | "accent";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-ink text-paper hover:bg-ink-2 active:bg-black disabled:bg-line-strong disabled:text-card",
  accent: "bg-accent text-white hover:brightness-110 active:brightness-95 disabled:opacity-50",
  secondary:
    "bg-card text-ink border border-line-strong hover:border-ink active:bg-sunk disabled:text-muted disabled:border-line",
  ghost: "text-ink-2 hover:bg-sunk hover:text-ink active:bg-line disabled:text-muted",
  danger: "bg-card text-danger border border-line-strong hover:border-danger hover:bg-danger-soft disabled:opacity-50",
};
const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-5 text-[15px] gap-2",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean }) {
  return (
    <button
      className={`inline-flex select-none items-center justify-center rounded-md font-medium transition-[background,border,color,filter] duration-150 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}

export function IconButton({
  icon: Icon,
  label,
  className = "",
  spinning = false,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { icon: LucideIcon; label: string; spinning?: boolean }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={`inline-grid h-9 w-9 shrink-0 place-items-center rounded-md text-ink-2 transition hover:bg-sunk hover:text-ink disabled:opacity-40 ${className}`}
      {...rest}
    >
      <Icon className={`h-[18px] w-[18px] ${spinning ? "animate-spin" : ""}`} strokeWidth={1.75} />
    </button>
  );
}

export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" role="status" aria-label="Loading">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="2.5" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-sunk ${className}`} />;
}

// ---------------------------------------------------------------- page structure

export function PageHeader({
  kicker,
  title,
  description,
  actions,
}: {
  kicker?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex items-end justify-between gap-4 md:mb-8">
      <div className="min-w-0">
        {kicker && <p className="kicker mb-2">{kicker}</p>}
        <h1 className="display text-[40px] md:text-[52px]">{title}</h1>
        {description && <p className="mt-2 max-w-prose text-[15px] text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between border-b border-line pb-2">
      <h2 className="kicker text-ink-2">{children}</h2>
      {action}
    </div>
  );
}

/** Underlined tab row; used for filters and the Add page tabs. */
export function Tabs<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode; count?: number }[];
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="no-scrollbar -mx-4 flex gap-5 overflow-x-auto border-b border-line px-4 md:mx-0 md:px-0">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={`relative shrink-0 pb-2.5 pt-1 text-sm transition ${
              active ? "font-medium text-ink" : "text-muted hover:text-ink-2"
            }`}
          >
            {o.label}
            {o.count !== undefined && <span className="ml-1.5 font-mono text-[11px] text-muted">{o.count}</span>}
            <span className={`absolute inset-x-0 -bottom-px h-[2px] rounded-full transition ${active ? "bg-ink" : "bg-transparent"}`} />
          </button>
        );
      })}
    </div>
  );
}

/** Pill toggles for choices inside forms. */
export function Choice({
  active,
  onClick,
  children,
  className = "",
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`h-8 rounded-md border px-3 text-[13px] transition ${
        active ? "border-ink bg-ink text-paper" : "border-line-strong bg-card text-ink-2 hover:border-ink hover:text-ink"
      } ${className}`}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------- item bits

const STATUS_DOT: Record<Status, string> = {
  available: "bg-ok",
  worn: "bg-warn",
  in_wash: "bg-info",
  unavailable: "bg-muted",
  on_the_way: "bg-accent",
  returned: "bg-danger",
};

export function StatusLabel({ status, className = "" }: { status: Status; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs text-ink-2 ${className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[status]}`} />
      {STATUS_LABELS[status]}
    </span>
  );
}

export function ColourDots({ colours, size = "h-3 w-3" }: { colours: string[]; size?: string }) {
  return (
    <span className="inline-flex items-center -space-x-0.5" title={colours.join(", ")} aria-label={`Colours: ${colours.join(", ")}`}>
      {colours.map((c) => {
        const css = colourCss(c);
        return css ? (
          <span key={c} className={`${size} rounded-full border border-black/15`} style={{ backgroundColor: css }} />
        ) : (
          <span key={c} className={`${size} rounded-full border border-dashed border-muted bg-card`} />
        );
      })}
    </span>
  );
}

// ---------------------------------------------------------------- feedback

type Tone = "info" | "warn" | "error" | "success";
const TONES: Record<Tone, { box: string; icon: LucideIcon; iconClass: string }> = {
  info: { box: "bg-info-soft text-ink border-info/20", icon: Info, iconClass: "text-info" },
  warn: { box: "bg-warn-soft text-ink border-warn/25", icon: AlertTriangle, iconClass: "text-warn" },
  error: { box: "bg-danger-soft text-ink border-danger/25", icon: XCircle, iconClass: "text-danger" },
  success: { box: "bg-ok-soft text-ink border-ok/25", icon: CheckCircle2, iconClass: "text-ok" },
};

export function Notice({ tone = "info", children, className = "" }: { tone?: Tone; children: ReactNode; className?: string }) {
  const { box, icon: Icon, iconClass } = TONES[tone];
  return (
    <div className={`flex gap-2.5 rounded-md border px-3 py-2.5 text-sm leading-snug ${box} ${className}`} role={tone === "error" ? "alert" : undefined}>
      <Icon className={`mt-px h-4 w-4 shrink-0 ${iconClass}`} strokeWidth={2} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: LucideIcon;
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-dashed border-line-strong px-6 py-14 text-center">
      <span className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-sunk text-ink-2">
        <Icon className="h-5 w-5" strokeWidth={1.75} />
      </span>
      <h3 className="display text-[26px]">{title}</h3>
      {body && <p className="mt-1.5 max-w-xs text-sm text-ink-2">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function UpgradeBanner({ message }: { message: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-lg bg-ink px-4 py-3.5 text-paper">
      <Lock className="h-4 w-4 shrink-0 opacity-70" strokeWidth={2} />
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-medium">{message}</p>
        <p className="text-paper/60">StripeFit Pro is €2.99, once. No subscription.</p>
      </div>
      <Link to="/pro" className="inline-flex h-8 items-center rounded-md bg-paper px-3 text-[13px] font-medium text-ink hover:bg-white">
        See Pro
      </Link>
    </div>
  );
}

export function LinkButton({ to, children, variant = "primary" }: { to: string; children: ReactNode; variant?: "primary" | "secondary" }) {
  return (
    <Link
      to={to}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition ${VARIANTS[variant]}`}
    >
      {children}
    </Link>
  );
}

// ---------------------------------------------------------------- forms

/** 1-5 scale. `highlight` marks a field the user still has to fill in. */
export function ScalePicker({
  value,
  onChange,
  labels,
  highlight = false,
  name,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  labels: string[];
  highlight?: boolean;
  name: string;
}) {
  return (
    <div>
      <div
        role="radiogroup"
        aria-label={name}
        className={`grid grid-cols-5 overflow-hidden rounded-md border ${highlight ? "border-warn ring-2 ring-warn/20" : "border-line-strong"}`}
      >
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            title={labels[n]}
            onClick={() => onChange(value === n ? null : n)}
            className={`h-9 border-l border-line font-mono text-[13px] transition first:border-l-0 ${
              value === n ? "bg-ink text-paper" : value !== null && n < value ? "bg-sunk text-ink-2" : "bg-card text-ink-2 hover:bg-sunk"
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      <p className={`mt-1 text-xs ${value ? "text-ink-2" : highlight ? "text-warn" : "text-muted"}`}>{value ? labels[value] : "Not set"}</p>
    </div>
  );
}

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <label htmlFor={htmlFor} className="kicker text-ink-2">
          {label}
        </label>
        {hint}
      </div>
      {children}
    </div>
  );
}

export const inputClass = "field";

export function NeedsInput() {
  return <span className="font-mono text-[10.5px] uppercase tracking-wide text-warn">Please fill in</span>;
}

// ---------------------------------------------------------------- dialog

/** Bottom sheet on mobile, centred dialog on desktop. Esc and backdrop close it; focus returns afterwards. */
export function Sheet({ open, onClose, children, title }: { open: boolean; onClose: () => void; children: ReactNode; title: string }) {
  const panel = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose; // callers pass inline functions; don't re-run the effect for them

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center md:items-center md:p-6" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 animate-fade bg-ink/40" onClick={onClose} />
      <div
        ref={panel}
        tabIndex={-1}
        className="relative max-h-[92dvh] w-full max-w-lg animate-sheet overflow-y-auto rounded-t-xl bg-paper shadow-[0_-8px_40px_rgb(0_0_0/0.18)] outline-none md:rounded-xl"
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-paper/95 px-5 py-3 backdrop-blur">
          <span className="kicker truncate">{title}</span>
          <IconButton icon={X} label="Close" onClick={onClose} className="-mr-2" />
        </div>
        <div className="px-5 pb-8 pt-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

/** Render fixed-position UI at the document root, outside any animated/transformed parent. */
export function Portal({ children }: { children: ReactNode }) {
  return createPortal(children, document.body);
}
