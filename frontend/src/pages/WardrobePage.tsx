import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Item } from "../api/types";
import { WashIcon } from "../components/Icons";
import ItemCard from "../components/ItemCard";
import ItemDrawer from "../components/ItemDrawer";
import { Button, Chip, EmptyState, Notice, Skeleton, UpgradeBanner, inputClass } from "../components/ui";
import { useMe, useToast } from "../context";
import { CATEGORY_FILTERS, STATUS_LABELS } from "../lib/format";

export default function WardrobePage() {
  const { me, refresh: refreshMe } = useMe();
  const { notify, showError } = useToast();
  const [items, setItems] = useState<Item[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<Item | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await api.items({ category, status }));
      setLoadError(false);
    } catch {
      setLoadError(true);
    }
  }, [category, status]);

  useEffect(() => {
    void load();
  }, [load]);

  // Counts for the laundry buttons come from the full wardrobe, not the filtered view.
  const [allItems, setAllItems] = useState<Item[]>([]);
  useEffect(() => {
    api.items().then(setAllItems).catch(() => undefined);
  }, [items]);
  const wornCount = useMemo(() => allItems.filter((i) => i.status === "worn").length, [allItems]);
  const washCount = useMemo(() => allItems.filter((i) => i.status === "in_wash").length, [allItems]);

  const laundry = async (action: "wash" | "done") => {
    setBusy(true);
    try {
      const { updated } = action === "wash" ? await api.washWorn() : await api.laundryDone();
      notify(action === "wash" ? `${updated} item(s) in the wash` : `${updated} item(s) clean and available`, "success");
      await load();
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (id: number) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const deleteSelected = async () => {
    setBusy(true);
    try {
      const { deleted } = await api.bulkDelete([...selected]);
      notify(`Deleted ${deleted} item(s)`, "success");
      setSelected(new Set());
      setSelecting(false);
      await Promise.all([load(), refreshMe()]);
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  const nearLimit = me && !me.premium && me.item_limit !== null && me.confirmed_item_count >= me.item_limit - 2;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Wardrobe</h1>
          <p className="text-sm text-slate-500">{me ? `${me.confirmed_item_count} items` : " "}</p>
        </div>
        <Button
          variant={selecting ? "primary" : "secondary"}
          className="py-1.5"
          onClick={() => {
            setSelecting(!selecting);
            setSelected(new Set());
          }}
        >
          {selecting ? "Done" : "Select"}
        </Button>
      </div>

      {nearLimit && (
        <UpgradeBanner
          message={
            me!.confirmed_item_count >= me!.item_limit!
              ? `Your free wardrobe is full (${me!.item_limit} items).`
              : `${me!.item_limit! - me!.confirmed_item_count} free item slots left.`
          }
        />
      )}

      {(wornCount > 0 || washCount > 0) && (
        <div className="flex items-center gap-2 rounded-2xl bg-white p-3 ring-1 ring-slate-200">
          <WashIcon className="h-6 w-6 shrink-0 text-sky-600" />
          <div className="flex-1 text-sm text-slate-600">
            {wornCount > 0 && <span>{wornCount} worn</span>}
            {wornCount > 0 && washCount > 0 && " · "}
            {washCount > 0 && <span>{washCount} in the wash</span>}
          </div>
          {wornCount > 0 && (
            <Button variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => laundry("wash")} disabled={busy}>
              Put worn in wash
            </Button>
          )}
          {washCount > 0 && (
            <Button className="px-3 py-1.5 text-xs" onClick={() => laundry("done")} disabled={busy}>
              Laundry done
            </Button>
          )}
        </div>
      )}

      <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
        {CATEGORY_FILTERS.map((c) => (
          <Chip key={c.value} active={category === c.value} onClick={() => setCategory(c.value)}>
            {c.label}
          </Chip>
        ))}
      </div>
      <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
        <option value="">Any status (except returned)</option>
        {Object.entries(STATUS_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>

      {loadError && <Notice tone="error">Couldn't load your wardrobe. Check the server is running, then refresh the page.</Notice>}

      {items === null && !loadError && (
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="aspect-[3/4]" />
          ))}
        </div>
      )}

      {items?.length === 0 &&
        (category || status ? (
          <EmptyState title="Nothing matches these filters" body="Try another category or status." />
        ) : (
          <EmptyState
            title="Add your first item"
            body="Snap a photo of something you own and StripeFit will label it for you."
            action={
              <Link to="/add" className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">
                Add clothes
              </Link>
            }
          />
        ))}

      {!!items?.length && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {items.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              selectable={selecting}
              selected={selected.has(item.id)}
              onClick={() => (selecting ? toggle(item.id) : setOpen(item))}
            />
          ))}
        </div>
      )}

      {selecting && selected.size > 0 && (
        <div className="fixed inset-x-0 bottom-20 z-30 mx-auto flex max-w-md justify-center px-4">
          <Button variant="danger" className="w-full shadow-lg" onClick={deleteSelected} loading={busy}>
            Delete {selected.size} item{selected.size > 1 ? "s" : ""}
          </Button>
        </div>
      )}

      {open && (
        <ItemDrawer
          item={open}
          onClose={() => setOpen(null)}
          onSaved={(updated) => {
            setItems((list) => list?.map((i) => (i.id === updated.id ? updated : i)) ?? null);
            setOpen(null);
          }}
          onDeleted={(id) => {
            setItems((list) => list?.filter((i) => i.id !== id) ?? null);
            setOpen(null);
            void refreshMe();
          }}
        />
      )}
    </div>
  );
}
