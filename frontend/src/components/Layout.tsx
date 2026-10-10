import { Link, NavLink, Outlet } from "react-router-dom";
import { useMe } from "../context";
import { ActivityIcon, CheckListIcon, HangerIcon, PlusIcon, SparklesIcon, StarIcon } from "./Icons";
import { Notice } from "./ui";

const TABS = [
  { to: "/", label: "Wardrobe", icon: HangerIcon, end: true },
  { to: "/add", label: "Add", icon: PlusIcon },
  { to: "/review", label: "Review", icon: CheckListIcon },
  { to: "/plan", label: "Plan", icon: SparklesIcon },
  { to: "/pro", label: "Pro", icon: StarIcon },
];

export default function Layout() {
  const { me, error } = useMe();

  return (
    <div className="min-h-dvh bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/85 backdrop-blur">
        <div className="mx-auto flex max-w-md items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-indigo-600 text-white">
              <HangerIcon className="h-5 w-5" />
            </span>
            <span className="text-lg font-bold tracking-tight">
              Stripe<span className="text-indigo-600">Fit</span>
            </span>
          </Link>
          <div className="flex items-center gap-2">
            {me?.mock_ai && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800" title="AI responses are simulated">
                Mock AI
              </span>
            )}
            {me &&
              (me.premium ? (
                <Link to="/pro" className="rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 px-2.5 py-0.5 text-xs font-bold text-white">
                  ★ PRO
                </Link>
              ) : (
                <Link to="/pro" className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                  Free · {me.confirmed_item_count}/{me.item_limit}
                </Link>
              ))}
            <Link to="/ai-log" className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600" title="AI call log">
              <ActivityIcon className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-md px-4 pb-28 pt-4">
        {error && (
          <div className="mb-4">
            <Notice tone="error">
              <strong>Can't reach the StripeFit server.</strong> Start the backend (port 8000), then refresh.
            </Notice>
          </div>
        )}
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
        <div className="mx-auto grid max-w-md grid-cols-5">
          {TABS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `relative flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium ${isActive ? "text-indigo-600" : "text-slate-500"}`
              }
            >
              <Icon className="h-6 w-6" />
              {label}
              {label === "Review" && !!me?.pending_count && (
                <span className="absolute right-[22%] top-1.5 min-w-[18px] rounded-full bg-rose-500 px-1 text-center text-[10px] font-bold leading-[18px] text-white">
                  {me.pending_count}
                </span>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
