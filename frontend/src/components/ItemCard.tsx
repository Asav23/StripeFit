import type { Item } from "../api/types";
import { CATEGORY_LABELS } from "../lib/format";
import { ColourDots, StatusChip } from "./ui";

export default function ItemCard({
  item,
  onClick,
  selectable = false,
  selected = false,
}: {
  item: Item;
  onClick: () => void;
  selectable?: boolean;
  selected?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group relative overflow-hidden rounded-2xl bg-white text-left shadow-sm ring-1 transition hover:shadow-md ${
        selected ? "ring-2 ring-indigo-500" : "ring-slate-200"
      } ${item.status !== "available" ? "opacity-80" : ""}`}
    >
      <div className="aspect-square overflow-hidden bg-slate-100">
        {item.thumb_url && <img src={item.thumb_url} alt={item.name} loading="lazy" className="h-full w-full object-cover" />}
      </div>
      {selectable && (
        <span
          className={`absolute left-2 top-2 grid h-6 w-6 place-items-center rounded-full text-xs font-bold ring-2 ring-white ${
            selected ? "bg-indigo-600 text-white" : "bg-white/90 text-transparent"
          }`}
        >
          ✓
        </span>
      )}
      {item.owner !== "me" && (
        <span className="absolute right-2 top-2 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
          {item.owner === "child" ? "Child's" : "Not mine"}
        </span>
      )}
      <div className="space-y-1.5 p-2.5">
        <p className="line-clamp-2 text-sm font-semibold leading-tight text-slate-800">{item.name}</p>
        <div className="flex items-center justify-between gap-1">
          <span className="text-xs text-slate-500">{CATEGORY_LABELS[item.category]}</span>
          <ColourDots colours={item.colours} size="h-3 w-3" />
        </div>
        <StatusChip status={item.status} />
      </div>
    </button>
  );
}
