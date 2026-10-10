import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Outfit } from "../api/types";
import OutfitCard from "../components/OutfitCard";
import { Button, Chip, Notice, Skeleton, inputClass } from "../components/ui";
import { useToast } from "../context";
import { OCCASION_LABELS, formatDateTime } from "../lib/format";

const EXAMPLES = [
  "Interview tomorrow 10am in Grand Canal Dock, walking",
  "Football training tonight",
  "Night out Saturday in town",
  "Lectures at UCD tomorrow, cycling",
  "Cousin's wedding Saturday afternoon in Galway",
];
const MAX_CHARS = 500;
const STEPS = ["Reading your plans…", "Checking the weather…", "Picking from your wardrobe…"];

export default function PlanPage() {
  const { showError } = useToast();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);
  const [outfit, setOutfit] = useState<Outfit | null>(null);
  const [clarification, setClarification] = useState<string | null>(null);
  const [blocker, setBlocker] = useState<{ message: string; nextStep?: string; code: string } | null>(null);
  const [history, setHistory] = useState<Outfit[]>([]);
  const textarea = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.outfits().then(setHistory).catch(() => undefined);
  }, [outfit?.id]);

  useEffect(() => {
    if (!loading) return;
    setStep(0);
    const timer = window.setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 1400);
    return () => window.clearInterval(timer);
  }, [loading]);

  const plan = async (request = text) => {
    const trimmed = request.trim();
    if (!trimmed) {
      setClarification("Tell us where you're going and when, e.g. “Lectures at UCD tomorrow, cycling”.");
      textarea.current?.focus();
      return;
    }
    setText(request);
    setLoading(true);
    setClarification(null);
    setBlocker(null);
    try {
      const result = await api.plan(trimmed);
      if (result.clarification) {
        setClarification(result.clarification);
        setOutfit(null);
        textarea.current?.focus();
      } else {
        setOutfit(result.outfit);
      }
    } catch (e) {
      if (e instanceof ApiError && ["empty_wardrobe", "nothing_available"].includes(e.code)) {
        setBlocker({ message: e.message, nextStep: e.nextStep, code: e.code });
        setOutfit(null);
      } else {
        showError(e);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Plan an outfit</h1>
        <p className="text-sm text-slate-500">Where are you going? We'll pick from clean clothes you own, for the weather.</p>
      </div>

      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          void plan();
        }}
      >
        <textarea
          ref={textarea}
          rows={3}
          maxLength={MAX_CHARS}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void plan();
            }
          }}
          placeholder="e.g. Interview tomorrow 10am in Grand Canal Dock, walking"
          className={`${inputClass} resize-none text-base`}
        />
        <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
          {EXAMPLES.map((ex) => (
            <Chip key={ex} onClick={() => void plan(ex)} className="text-xs">
              {ex}
            </Chip>
          ))}
        </div>
        <Button type="submit" className="w-full py-3 text-base" loading={loading}>
          {loading ? STEPS[step] : "Plan my outfit"}
        </Button>
      </form>

      {clarification && (
        <Notice tone="warn">
          <strong>{clarification}</strong>
        </Notice>
      )}

      {blocker && (
        <Notice tone="warn">
          <p className="font-semibold">{blocker.message}</p>
          {blocker.nextStep && <p>{blocker.nextStep}</p>}
          <Link to={blocker.code === "empty_wardrobe" ? "/add" : "/"} className="mt-1 inline-block font-semibold underline">
            {blocker.code === "empty_wardrobe" ? "Add clothes →" : "Go to wardrobe →"}
          </Link>
        </Notice>
      )}

      {loading && (
        <div className="space-y-3 rounded-3xl bg-white p-4 ring-1 ring-slate-200">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-16" />
          <Skeleton className="h-10" />
          <div className="grid grid-cols-2 gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="aspect-square" />
            ))}
          </div>
        </div>
      )}

      {!loading && outfit && <OutfitCard outfit={outfit} onChange={setOutfit} />}

      {history.filter((h) => h.id !== outfit?.id).length > 0 && (
        <section className="space-y-2 pt-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Recent plans</h2>
          {history
            .filter((h) => h.id !== outfit?.id)
            .slice(0, 8)
            .map((h) => (
              <button
                key={h.id}
                onClick={() => {
                  setOutfit(h);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                className="flex w-full items-center gap-3 rounded-2xl bg-white p-2.5 text-left ring-1 ring-slate-200 hover:ring-slate-300"
              >
                <div className="flex -space-x-3">
                  {h.slots.slice(0, 3).map(({ item }) => (
                    <img key={item.id} src={item.thumb_url ?? ""} alt="" className="h-10 w-10 rounded-full object-cover ring-2 ring-white" />
                  ))}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-800">{h.request_text}</p>
                  <p className="text-xs text-slate-500">
                    {OCCASION_LABELS[h.parsed.occasion] ?? h.parsed.occasion} · {formatDateTime(h.created_at)}
                    {h.feedback === "up" && " · 👍"}
                    {h.feedback === "down" && " · 👎"}
                  </p>
                </div>
              </button>
            ))}
        </section>
      )}
    </div>
  );
}
