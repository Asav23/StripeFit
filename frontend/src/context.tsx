import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { ApiError, api } from "./api/client";
import type { Me } from "./api/types";

// ---------------------------------------------------------------- toasts

type Tone = "success" | "error" | "info";
interface Toast {
  id: number;
  tone: Tone;
  message: string;
  nextStep?: string;
}

interface ToastApi {
  notify: (message: string, tone?: Tone, nextStep?: string) => void;
  /** Show any thrown error as a friendly toast (never a raw exception). */
  showError: (error: unknown) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const notify = useCallback((message: string, tone: Tone = "info", nextStep?: string) => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, tone, message, nextStep }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "error" ? 7000 : 4000);
  }, []);

  const showError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError) notify(error.message, "error", error.nextStep);
      else notify("Something went wrong.", "error", "Please try again.");
    },
    [notify],
  );

  const dismiss = (id: number) => setToasts((t) => t.filter((x) => x.id !== id));
  const icons: Record<Tone, ReactNode> = {
    success: <CheckCircle2 className="h-4 w-4 text-[#9fd3b0]" />,
    error: <XCircle className="h-4 w-4 text-[#f0a49c]" />,
    info: <Info className="h-4 w-4 text-paper/70" />,
  };

  return (
    <ToastContext.Provider value={{ notify, showError }}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 md:bottom-6 md:left-auto md:right-6 md:items-end"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            className="pointer-events-auto flex w-full max-w-sm animate-rise items-start gap-3 rounded-lg bg-ink px-4 py-3 text-sm text-paper shadow-[0_10px_30px_rgb(0_0_0/0.22)]"
          >
            <span className="mt-0.5">{icons[t.tone]}</span>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{t.message}</p>
              {t.nextStep && <p className="mt-0.5 text-paper/65">{t.nextStep}</p>}
            </div>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="-mr-1 rounded p-0.5 text-paper/50 hover:text-paper">
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}

// ---------------------------------------------------------------- current user (plan, counts)

interface MeApi {
  me: Me | null;
  error: boolean;
  refresh: () => Promise<void>;
}

const MeContext = createContext<MeApi | null>(null);
const RETRY_MS = 4000;

export function MeProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setMe(await api.me());
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // If the API was unreachable (e.g. restarting), keep retrying quietly until it's back.
  useEffect(() => {
    if (!error) return;
    const timer = window.setInterval(() => void refresh(), RETRY_MS);
    return () => window.clearInterval(timer);
  }, [error, refresh]);

  return <MeContext.Provider value={{ me, error, refresh }}>{children}</MeContext.Provider>;
}

export function useMe(): MeApi {
  const ctx = useContext(MeContext);
  if (!ctx) throw new Error("useMe outside MeProvider");
  return ctx;
}
