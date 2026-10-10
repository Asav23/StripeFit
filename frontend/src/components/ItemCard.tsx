import { Check } from "lucide-react";
import type { Item } from "../api/types";
import { CATEGORY_LABELS } from "../lib/format";
import { ColourDots, StatusLabel } from "./ui";

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
  const away = item.status !== "available";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selectable ? selected : undefined}
      className="group block w-full text-left"
    >
      <div
        className={`relative aspect-[4/5] overflow-hidden rounded-md bg-sunk transition ${
          selected ? "ring-2 ring-ink ring-offset-2 ring-offset-paper" : ""
        }`}
      >
        {item.thumb_url && (
          <img
            src={item.thumb_url}
            alt=""
            loading="lazy"
            className={`h-full w-full object-cover transition duration-300 group-hover:scale-[1.03] ${away ? "opacity-50" : ""}`}
          />
        )}
        {away && (
          <span className="absolute left-2 top-2 rounded-sm bg-card/95 px-1.5 py-0.5">
            <StatusLabel status={item.status} />
          </span>
        )}
        {item.owner !== "me" && <span className="tag absolute right-2 top-2">{item.owner === "child" ? "Child's" : "Not mine"}</span>}
        {selectable && (
          <span
            className={`absolute bottom-2 right-2 grid h-6 w-6 place-items-center rounded-full border transition ${
              selected ? "border-ink bg-ink text-paper" : "border-ink/30 bg-card/90 text-transparent"
            }`}
          >
            <Check className="h-3.5 w-3.5" strokeWidth={3} />
          </span>
        )}
      </div>
      <div className="pt-2.5">
        <p className="line-clamp-2 text-[14px] font-medium leading-snug text-ink group-hover:underline group-hover:decoration-line-strong group-hover:underline-offset-4">
          {item.name}
        </p>
        <div className="mt-1 flex items-center gap-2">
          <span className="text-xs text-muted">{CATEGORY_LABELS[item.category]}</span>
          <ColourDots colours={item.colours} size="h-2.5 w-2.5" />
        </div>
      </div>
    </button>
  );
}
