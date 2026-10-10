import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
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

  const tones: Record<Tone, string> = {
    success: "bg-emerald-600",
    error: "bg-rose-600",
    info: "bg-slate-800",
  };

  return (
    <ToastContext.Provider value={{ notify, showError }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-3 z-50 flex flex-col items-center gap-2 px-4">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto w-full max-w-md rounded-xl px-4 py-3 text-sm text-white shadow-lg ${tones[t.tone]}`}
          >
            <p className="font-semibold">{t.message}</p>
            {t.nextStep && <p className="mt-0.5 text-white/85">{t.nextStep}</p>}
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

  return <MeContext.Provider value={{ me, error, refresh }}>{children}</MeContext.Provider>;
}

export function useMe(): MeApi {
  const ctx = useContext(MeContext);
  if (!ctx) throw new Error("useMe outside MeProvider");
  return ctx;
}
