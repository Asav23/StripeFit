import { ArrowRight, CheckCircle2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Purchase } from "../api/types";
import { Button, LinkButton, Notice, SectionTitle, Spinner } from "../components/ui";
import { useMe } from "../context";
import { PurchaseRecord } from "./ProPage";

const POLL_MS = 1500;
const MAX_POLLS = 10;

type State = "checking" | "paid" | "pending" | "error";

export default function ProSuccessPage() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const { refresh } = useMe();
  const [state, setState] = useState<State>("checking");
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Confirm with Stripe via our backend (covers a late webhook), then refresh the plan.
  const check = useCallback(async () => {
    if (!sessionId) {
      setState("error");
      setError("This page needs a checkout session. Start from the Pro tab.");
      return;
    }
    setState("checking");
    for (let attempt = 0; attempt < MAX_POLLS; attempt++) {
      try {
        const result = await api.stripeSession(sessionId);
        if (result.paid && result.purchase) {
          setPurchase(result.purchase);
          setState("paid");
          await refresh();
          return;
        }
      } catch (e) {
        setState("error");
        setError(e instanceof Error ? e.message : "Couldn't confirm your payment.");
        return;
      }
      await new Promise((r) => setTimeout(r, POLL_MS));
    }
    setState("pending");
  }, [sessionId, refresh]);

  useEffect(() => {
    void check();
  }, [check]);

  return (
    <div className="mx-auto max-w-lg pt-6">
      {state === "checking" && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <Spinner className="h-7 w-7" />
          <p className="text-ink-2">Confirming your payment with Stripe…</p>
        </div>
      )}
      {state === "paid" && purchase && (
        <div className="animate-rise space-y-8">
          <div className="text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-ok" strokeWidth={1.5} />
            <p className="kicker mt-4">Payment confirmed</p>
            <h1 className="display mt-1 text-[48px]">Pro is yours</h1>
            <p className="mt-2 text-ink-2">Unlimited items and order import are unlocked.</p>
          </div>
          <section>
            <SectionTitle>Receipt</SectionTitle>
            <PurchaseRecord purchase={purchase} />
          </section>
          <div className="flex flex-wrap justify-center gap-2">
            <LinkButton to="/add?tab=order">
              Import your orders <ArrowRight className="h-4 w-4" />
            </LinkButton>
            <LinkButton to="/" variant="secondary">
              Back to wardrobe
            </LinkButton>
          </div>
        </div>
      )}
      {state === "pending" && (
        <Notice tone="warn">
          <p className="font-medium">Your payment is still processing.</p>
          <p className="text-ink-2">This usually takes a few seconds.</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={check}>
            Check again
          </Button>
        </Notice>
      )}
      {state === "error" && (
        <Notice tone="error">
          <p className="font-medium">{error}</p>
          <div className="mt-3">
            <LinkButton to="/pro" variant="secondary">
              Back to Pro
            </LinkButton>
          </div>
        </Notice>
      )}
    </div>
  );
}
