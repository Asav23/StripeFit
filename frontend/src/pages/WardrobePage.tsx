import { Plus, Shirt, Trash2, WashingMachine, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Item } from "../api/types";
import ItemCard from "../components/ItemCard";
import ItemDrawer from "../components/ItemDrawer";
import { Button, EmptyState, LinkButton, Notice, PageHeader, Portal, Skeleton, Tabs, UpgradeBanner } from "../components/ui";
import { useMe, useToast } from "../context";
import { CATEGORY_FILTERS, STATUS_LABELS } from "../lib/format";

export default function WardrobePage() {
  const { me, refresh: refreshMe } = useMe();
  const { notify, showError } = useToast();
  const [all, setAll] = useState<Item[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<Item | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  // Load the whole (non-returned) wardrobe once; filter locally so counts stay accurate.
  // Returned items are only fetched when that status is chosen.
  const load = useCallback(async () => {
    try {
      const base = await api.items();
      const returned = status === "returned" ? await api.items({ status: "returned" }) : [];
      setAll([...base, ...returned]);
      setLoadError(false);
    } catch {
      setLoadError(true);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const i of all ?? []) if (i.status !== "returned") c[i.category] = (c[i.category] ?? 0) + 1;
    return c;
  }, [all]);
  const byStatus = (s: string) => (all ?? []).filter((i) => i.status === s).length;
  const items = (all ?? []).filter((i) => (!category || i.category === category) && (status ? i.status === status : i.status !== "returned"));
  const wornCount = byStatus("worn");
  const washCount = byStatus("in_wash");
  const cleanCount = byStatus("available");

  const laundry = async (action: "wash" | "done") => {
    setBusy(true);
    try {
      const { updated } = action === "wash" ? await api.washWorn() : await api.laundryDone();
      notify(action === "wash" ? `${updated} item${updated === 1 ? "" : "s"} in the wash` : `${updated} item${updated === 1 ? "" : "s"} clean again`, "success");
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

  const stopSelecting = () => {
    setSelecting(false);
    setSelected(new Set());
  };

  const deleteSelected = async () => {
    setBusy(true);
    try {
      const { deleted } = await api.bulkDelete([...selected]);
      notify(`Deleted ${deleted} item${deleted === 1 ? "" : "s"}`, "success");
      stopSelecting();
      await Promise.all([load(), refreshMe()]);
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  const total = me?.confirmed_item_count;
  const nearLimit = me && !me.premium && me.item_limit !== null && me.confirmed_item_count >= me.item_limit - 2;
  const summary = all
    ? [`${cleanCount} clean`, washCount && `${washCount} in the wash`, wornCount && `${wornCount} worn`, byStatus("on_the_way") && `${byStatus("on_the_way")} on the way`]
        .filter(Boolean)
        .join(" · ")
    : "";

  return (
    <div>
      <PageHeader
        kicker={total !== undefined ? `${total} pieces` : "Your clothes"}
        title="Wardrobe"
        description={summary || undefined}
        actions={
          all?.length ? (
            selecting ? (
              <Button variant="ghost" size="sm" onClick={stopSelecting}>
                <X className="h-4 w-4" /> Cancel
              </Button>
            ) : (
              <>
                <Button variant="secondary" size="sm" onClick={() => setSelecting(true)}>
                  Select
                </Button>
                <LinkButton to="/add">
                  <Plus className="h-4 w-4" /> <span className="hidden sm:inline">Add</span>
                </LinkButton>
              </>
            )
          ) : undefined
        }
      />

      <div className="space-y-4">
        {nearLimit &&
          (me!.confirmed_item_count >= me!.item_limit! ? (
            <UpgradeBanner message={`Your free wardrobe is full (${me!.item_limit} items).`} />
          ) : (
            <p className="flex items-center gap-2 text-[13px] text-ink-2">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              {me!.item_limit! - me!.confirmed_item_count} free item slots left.
              <Link to="/pro" className="font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                Pro removes the limit
              </Link>
            </p>
          ))}

        {(wornCount > 0 || washCount > 0) && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-card px-4 py-3 shadow-[var(--shadow-card)]">
            <WashingMachine className="h-5 w-5 text-info" strokeWidth={1.75} />
            <p className="flex-1 text-sm text-ink-2">
              {wornCount > 0 && `${wornCount} worn`}
              {wornCount > 0 && washCount > 0 && " · "}
              {washCount > 0 && `${washCount} in the wash`}
              <span className="text-muted"> won't be picked for outfits</span>
            </p>
            <div className="flex gap-2">
              {wornCount > 0 && (
                <Button variant="secondary" size="sm" onClick={() => laundry("wash")} disabled={busy}>
                  Put worn in wash
                </Button>
              )}
              {washCount > 0 && (
                <Button size="sm" onClick={() => laundry("done")} disabled={busy}>
                  Laundry done
                </Button>
              )}
            </div>
          </div>
        )}

        <div className="flex items-end gap-4">
          <div className="min-w-0 flex-1">
            <Tabs
              label="Category"
              value={category}
              onChange={setCategory}
              options={CATEGORY_FILTERS.map((c) => ({
                value: c.value,
                label: c.label,
                count: c.value ? counts[c.value] ?? 0 : undefined,
              }))}
            />
          </div>
          <select
            className="field mb-1.5 hidden h-9 w-44 py-0 text-[13px] md:block"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="">Any status</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <select className="field h-9 py-0 text-[13px] md:hidden" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          <option value="">Any status</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-6">
        {loadError && <Notice tone="error">Couldn't load your wardrobe. Check the server is running, then refresh the page.</Notice>}

        {all === null && !loadError && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i}>
                <Skeleton className="aspect-[4/5]" />
                <Skeleton className="mt-3 h-4 w-3/4" />
                <Skeleton className="mt-2 h-3 w-1/3" />
              </div>
            ))}
          </div>
        )}

        {all !== null && items.length === 0 &&
          (all.length === 0 && !status ? (
            <EmptyState
              icon={Shirt}
              title="Start your wardrobe"
              body="Photograph something you own and StripeFit will label it for you. Then it can plan outfits from it."
              action={
                <LinkButton to="/add">
                  <Plus className="h-4 w-4" /> Add your first item
                </LinkButton>
              }
            />
          ) : (
            <EmptyState
              icon={Shirt}
              title="Nothing here"
              body="No items match these filters."
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setCategory("");
                    setStatus("");
                  }}
                >
                  Clear filters
                </Button>
              }
            />
          ))}

        {items.length > 0 && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-3 lg:grid-cols-4">
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
      </div>

      {selecting && (
        <Portal>
        <div className="fixed inset-x-0 bottom-[68px] z-30 border-t border-line bg-card/95 px-4 py-3 shadow-[0_-4px_16px_rgb(10_37_64/0.06)] backdrop-blur md:bottom-0 md:left-[232px]">
          <div className="mx-auto flex max-w-5xl items-center gap-3 md:px-6">
            <p className="flex-1 text-sm text-ink-2">
              {selected.size ? `${selected.size} selected` : "Tap items to select them"}
            </p>
            <Button variant="danger" onClick={deleteSelected} loading={busy} disabled={!selected.size}>
              <Trash2 className="h-4 w-4" /> Delete
            </Button>
          </div>
        </div>
        </Portal>
      )}

      {open && (
        <ItemDrawer
          item={open}
          onClose={() => setOpen(null)}
          onSaved={(updated) => {
            setAll((list) => list?.map((i) => (i.id === updated.id ? updated : i)) ?? null);
            setOpen(null);
          }}
          onDeleted={(id) => {
            setAll((list) => list?.filter((i) => i.id !== id) ?? null);
            setOpen(null);
            void refreshMe();
          }}
        />
      )}
    </div>
  );
}
