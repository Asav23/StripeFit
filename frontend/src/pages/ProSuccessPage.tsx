import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Purchase } from "../api/types";
import { Button, Notice, Spinner } from "../components/ui";
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
    <div className="space-y-5 pt-4">
      {state === "checking" && (
        <div className="flex flex-col items-center gap-3 py-12 text-slate-600">
          <Spinner className="h-8 w-8 text-indigo-600" />
          <p>Confirming your payment with Stripe…</p>
        </div>
      )}
      {state === "paid" && purchase && (
        <>
          <div className="rounded-3xl bg-gradient-to-br from-emerald-500 to-teal-600 p-6 text-center text-white shadow-lg">
            <p className="text-5xl">🎉</p>
            <p className="mt-2 text-2xl font-bold">Pro active</p>
            <p className="text-emerald-50">Unlimited items and order import are unlocked.</p>
          </div>
          <PurchaseRecord purchase={purchase} />
          <div className="grid grid-cols-2 gap-2">
            <Link to="/add?tab=order" className="rounded-xl bg-indigo-600 py-2.5 text-center text-sm font-semibold text-white">
              Import orders
            </Link>
            <Link to="/" className="rounded-xl bg-white py-2.5 text-center text-sm font-semibold text-slate-700 ring-1 ring-slate-300">
              Wardrobe
            </Link>
          </div>
        </>
      )}
      {state === "pending" && (
        <Notice tone="warn">
          <p className="font-semibold">Your payment is still processing.</p>
          <p>This usually takes a few seconds.</p>
          <Button variant="secondary" className="mt-2" onClick={check}>
            Check again
          </Button>
        </Notice>
      )}
      {state === "error" && (
        <Notice tone="error">
          <p className="font-semibold">{error}</p>
          <Link to="/pro" className="mt-1 inline-block font-semibold underline">
            Back to Pro →
          </Link>
        </Notice>
      )}
    </div>
  );
}
