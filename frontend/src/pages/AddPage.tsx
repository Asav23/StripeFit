import { Lock } from "lucide-react";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import GmailImporter from "../components/GmailImporter";
import OrderImporter from "../components/OrderImporter";
import PhotoUploader from "../components/PhotoUploader";
import { PageHeader, Skeleton, Tabs, UpgradeBanner } from "../components/ui";
import { useMe, useToast } from "../context";

type TabId = "photos" | "order" | "gmail";

const GMAIL_MESSAGES: Record<string, [string, "success" | "error" | "info"]> = {
  connected: ["Gmail connected. You can import your orders now.", "success"],
  cancelled: ["Gmail connection cancelled.", "info"],
  error: ["Couldn't connect Gmail. Please try again.", "error"],
};

const PRO_PITCH: Record<Exclude<TabId, "photos">, { title: string; body: string }> = {
  order: {
    title: "Order-email import is part of Pro.",
    body: "Drop in confirmation, dispatch and refund emails and StripeFit adds what you bought, removes refunds, and flags child sizes and gifts.",
  },
  gmail: {
    title: "Gmail import is part of Pro.",
    body: "A read-only scan of order emails from clothing shops, so your wardrobe fills itself.",
  },
};

export default function AddPage() {
  const { me } = useMe();
  const { notify } = useToast();
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: TabId = raw === "order" || raw === "gmail" ? raw : "photos";

  // Back from Google's consent screen: /add?tab=gmail&gmail=connected
  useEffect(() => {
    const result = params.get("gmail");
    if (result && GMAIL_MESSAGES[result]) {
      notify(...GMAIL_MESSAGES[result]);
      setParams({ tab: "gmail" }, { replace: true });
    }
  }, [params, setParams, notify]);

  const pro = (label: string) =>
    me?.premium ? (
      label
    ) : (
      <span className="inline-flex items-center gap-1.5">
        {label}
        <Lock className="h-3 w-3 text-muted" />
      </span>
    );

  return (
    <div>
      <PageHeader kicker="Add clothes" title="Add to your wardrobe" description="Snap what you own, or let your order emails do the work." />
      <div className="mb-6">
        <Tabs<TabId>
          label="How to add"
          value={tab}
          onChange={(t) => setParams({ tab: t })}
          options={[
            { value: "photos", label: "Photos" },
            { value: "order", label: pro("Order emails") },
            { value: "gmail", label: pro("Gmail") },
          ]}
        />
      </div>

      <div key={tab} className="animate-rise">
        {tab === "photos" && <PhotoUploader />}
        {tab !== "photos" &&
          (!me ? (
            <Skeleton className="h-40" />
          ) : !me.premium ? (
            <div className="max-w-xl space-y-4">
              <UpgradeBanner message={PRO_PITCH[tab].title} />
              <p className="text-sm text-ink-2">{PRO_PITCH[tab].body}</p>
            </div>
          ) : tab === "order" ? (
            <OrderImporter />
          ) : (
            <GmailImporter />
          ))}
      </div>
    </div>
  );
}
