import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import GmailImporter from "../components/GmailImporter";
import OrderImporter from "../components/OrderImporter";
import PhotoUploader from "../components/PhotoUploader";
import { Skeleton, UpgradeBanner } from "../components/ui";
import { useMe, useToast } from "../context";

const TABS = [
  { id: "photos", label: "Photos", pro: false },
  { id: "order", label: "From an order", pro: true },
  { id: "gmail", label: "Gmail", pro: true },
] as const;

const GMAIL_MESSAGES: Record<string, [string, "success" | "error" | "info"]> = {
  connected: ["Gmail connected. You can import your orders now.", "success"],
  cancelled: ["Gmail connection cancelled.", "info"],
  error: ["Couldn't connect Gmail. Please try again.", "error"],
};

export default function AddPage() {
  const { me } = useMe();
  const { notify } = useToast();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "photos";

  // Back from Google's consent screen: /add?tab=gmail&gmail=connected
  useEffect(() => {
    const result = params.get("gmail");
    if (result && GMAIL_MESSAGES[result]) {
      notify(...GMAIL_MESSAGES[result]);
      setParams({ tab: "gmail" }, { replace: true });
    }
  }, [params, setParams, notify]);

  const current = TABS.find((t) => t.id === tab) ?? TABS[0];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">Add clothes</h1>
      <div className="grid grid-cols-3 gap-1 rounded-2xl bg-slate-200/70 p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setParams({ tab: t.id })}
            className={`rounded-xl py-2 text-sm font-semibold transition ${
              current.id === t.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
            }`}
          >
            {t.label}
            {t.pro && !me?.premium && <span className="ml-1 text-[10px] text-indigo-600">PRO</span>}
          </button>
        ))}
      </div>

      {current.id === "photos" && <PhotoUploader />}
      {current.id !== "photos" &&
        (!me ? (
          <Skeleton className="h-40" />
        ) : !me.premium ? (
          <div className="space-y-3">
            <UpgradeBanner
              message={current.id === "gmail" ? "Gmail import is part of StripeFit Pro." : "Order-email import is part of StripeFit Pro."}
            />
            <p className="text-sm text-slate-600">
              Pro reads your order confirmations, dispatch and refund emails and adds what you bought, so your wardrobe
              fills itself. Refunded items are removed, and child sizes and gifts are flagged.
            </p>
          </div>
        ) : current.id === "order" ? (
          <OrderImporter />
        ) : (
          <GmailImporter />
        ))}
    </div>
  );
}
