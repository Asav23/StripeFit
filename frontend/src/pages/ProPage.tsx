import { useState } from "react";
import { api } from "../api/client";
import type { Purchase } from "../api/types";
import { StarIcon } from "../components/Icons";
import { Button, Notice, Skeleton } from "../components/ui";
import { useMe, useToast } from "../context";
import { formatDateTime, formatMoney } from "../lib/format";

const FEATURES = [
  ["Unlimited wardrobe", "The free plan holds 20 items. Pro has no limit."],
  ["Import from order emails", "Drop in confirmations, dispatch and refund emails or screenshots. We add what you bought and remove refunds."],
  ["Gmail import", "Read-only scan of order emails from clothing shops, so your wardrobe fills itself."],
];

export function PurchaseRecord({ purchase }: { purchase: Purchase }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 rounded-2xl bg-white p-4 text-sm ring-1 ring-slate-200">
      <dt className="text-slate-500">Amount</dt>
      <dd className="font-semibold">{formatMoney(purchase.amount_total, purchase.currency, true)}</dd>
      <dt className="text-slate-500">Currency</dt>
      <dd>{(purchase.currency ?? "").toUpperCase()}</dd>
      <dt className="text-slate-500">Date</dt>
      <dd>{formatDateTime(purchase.created_at)}</dd>
      <dt className="text-slate-500">Status</dt>
      <dd className="font-semibold capitalize text-emerald-700">{purchase.status}</dd>
      <dt className="text-slate-500">Session</dt>
      <dd className="truncate font-mono text-xs" title={purchase.stripe_session_id}>
        {purchase.stripe_session_id}
      </dd>
    </dl>
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

  return (
    <div className="space-y-5">
      <div className="overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-indigo-600 to-violet-600 p-6 text-white shadow-lg">
        <div className="mb-3 flex items-center gap-2">
          <StarIcon className="h-6 w-6" />
          <span className="text-sm font-bold uppercase tracking-widest text-indigo-100">StripeFit Pro</span>
        </div>
        {me.premium ? (
          <>
            <p className="text-3xl font-bold">Pro active ✓</p>
            <p className="mt-1 text-indigo-100">Since {formatDateTime(me.premium_since)}. Thanks for supporting StripeFit!</p>
          </>
        ) : (
          <>
            <p className="text-4xl font-bold">
              €2.99 <span className="text-lg font-medium text-indigo-100">one-time</span>
            </p>
            <p className="mt-1 text-indigo-100">Pay once, keep it forever. No subscription.</p>
          </>
        )}
      </div>

      <ul className="space-y-3">
        {FEATURES.map(([title, body]) => (
          <li key={title} className="flex gap-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200">
            <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-700">✓</span>
            <div>
              <p className="font-semibold text-slate-800">{title}</p>
              <p className="text-sm text-slate-500">{body}</p>
            </div>
          </li>
        ))}
      </ul>

      {me.premium ? (
        <>
          {me.latest_purchase && (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Your purchase</h2>
              <PurchaseRecord purchase={me.latest_purchase} />
            </div>
          )}
          <button onClick={reset} className="w-full text-center text-xs text-slate-400 underline">
            Demo: reset to the free plan
          </button>
        </>
      ) : (
        <>
          <Button className="w-full py-3.5 text-base" onClick={buy} loading={busy}>
            Buy StripeFit Pro · €2.99
          </Button>
          {!me.stripe_configured && (
            <Notice tone="warn">Payments aren't set up on this server yet (no Stripe test key), so checkout won't open.</Notice>
          )}
          <Notice tone="info">
            <strong>Test mode.</strong> No real money moves. Pay with card <span className="font-mono">4242 4242 4242 4242</span>, any
            future expiry date and any CVC.
          </Notice>
        </>
      )}

      <section className="rounded-2xl bg-slate-100 p-4 text-sm text-slate-600">
        <h2 className="mb-1 font-semibold text-slate-800">Why one-time, not a subscription?</h2>
        <p>
          Students don't want another subscription quietly eating their budget. A single payment under the price of a
          coffee is easy to say yes to, and there's nothing to remember to cancel. Pro covers the AI cost of importing your
          orders; planning outfits stays free.
        </p>
      </section>
    </div>
  );
}
