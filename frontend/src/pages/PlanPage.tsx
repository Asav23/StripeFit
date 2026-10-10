import { ArrowRight, CornerDownLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { Outfit } from "../api/types";
import OutfitCard from "../components/OutfitCard";
import { Button, LinkButton, Notice, PageHeader, SectionTitle, Skeleton } from "../components/ui";
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
const STEPS = ["Reading your plans", "Checking the weather", "Picking from your wardrobe"];

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
  const result = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.outfits().then(setHistory).catch(() => undefined);
  }, [outfit?.id]);

  useEffect(() => {
    if (!loading) return;
    setStep(0);
    const timer = window.setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 1200);
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
      const response = await api.plan(trimmed);
      if (response.clarification) {
        setClarification(response.clarification);
        setOutfit(null);
        textarea.current?.focus();
      } else {
        setOutfit(response.outfit);
        // Bring the result into view (it starts below the fold on phones).
        requestAnimationFrame(() => result.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
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

  const past = history.filter((h) => h.id !== outfit?.id).slice(0, 8);

  return (
    <div>
      <PageHeader kicker="Plan an outfit" title="Where are you going?" description="We'll pick from clean clothes you own, dressed for the occasion and the forecast." />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void plan();
        }}
        className="rounded-lg border border-line-strong bg-card transition focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgb(29_27_24/0.06)]"
      >
        <label htmlFor="plan-input" className="sr-only">
          Where are you going, when, and how are you getting there?
        </label>
        <textarea
          id="plan-input"
          ref={textarea}
          rows={2}
          maxLength={MAX_CHARS}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void plan();
            }
          }}
          placeholder="Interview tomorrow at 10 in Grand Canal Dock, walking…"
          className="block w-full resize-none bg-transparent px-4 pb-2 pt-4 text-[18px] leading-relaxed outline-none placeholder:text-muted md:px-5 md:text-[20px]"
        />
        <div className="flex items-center gap-3 px-3 pb-3 md:px-4">
          <span className="hidden items-center gap-1 font-mono text-[11px] text-muted sm:inline-flex">
            <CornerDownLeft className="h-3 w-3" /> to plan
          </span>
          {text.length > MAX_CHARS * 0.8 && (
            <span className="font-mono text-[11px] text-warn">
              {text.length}/{MAX_CHARS}
            </span>
          )}
          <Button type="submit" className="ml-auto" loading={loading}>
            {loading ? STEPS[step] : "Plan outfit"}
            {!loading && <ArrowRight className="h-4 w-4" />}
          </Button>
        </div>
      </form>

      <div className="mt-4 flex flex-wrap items-baseline gap-x-1 gap-y-2">
        <span className="kicker mr-2">Try</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => void plan(ex)}
            disabled={loading}
            className="rounded-sm px-1.5 py-0.5 text-[13px] text-ink-2 underline decoration-line-strong underline-offset-4 transition hover:bg-sunk hover:text-ink hover:decoration-ink disabled:opacity-50"
          >
            {ex}
          </button>
        ))}
      </div>

      <div ref={result} className="mt-8 scroll-mt-20 space-y-4">
        {clarification && (
          <Notice tone="warn">{clarification}</Notice>
        )}

        {blocker && (
          <Notice tone="warn">
            <p className="font-medium">{blocker.message}</p>
            {blocker.nextStep && <p className="text-ink-2">{blocker.nextStep}</p>}
            <div className="mt-3">
              <LinkButton to={blocker.code === "empty_wardrobe" ? "/add" : "/"} variant="secondary">
                {blocker.code === "empty_wardrobe" ? "Add clothes" : "Go to wardrobe"}
              </LinkButton>
            </div>
          </Notice>
        )}

        {loading && (
          <div className="overflow-hidden rounded-lg border border-line bg-card" aria-busy="true">
            <div className="flex items-end justify-between border-b border-line p-5 md:p-7">
              <div className="space-y-3">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-12 w-48" />
                <Skeleton className="h-3 w-64" />
              </div>
              <Skeleton className="hidden h-12 w-40 md:block" />
            </div>
            <div className="space-y-5 p-5 md:p-7">
              <Skeleton className="h-12" />
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="aspect-[4/5]" />
                ))}
              </div>
            </div>
          </div>
        )}

        {!loading && outfit && <OutfitCard outfit={outfit} onChange={setOutfit} />}
      </div>

      {past.length > 0 && (
        <section className="mt-12">
          <SectionTitle>Recent plans</SectionTitle>
          <ul className="divide-y divide-line">
            {past.map((h) => (
              <li key={h.id}>
                <button
                  onClick={() => {
                    setOutfit(h);
                    setClarification(null);
                    setBlocker(null);
                    result.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                  className="group flex w-full items-center gap-4 py-3 text-left"
                >
                  <div className="flex -space-x-2">
                    {h.slots.slice(0, 3).map(({ item }) => (
                      <img key={item.id} src={item.thumb_url ?? ""} alt="" className="h-11 w-9 rounded-sm border-2 border-paper bg-sunk object-cover" />
                    ))}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium group-hover:underline group-hover:underline-offset-4">{h.request_text}</p>
                    <p className="mt-0.5 font-mono text-[11px] text-muted">
                      {OCCASION_LABELS[h.parsed.occasion] ?? h.parsed.occasion} · {formatDateTime(h.created_at)}
                      {h.feedback === "up" && " · liked"}
                      {h.feedback === "down" && " · disliked"}
                      {h.worn && " · worn"}
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-ink" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
