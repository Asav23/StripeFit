import { Camera, ClipboardCheck, Copy, Plus, UserRound } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { Duplicate, ItemEdit, Owner, ReviewItem } from "../api/types";
import ItemEditor from "../components/ItemEditor";
import { Button, Choice, EmptyState, LinkButton, Notice, PageHeader, Skeleton, UpgradeBanner } from "../components/ui";
import { useMe, useToast } from "../context";
import { formatMoney } from "../lib/format";

const SOURCE_LABELS: Record<string, string> = { photo: "Photo", email: "Order email", gmail: "Gmail", manual: "Manual" };

function missingFields(d: ItemEdit): string[] {
  const missing: string[] = [];
  if (!d.category || d.category === "unknown") missing.push("category");
  if (!d.colours?.length || d.colours.every((c) => c === "unknown")) missing.push("colours");
  if (d.formality == null) missing.push("formality");
  if (d.warmth == null && d.category !== "shoes" && d.category !== "accessory") missing.push("warmth");
  if (d.waterproof == null && d.category === "outerwear") missing.push("waterproof");
  return missing;
}

function ReviewCard({ item, index, onDone }: { item: ReviewItem; index: number; onDone: (id: number, message: string) => void }) {
  const { showError } = useToast();
  const [draft, setDraft] = useState<ItemEdit>({
    name: item.name,
    category: item.category,
    colours: item.colours,
    formality: item.formality,
    warmth: item.warmth,
    waterproof: item.waterproof,
    material: item.material,
    owner: item.owner,
    size: item.size,
  });
  const [duplicate, setDuplicate] = useState<Duplicate | null>(item.duplicate);
  const [busy, setBusy] = useState<"confirm" | "merge" | "keep" | "reject" | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [image, setImage] = useState(item.thumb_url);
  const [hasPhoto, setHasPhoto] = useState(item.has_real_photo);
  const photoInput = useRef<HTMLInputElement>(null);
  const missing = missingFields(draft);

  const confirm = async (decision?: "merge" | "keep_both") => {
    setBusy(decision === "merge" ? "merge" : decision === "keep_both" ? "keep" : "confirm");
    try {
      const result = await api.confirm(item.id, {
        ...draft,
        duplicate_decision: decision,
        merge_target_id: decision === "merge" ? duplicate?.item.id : undefined,
      });
      onDone(item.id, result.merged ? `Merged into your ${result.item.name.toLowerCase()}` : `${result.item.name} added to your wardrobe`);
    } catch (e) {
      if (e instanceof ApiError && e.code === "possible_duplicate") setDuplicate(e.detail.duplicate as Duplicate);
      else if (e instanceof ApiError && e.code === "upgrade_required") setBlocked(e.message);
      else showError(e);
      setBusy(null);
    }
  };

  const reject = async () => {
    setBusy("reject");
    try {
      await api.reject(item.id);
      onDone(item.id, "Removed from review");
    } catch (e) {
      showError(e);
      setBusy(null);
    }
  };

  const addPhoto = async (file?: File) => {
    if (!file) return;
    try {
      const updated = await api.replacePhoto(item.id, file);
      setImage(updated.thumb_url);
      setHasPhoto(true);
    } catch (e) {
      showError(e);
    }
  };

  const askOwner = item.owner !== "me" && item.prompt;
  const provenance = [SOURCE_LABELS[item.source] ?? item.source, item.retailer, item.size, item.price != null ? formatMoney(item.price, item.currency) : null].filter(Boolean);

  return (
    <article className="animate-rise border-t border-line pt-6 md:grid md:grid-cols-[220px_1fr] md:gap-10">
      <div className="mb-5 flex gap-4 md:mb-0 md:block">
        <div className="relative aspect-[4/5] w-28 shrink-0 overflow-hidden rounded-md bg-sunk md:w-full">
          {image && <img src={image} alt={item.name} className="h-full w-full object-cover" />}
          {!hasPhoto && (
            <button
              onClick={() => photoInput.current?.click()}
              className="absolute inset-x-1.5 bottom-1.5 flex h-7 items-center justify-center gap-1 rounded-sm bg-card/95 text-[11px] font-medium hover:bg-card"
            >
              <Camera className="h-3.5 w-3.5" /> Add photo
            </button>
          )}
          <input ref={photoInput} type="file" accept="image/*" hidden onChange={(e) => addPhoto(e.target.files?.[0])} />
        </div>
        <div className="min-w-0 space-y-2 md:mt-4">
          <p className="font-mono text-[11px] text-muted">No. {String(index + 1).padStart(2, "0")}</p>
          <div className="flex flex-wrap gap-1">
            {provenance.map((p) => (
              <span key={p} className="tag">
                {p}
              </span>
            ))}
            {item.status === "on_the_way" && <span className="tag border-accent/40 text-accent">On the way</span>}
          </div>
          {item.confidence != null && (
            <p className={`text-xs ${item.low_confidence ? "text-warn" : "text-muted"}`}>
              {item.low_confidence ? "The AI wasn't sure. Tinted fields are guesses." : `AI confidence ${Math.round(item.confidence * 100)}%`}
            </p>
          )}
          {item.notes && <p className="text-xs italic leading-relaxed text-muted">{item.notes}</p>}
        </div>
      </div>

      <div className="min-w-0 space-y-5">
        {askOwner && (
          <div className="rounded-lg border border-line bg-card p-4 shadow-[var(--shadow-card)]">
            <p className="mb-3 flex items-center gap-2 text-sm font-medium">
              <UserRound className="h-4 w-4 text-accent" /> {item.prompt}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {(
                [
                  ["me", "Yes, it's mine"],
                  ["child", "My child's"],
                  ["other", "Someone else's"],
                ] as [Owner, string][]
              ).map(([o, label]) => (
                <Choice key={o} active={draft.owner === o} onClick={() => setDraft((d) => ({ ...d, owner: o }))}>
                  {label}
                </Choice>
              ))}
            </div>
            {draft.owner !== "me" && <p className="mt-2 text-xs text-muted">It stays in your wardrobe but is never used in your outfits.</p>}
          </div>
        )}

        {duplicate && (
          <div className="rounded-md border border-warn/40 bg-warn-soft p-4">
            <div className="flex items-center gap-3">
              {duplicate.item.thumb_url && <img src={duplicate.item.thumb_url} alt="" className="h-14 w-12 rounded-sm object-cover" />}
              <div className="min-w-0 text-sm">
                <p className="flex items-center gap-1.5 font-medium">
                  <Copy className="h-3.5 w-3.5 text-warn" /> Looks like your {duplicate.item.name.toLowerCase()}. Same item?
                </p>
                <p className="mt-0.5 text-xs text-ink-2">{duplicate.reason}</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" onClick={() => confirm("merge")} loading={busy === "merge"} disabled={busy !== null}>
                Same item, merge
              </Button>
              <Button size="sm" variant="secondary" onClick={() => confirm("keep_both")} loading={busy === "keep"} disabled={busy !== null}>
                Different, keep both
              </Button>
              <Button size="sm" variant="ghost" onClick={reject} loading={busy === "reject"} disabled={busy !== null}>
                Discard this one
              </Button>
            </div>
          </div>
        )}

        <ItemEditor
          draft={draft}
          onChange={(patch) => setDraft((d) => ({ ...d, ...patch }))}
          missing={missing}
          uncertain={item.low_confidence}
          showOwner={item.owner === "me"}
        />

        {blocked && <UpgradeBanner message={blocked} />}

        {!duplicate && (
          <div className="flex items-center gap-2 border-t border-line pt-4">
            <p className="hidden flex-1 text-xs text-muted sm:block">
              {missing.length ? `${missing.length} field${missing.length > 1 ? "s" : ""} still empty. You can fill them in later.` : "All labels filled in."}
            </p>
            <Button variant="ghost" onClick={reject} loading={busy === "reject"} disabled={busy !== null}>
              Reject
            </Button>
            <Button onClick={() => confirm()} loading={busy === "confirm"} disabled={busy !== null || missing.includes("category")} className="flex-1 sm:flex-none">
              {missing.includes("category") ? "Pick a category" : "Add to wardrobe"}
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}

export default function ReviewPage() {
  const { refresh } = useMe();
  const { notify } = useToast();
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await api.review());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const done = (id: number, message: string) => {
    notify(message, "success");
    setItems((list) => list?.filter((i) => i.id !== id) ?? null);
    void refresh();
  };

  return (
    <div>
      <PageHeader
        kicker={items?.length ? `${items.length} waiting` : "Review"}
        title="Check before it's yours"
        description="The AI's labels are a first draft. Nothing joins your wardrobe until you confirm it."
      />
      {failed && <Notice tone="error">Couldn't load the review queue. Check the server is running and refresh.</Notice>}
      {items === null && !failed && (
        <div className="grid gap-10 border-t border-line pt-6 md:grid-cols-[220px_1fr]">
          <Skeleton className="aspect-[4/5]" />
          <div className="space-y-4">
            <Skeleton className="h-10" />
            <Skeleton className="h-16" />
            <Skeleton className="h-24" />
          </div>
        </div>
      )}
      {items?.length === 0 && (
        <EmptyState
          icon={ClipboardCheck}
          title="All caught up"
          body="Items from photos and order emails wait here for you to check."
          action={
            <LinkButton to="/add">
              <Plus className="h-4 w-4" /> Add clothes
            </LinkButton>
          }
        />
      )}
      <div className="space-y-10">
        {items?.map((item, i) => <ReviewCard key={item.id} item={item} index={i} onDone={done} />)}
      </div>
    </div>
  );
}
