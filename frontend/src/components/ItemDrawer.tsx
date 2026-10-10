import { useRef, useState } from "react";
import { api } from "../api/client";
import type { Item, ItemEdit, Status } from "../api/types";
import { useToast } from "../context";
import { STATUS_LABELS, daysAgo, formatMoney } from "../lib/format";
import { CameraIcon, TrashIcon, XIcon } from "./Icons";
import ItemEditor from "./ItemEditor";
import { Button, Sheet } from "./ui";

const STATUS_CHOICES: Status[] = ["available", "worn", "in_wash", "unavailable", "on_the_way", "returned"];

export default function ItemDrawer({
  item,
  onClose,
  onSaved,
  onDeleted,
}: {
  item: Item;
  onClose: () => void;
  onSaved: (item: Item) => void;
  onDeleted: (id: number) => void;
}) {
  const { notify, showError } = useToast();
  const [draft, setDraft] = useState<ItemEdit>({
    name: item.name,
    category: item.category,
    colours: item.colours,
    formality: item.formality,
    warmth: item.warmth,
    waterproof: item.waterproof,
    material: item.material,
    owner: item.owner,
    status: item.status,
    size: item.size,
  });
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [image, setImage] = useState(item.image_url);
  const photoInput = useRef<HTMLInputElement>(null);

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateItem(item.id, draft);
      notify("Saved", "success");
      onSaved(updated);
    } catch (e) {
      showError(e);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setSaving(true);
    try {
      await api.deleteItem(item.id);
      notify(`Deleted ${item.name}`, "success");
      onDeleted(item.id);
    } catch (e) {
      showError(e);
      setSaving(false);
    }
  };

  const replacePhoto = async (file: File | undefined) => {
    if (!file) return;
    try {
      const updated = await api.replacePhoto(item.id, file);
      setImage(updated.image_url);
      onSaved(updated);
      notify("Photo updated", "success");
    } catch (e) {
      showError(e);
    }
  };

  return (
    <Sheet open onClose={onClose} title={item.name}>
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h2 className="text-lg font-bold">{item.name}</h2>
          <p className="text-xs text-slate-500">
            {daysAgo(item.last_worn)}
            {item.retailer && ` · ${item.retailer}`}
            {item.price != null && ` · ${formatMoney(item.price, item.currency)}`}
          </p>
        </div>
        <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-200" aria-label="Close">
          <XIcon className="h-5 w-5" />
        </button>
      </div>

      <div className="relative mb-4 overflow-hidden rounded-2xl bg-slate-100">
        {image && <img src={image} alt={item.name} className="mx-auto max-h-72 object-contain" />}
        <button
          onClick={() => photoInput.current?.click()}
          className="absolute bottom-2 right-2 flex items-center gap-1 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 shadow"
        >
          <CameraIcon className="h-4 w-4" /> {item.has_real_photo ? "Replace photo" : "Add photo"}
        </button>
        <input ref={photoInput} type="file" accept="image/*" hidden onChange={(e) => replacePhoto(e.target.files?.[0])} />
      </div>

      <div className="mb-4">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Status</p>
        <div className="flex flex-wrap gap-1.5">
          {STATUS_CHOICES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setDraft((d) => ({ ...d, status: s }))}
              className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                draft.status === s ? "bg-slate-800 text-white ring-slate-800" : "bg-white text-slate-600 ring-slate-200"
              }`}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-slate-500">“Unavailable” = lent out, at home, being repaired… it won't be picked for outfits.</p>
      </div>

      <ItemEditor draft={draft} onChange={(patch) => setDraft((d) => ({ ...d, ...patch }))} />

      <div className="mt-6 flex gap-2">
        {confirmDelete ? (
          <>
            <Button variant="danger" className="flex-1" onClick={remove} loading={saving}>
              Yes, delete
            </Button>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button variant="danger" onClick={() => setConfirmDelete(true)} aria-label="Delete item">
              <TrashIcon className="h-4 w-4" />
            </Button>
            <Button className="flex-1" onClick={save} loading={saving}>
              Save changes
            </Button>
          </>
        )}
      </div>
    </Sheet>
  );
}
