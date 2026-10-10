import { ArrowLeft, CreditCard, FlaskConical, Lock } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Button, Notice } from "../components/ui";
import { useMe, useToast } from "../context";

/**
 * Demo checkout, used only while no Stripe keys are configured. Nothing is charged and no card
 * details are collected; "Pay" records a demo purchase and unlocks Pro so the features can be shown.
 */
export default function DemoCheckoutPage() {
  const { me } = useMe();
  const { showError } = useToast();
  const navigate = useNavigate();
  const [paying, setPaying] = useState(false);

  const pay = async () => {
    setPaying(true);
    try {
      const { session_id } = await api.demoCheckout();
      navigate(`/pro/success?session_id=${encodeURIComponent(session_id)}`, { replace: true });
    } catch (e) {
      showError(e);
      setPaying(false);
    }
  };

  if (me?.stripe_configured) {
    return (
      <Notice tone="info">
        Real Stripe test checkout is set up, so the demo checkout is off.{" "}
        <Link to="/pro" className="font-medium underline">
          Back to Pro
        </Link>
      </Notice>
    );
  }

  return (
    <div className="mx-auto max-w-md pt-2 md:pt-8">
      <Link to="/pro" className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-muted transition hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" /> Back
      </Link>

      <div className="overflow-hidden rounded-xl border border-line bg-card shadow-[var(--shadow-overlay)]">
        <div className="flex items-center gap-2 border-b border-warn/20 bg-warn-soft px-5 py-2.5 text-[12.5px] font-medium text-warn">
          <FlaskConical className="h-3.5 w-3.5" /> Demo checkout: no real payment is taken
        </div>

        <div className="p-6">
          <p className="eyebrow">StripeFit</p>
          <div className="mt-3 flex items-baseline justify-between gap-4">
            <h1 className="display text-[22px]">StripeFit Pro</h1>
            <p className="display font-mono text-[22px]">€2.99</p>
          </div>
          <p className="mt-1 text-[13px] text-muted">One-time purchase · no subscription</p>

          <dl className="mt-6 space-y-2 border-y border-line py-4 text-[13px]">
            <div className="flex justify-between">
              <dt className="text-ink-2">Unlimited wardrobe, order-email and Gmail import</dt>
              <dd className="font-mono">€2.99</dd>
            </div>
            <div className="flex justify-between font-medium">
              <dt>Total due today</dt>
              <dd className="font-mono">€2.99</dd>
            </div>
          </dl>

          <div className="mt-5 flex items-center gap-3 rounded-lg border border-line bg-paper px-4 py-3">
            <CreditCard className="h-4 w-4 text-ink-2" />
            <div className="min-w-0 flex-1">
              <p className="font-mono text-[13px] tracking-wide">4242 4242 4242 4242</p>
              <p className="text-[11.5px] text-muted">Test card · simulated, nothing is charged</p>
            </div>
          </div>

          <Button size="lg" className="mt-5 w-full" onClick={pay} loading={paying}>
            {paying ? "Processing" : "Pay €2.99"}
          </Button>
          <p className="mt-3 flex items-center justify-center gap-1.5 text-[11.5px] text-muted">
            <Lock className="h-3 w-3" /> Add Stripe test keys to use real Stripe Checkout instead.
          </p>
        </div>
      </div>
    </div>
  );
}
