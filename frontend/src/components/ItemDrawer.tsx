import { Camera, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "../api/client";
import type { Item, ItemEdit, Status } from "../api/types";
import { useToast } from "../context";
import { CATEGORY_LABELS, STATUS_LABELS, daysAgo, formatMoney } from "../lib/format";
import ItemEditor from "./ItemEditor";
import { Button, Choice, Sheet } from "./ui";

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
  const [hasPhoto, setHasPhoto] = useState(item.has_real_photo);
  const [uploading, setUploading] = useState(false);
  const photoInput = useRef<HTMLInputElement>(null);

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateItem(item.id, draft);
      notify("Changes saved", "success");
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
    setUploading(true);
    try {
      const updated = await api.replacePhoto(item.id, file);
      setImage(updated.image_url);
      setHasPhoto(true);
      onSaved(updated);
      notify("Photo updated", "success");
    } catch (e) {
      showError(e);
    } finally {
      setUploading(false);
    }
  };

  const meta = [CATEGORY_LABELS[item.category], daysAgo(item.last_worn), item.retailer, item.price != null ? formatMoney(item.price, item.currency) : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <Sheet open onClose={onClose} title="Item details">
      <div className="mb-6 flex gap-4">
        <div className="relative h-36 w-28 shrink-0 overflow-hidden rounded-md bg-sunk">
          {image && <img src={image} alt={item.name} className="h-full w-full object-cover" />}
          <button
            onClick={() => photoInput.current?.click()}
            disabled={uploading}
            className="absolute inset-x-1.5 bottom-1.5 flex h-7 items-center justify-center gap-1 rounded-sm bg-card/95 text-[11px] font-medium text-ink hover:bg-card"
          >
            <Camera className="h-3.5 w-3.5" /> {uploading ? "Uploading…" : hasPhoto ? "Replace" : "Add photo"}
          </button>
          <input ref={photoInput} type="file" accept="image/*" hidden onChange={(e) => replacePhoto(e.target.files?.[0])} />
        </div>
        <div className="min-w-0 pt-1">
          <h2 className="display text-[22px]">{item.name}</h2>
          <p className="mt-2 text-[13px] text-muted">{meta}</p>
        </div>
      </div>

      <div className="mb-6">
        <p className="kicker mb-2 text-ink-2">Status</p>
        <div className="flex flex-wrap gap-1.5">
          {STATUS_CHOICES.map((s) => (
            <Choice key={s} active={draft.status === s} onClick={() => setDraft((d) => ({ ...d, status: s }))}>
              {STATUS_LABELS[s]}
            </Choice>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted">Unavailable means lent out, at home or being repaired. It won't be picked for outfits.</p>
      </div>

      <ItemEditor draft={draft} onChange={(patch) => setDraft((d) => ({ ...d, ...patch }))} />

      <div className="sticky bottom-0 -mx-5 mt-8 flex gap-2 border-t border-line bg-card px-5 pt-4">
        {confirmDelete ? (
          <>
            <p className="flex-1 self-center text-sm text-ink-2">Delete this item for good?</p>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              Keep
            </Button>
            <Button variant="danger" onClick={remove} loading={saving}>
              Delete
            </Button>
          </>
        ) : (
          <>
            <Button variant="danger" onClick={() => setConfirmDelete(true)} aria-label="Delete item" className="px-3">
              <Trash2 className="h-4 w-4" />
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
