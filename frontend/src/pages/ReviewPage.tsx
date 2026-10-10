import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Duplicate, ItemEdit, Owner, ReviewItem } from "../api/types";
import { CameraIcon } from "../components/Icons";
import ItemEditor from "../components/ItemEditor";
import { Button, EmptyState, Notice, Skeleton, UpgradeBanner } from "../components/ui";
import { useMe, useToast } from "../context";
import { formatMoney } from "../lib/format";

const SOURCE_LABELS: Record<string, string> = { photo: "📷 Photo", email: "✉️ Order email", gmail: "✉️ Gmail", manual: "Manual" };

function missingFields(d: ItemEdit): string[] {
  const missing: string[] = [];
  if (!d.category || d.category === "unknown") missing.push("category");
  if (!d.colours?.length || d.colours.every((c) => c === "unknown")) missing.push("colours");
  if (d.formality == null) missing.push("formality");
  if (d.warmth == null && d.category !== "shoes" && d.category !== "accessory") missing.push("warmth");
  if (d.waterproof == null && d.category === "outerwear") missing.push("waterproof");
  return missing;
}

function ReviewCard({ item, onDone }: { item: ReviewItem; onDone: (id: number, message: string) => void }) {
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
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [image, setImage] = useState(item.thumb_url);
  const [hasPhoto, setHasPhoto] = useState(item.has_real_photo);
  const photoInput = useRef<HTMLInputElement>(null);
  const missing = missingFields(draft);

  const confirm = async (decision?: "merge" | "keep_both") => {
    setBusy(true);
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
      setBusy(false);
    }
  };

  const reject = async () => {
    setBusy(true);
    try {
      await api.reject(item.id);
      onDone(item.id, "Removed from review");
    } catch (e) {
      showError(e);
      setBusy(false);
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

  const setOwner = (owner: Owner) => setDraft((d) => ({ ...d, owner }));

  return (
    <article className="space-y-4 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex gap-3">
        <div className="relative h-28 w-28 shrink-0 overflow-hidden rounded-2xl bg-slate-100">
          {image && <img src={image} alt={item.name} className="h-full w-full object-cover" />}
          {!hasPhoto && (
            <button
              onClick={() => photoInput.current?.click()}
              className="absolute inset-x-1 bottom-1 flex items-center justify-center gap-1 rounded-lg bg-white/95 py-1 text-[11px] font-semibold text-indigo-700"
            >
              <CameraIcon className="h-3.5 w-3.5" /> Add photo
            </button>
          )}
          <input ref={photoInput} type="file" accept="image/*" hidden onChange={(e) => addPhoto(e.target.files?.[0])} />
        </div>
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap gap-1">
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
              {SOURCE_LABELS[item.source] ?? item.source}
            </span>
            {item.retailer && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">{item.retailer}</span>
            )}
            {item.status === "on_the_way" && (
              <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700">On the way</span>
            )}
          </div>
          {item.confidence != null &&
            (item.low_confidence ? (
              <p className="text-xs font-semibold text-amber-700">AI wasn't sure about this one. Please double-check the highlighted fields.</p>
            ) : (
              <p className="text-xs text-slate-500">AI confidence {Math.round(item.confidence * 100)}%</p>
            ))}
          {item.price != null && <p className="text-xs text-slate-500">{formatMoney(item.price, item.currency)}</p>}
          {item.notes && <p className="text-xs italic text-slate-500">{item.notes}</p>}
        </div>
      </div>

      {item.owner !== "me" && item.prompt && (
        <div className="rounded-2xl bg-violet-50 p-3 ring-1 ring-violet-200">
          <p className="mb-2 text-sm font-semibold text-violet-900">{item.prompt}</p>
          <div className="flex flex-wrap gap-1.5">
            {(
              [
                ["me", "Yes, it's mine"],
                ["child", "My child's"],
                ["other", "Someone else's"],
              ] as [Owner, string][]
            ).map(([o, label]) => (
              <button
                key={o}
                onClick={() => setOwner(o)}
                className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                  draft.owner === o ? "bg-violet-700 text-white ring-violet-700" : "bg-white text-violet-800 ring-violet-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {draft.owner !== "me" && <p className="mt-2 text-xs text-violet-700">Kept in your wardrobe but never used in your outfits.</p>}
        </div>
      )}

      {duplicate && (
        <div className="rounded-2xl bg-amber-50 p-3 ring-1 ring-amber-200">
          <div className="flex items-center gap-3">
            {duplicate.item.thumb_url && <img src={duplicate.item.thumb_url} alt="" className="h-14 w-14 rounded-xl object-cover" />}
            <div className="text-sm">
              <p className="font-semibold text-amber-900">Looks like your {duplicate.item.name.toLowerCase()}. Same item?</p>
              <p className="text-xs text-amber-800">{duplicate.reason}</p>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button className="py-2" onClick={() => confirm("merge")} loading={busy}>
              Merge
            </Button>
            <Button variant="secondary" className="py-2" onClick={() => confirm("keep_both")} disabled={busy}>
              Keep both
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
        <div className="grid grid-cols-3 gap-2">
          <Button variant="secondary" onClick={reject} disabled={busy}>
            Reject
          </Button>
          <Button className="col-span-2" onClick={() => confirm()} loading={busy} disabled={missing.includes("category")}>
            {missing.includes("category") ? "Pick a category" : "Confirm"}
          </Button>
        </div>
      )}
      {duplicate && (
        <button onClick={reject} className="w-full text-center text-sm text-slate-500 underline" disabled={busy}>
          Not a duplicate, and I don't want it: reject
        </button>
      )}
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
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Review</h1>
        <p className="text-sm text-slate-500">Nothing joins your wardrobe until you confirm it.</p>
      </div>
      {failed && <Notice tone="error">Couldn't load the review queue. Check the server is running and refresh.</Notice>}
      {items === null && !failed && <Skeleton className="h-96" />}
      {items?.length === 0 && (
        <EmptyState
          title="All caught up"
          body="New items from photos or order emails will appear here for you to check."
          action={
            <Link to="/add" className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">
              Add clothes
            </Link>
          }
        />
      )}
      {items?.map((item) => <ReviewCard key={item.id} item={item} onDone={done} />)}
    </div>
  );
}
