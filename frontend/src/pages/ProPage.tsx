import { Check, CreditCard } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import type { Purchase } from "../api/types";
import { Button, Notice, PageHeader, SectionTitle, Skeleton } from "../components/ui";
import { useMe, useToast } from "../context";
import { formatDateTime, formatMoney } from "../lib/format";

const FEATURES: [string, string][] = [
  ["Unlimited wardrobe", "The free plan holds 20 items. Pro has no limit."],
  ["Order-email import", "Drop in confirmations, dispatch and refund emails or screenshots. We add what you bought and remove refunds."],
  ["Gmail import", "A read-only scan of order emails from clothing shops, so your wardrobe fills itself."],
];

export function PurchaseRecord({ purchase }: { purchase: Purchase }) {
  const rows: [string, string][] = [
    ["Amount", formatMoney(purchase.amount_total, purchase.currency, true)],
    ["Currency", (purchase.currency ?? "").toUpperCase()],
    ["Date", formatDateTime(purchase.created_at)],
    ["Status", purchase.status],
    ["Session", purchase.stripe_session_id],
  ];
  return (
    <dl className="divide-y divide-dashed divide-line-strong rounded-lg border border-line bg-card px-4 font-mono text-[12.5px]">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-baseline justify-between gap-6 py-2.5">
          <dt className="uppercase tracking-wide text-muted">{k}</dt>
          <dd className={`min-w-0 truncate text-right ${k === "Status" ? "uppercase text-ok" : "text-ink"}`} title={v}>
            {v}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** The price, drawn as a garment swing tag. */
function SwingTag({ premium }: { premium: boolean }) {
  return (
    <div className="relative mx-auto w-full max-w-[260px] rotate-[-2deg] rounded-md border border-line-strong bg-card px-6 pb-7 pt-10 text-center shadow-[0_18px_40px_-20px_rgb(0_0_0/0.35)] transition hover:rotate-0">
      <span className="absolute left-1/2 top-4 h-3 w-3 -translate-x-1/2 rounded-full border border-line-strong bg-paper" />
      <p className="kicker">StripeFit</p>
      <p className="display mt-1 text-[30px]">Pro</p>
      <div className="my-4 border-t border-dashed border-line-strong" />
      {premium ? (
        <p className="display text-[44px] leading-none text-ok">Yours</p>
      ) : (
        <p className="display text-[64px] leading-none">
          <span className="align-top text-[30px]">€</span>2.99
        </p>
      )}
      <p className="mt-2 font-mono text-[11px] uppercase tracking-wide text-muted">{premium ? "Active" : "One-time · no subscription"}</p>
    </div>
  );
}

export default function ProPage() {
  const { me, refresh } = useMe();
  const { notify, showError } = useToast();
  const [busy, setBusy] = useState(false);

  const buy = async () => {
    setBusy(true);
    try {
      const { url } = await api.checkout();
      window.location.href = url; // Stripe-hosted Checkout (test mode)
    } catch (e) {
      showError(e);
      setBusy(false);
    }
  };

  const reset = async () => {
    try {
      await api.resetPremium();
      await refresh();
      notify("Back on the free plan (demo reset).", "info");
    } catch (e) {
      showError(e);
    }
  };

  if (!me) return <Skeleton className="h-96" />;

  const cta = (
    <div className="space-y-3">
      <Button size="lg" onClick={buy} loading={busy} className="w-full md:w-auto">
        <CreditCard className="h-4 w-4" /> Buy StripeFit Pro · €2.99
      </Button>
      {!me.stripe_configured && <Notice tone="warn">Payments aren't set up on this server yet (no Stripe test key), so checkout won't open.</Notice>}
      <p className="text-[13px] text-muted">
        Test mode: no real money moves. Pay with <span className="font-mono text-ink-2">4242 4242 4242 4242</span>, any future expiry and any CVC.
      </p>
    </div>
  );

  return (
    <div>
      <PageHeader
        kicker="StripeFit Pro"
        title={me.premium ? "Pro is active" : "Pay once. Keep it."}
        description={
          me.premium
            ? `Since ${formatDateTime(me.premium_since)}. Thanks for supporting StripeFit.`
            : "Unlimited wardrobe and automatic order import for less than a coffee. Outfit planning stays free."
        }
      />

      <div className="grid items-start gap-10 md:grid-cols-[1fr_300px]">
        <div className="space-y-8">
          <ul className="divide-y divide-line border-y border-line">
            {FEATURES.map(([title, body]) => (
              <li key={title} className="flex gap-4 py-4">
                <Check className="mt-1 h-4 w-4 shrink-0 text-accent" strokeWidth={2.5} />
                <div>
                  <p className="font-medium">{title}</p>
                  <p className="mt-0.5 text-sm text-ink-2">{body}</p>
                </div>
              </li>
            ))}
          </ul>

          {!me.premium && <div className="hidden md:block">{cta}</div>}

          {me.premium && me.latest_purchase && (
            <section>
              <SectionTitle>Receipt</SectionTitle>
              <PurchaseRecord purchase={me.latest_purchase} />
            </section>
          )}

          <section className="max-w-prose">
            <SectionTitle>Why one-time, not a subscription?</SectionTitle>
            <p className="text-sm leading-relaxed text-ink-2">
              Students don't want another subscription quietly eating their budget. A single payment under the price of a coffee is easy to say
              yes to, and there's nothing to remember to cancel. Pro covers the AI cost of importing your orders.
            </p>
          </section>

          {me.premium && (
            <button onClick={reset} className="text-xs text-muted underline underline-offset-4 hover:text-ink">
              Demo: reset to the free plan
            </button>
          )}
        </div>

        <div className="order-first md:order-none md:pt-4">
          <SwingTag premium={me.premium} />
          {!me.premium && <div className="mt-8 md:hidden">{cta}</div>}
        </div>
      </div>
    </div>
  );
}
