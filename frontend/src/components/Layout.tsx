import { Activity, CalendarCheck, ClipboardCheck, Plus, Shirt, Sparkles, Star, type LucideIcon } from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useMe } from "../context";
import { Notice } from "./ui";

const TABS: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: "/", label: "Wardrobe", icon: Shirt, end: true },
  { to: "/today", label: "Today", icon: CalendarCheck },
  { to: "/plan", label: "Plan", icon: Sparkles },
  { to: "/add", label: "Add", icon: Plus },
  { to: "/review", label: "Review", icon: ClipboardCheck },
  { to: "/pro", label: "Pro", icon: Star },
];

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-serif text-[27px] leading-none tracking-[-0.01em] text-ink ${className}`}>
      Stripe<em className="text-accent">fit</em>
    </span>
  );
}

function PlanBadge() {
  const { me } = useMe();
  if (!me) return null;
  if (me.premium) return <span className="tag surface-night px-2 font-semibold text-white">Pro</span>;
  const used = me.confirmed_item_count;
  const limit = me.item_limit ?? 0;
  return (
    <Link to="/pro" className="group flex items-center gap-2" title="Free plan item allowance">
      <span className="font-mono text-[11px] text-ink-2">
        {used}/{limit}
      </span>
      <span className="h-1.5 w-10 overflow-hidden rounded-full bg-line">
        <span className={`block h-full rounded-full ${used >= limit ? "bg-danger" : "bg-accent"}`} style={{ width: `${Math.min(100, (used / limit) * 100)}%` }} />
      </span>
    </Link>
  );
}

function ReviewCount({ className = "" }: { className?: string }) {
  const { me } = useMe();
  if (!me?.pending_count) return null;
  return (
    <span className={`min-w-[18px] rounded-full bg-accent px-1 text-center font-mono text-[10px] font-medium leading-[18px] text-white shadow-[var(--shadow-xs)] ${className}`}>
      {me.pending_count}
    </span>
  );
}

export default function Layout() {
  const { me, error } = useMe();
  const location = useLocation();

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[232px_1fr]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-line bg-card px-4 py-6 md:flex">
        <Link to="/" className="mb-10 px-2">
          <Wordmark />
        </Link>
        <nav className="flex flex-col gap-0.5" aria-label="Main">
          {TABS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex h-9 items-center gap-3 rounded-md px-2.5 text-[14px] transition-colors duration-150 ${
                  isActive ? "bg-accent-soft font-medium text-accent" : "text-ink-2 hover:bg-sunk hover:text-ink"
                }`
              }
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
              <span className="flex-1">{label}</span>
              {label === "Review" && <ReviewCount />}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-4 px-2">
          <div className="flex items-center justify-between">
            <span className="kicker">Your plan</span>
            <PlanBadge />
          </div>
          <NavLink
            to="/ai-log"
            className={({ isActive }) => `flex items-center gap-2 text-xs transition ${isActive ? "text-ink" : "text-muted hover:text-ink"}`}
          >
            <Activity className="h-3.5 w-3.5" />
            AI log & demo controls
            {me?.mock_ai && <span className="tag ml-auto px-1 py-0 text-[9.5px]">Mock</span>}
          </NavLink>
        </div>
      </aside>

      <div className="relative min-w-0">
        <div aria-hidden className="page-wash pointer-events-none absolute inset-x-0 top-0 h-80" />
        {/* Mobile header */}
        <header className="sticky top-0 z-30 border-b border-line bg-card/90 backdrop-blur md:hidden">
          <div className="flex h-14 items-center justify-between px-4">
            <Link to="/">
              <Wordmark className="text-[24px]" />
            </Link>
            <div className="flex items-center gap-3">
              <PlanBadge />
              <Link to="/ai-log" className="grid h-9 w-9 place-items-center rounded-md text-muted hover:bg-sunk hover:text-ink" aria-label="AI log">
                <Activity className="h-[18px] w-[18px]" strokeWidth={1.75} />
              </Link>
            </div>
          </div>
        </header>

        <main key={location.pathname} className="relative mx-auto w-full max-w-5xl animate-rise px-4 pb-32 pt-6 md:px-10 md:pb-16 md:pt-12">
          {error && (
            <Notice tone="error" className="mb-6">
              <strong className="font-medium">Can't reach the StripeFit server.</strong> Retrying automatically. Check the backend
              is running on port 8000.
            </Notice>
          )}
          <Outlet />
        </main>
      </div>

      {/* Mobile tab bar */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        <div className="grid grid-cols-6">
          {TABS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `relative flex flex-col items-center gap-1 pb-2 pt-2.5 text-[10px] font-medium ${isActive ? "text-accent" : "text-muted"}`
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`absolute inset-x-4 top-0 h-[2px] rounded-full ${isActive ? "bg-accent" : ""}`} />
                  <Icon className="h-[21px] w-[21px]" strokeWidth={isActive ? 2 : 1.6} />
                  {label}
                  {label === "Review" && <ReviewCount className="absolute right-[22%] top-1" />}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
