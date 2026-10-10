import type { Category, Owner, Slot, Status } from "../api/types";

export const TIMEZONE = "Europe/Dublin";

export const CATEGORY_LABELS: Record<Category, string> = {
  top: "Top",
  bottom: "Bottom",
  one_piece: "Dress / one-piece",
  outerwear: "Outerwear",
  shoes: "Shoes",
  accessory: "Accessory",
  sportswear: "Sportswear",
  unknown: "Unknown",
};

export const CATEGORY_FILTERS: { value: string; label: string }[] = [
  { value: "", label: "All" },
  { value: "top", label: "Tops" },
  { value: "bottom", label: "Bottoms" },
  { value: "one_piece", label: "Dresses" },
  { value: "outerwear", label: "Outerwear" },
  { value: "shoes", label: "Shoes" },
  { value: "accessory", label: "Accessories" },
  { value: "sportswear", label: "Sport" },
];

export const STATUS_LABELS: Record<Status, string> = {
  available: "Available",
  worn: "Worn",
  in_wash: "In the wash",
  unavailable: "Unavailable",
  on_the_way: "On the way",
  returned: "Returned",
};

export const STATUS_STYLES: Record<Status, string> = {
  available: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  worn: "bg-amber-50 text-amber-700 ring-amber-200",
  in_wash: "bg-sky-50 text-sky-700 ring-sky-200",
  unavailable: "bg-slate-100 text-slate-600 ring-slate-200",
  on_the_way: "bg-violet-50 text-violet-700 ring-violet-200",
  returned: "bg-rose-50 text-rose-700 ring-rose-200",
};

export const OWNER_LABELS: Record<Owner, string> = {
  me: "Mine",
  child: "My child's",
  other: "Someone else's",
  unknown: "Not sure",
};

export const SLOT_LABELS: Record<Slot, string> = {
  top: "Top",
  bottom: "Bottom",
  one_piece: "Dress",
  outerwear: "Outerwear",
  shoes: "Shoes",
  accessory: "Accessory",
};

export const FORMALITY_LABELS = ["", "Gym / lounge", "Casual", "Smart casual", "Smart", "Black tie"];
export const WARMTH_LABELS = ["", "Very light", "Light", "Medium", "Warm", "Very warm"];

export const OCCASION_LABELS: Record<string, string> = {
  uni: "Uni",
  casual: "Casual",
  night_out: "Night out",
  date: "Date",
  interview: "Interview",
  work: "Work",
  wedding: "Wedding",
  funeral: "Funeral",
  sport: "Sport",
  other: "Other",
};

export const TRAVEL_LABELS: Record<string, string> = {
  walk: "🚶 Walking",
  cycle: "🚲 Cycling",
  bus: "🚌 Bus",
  train: "🚆 Train / Luas",
  car: "🚗 Car",
  unknown: "Travel not given",
};

const COLOURS: Record<string, string> = {
  black: "#212124", white: "#f5f5f2", grey: "#8c9096", gray: "#8c9096", charcoal: "#46484e", navy: "#1f2d54",
  blue: "#3465b4", "light blue": "#96bee6", denim: "#48668c", red: "#c43030", burgundy: "#6e1c2c", pink: "#e896af",
  purple: "#6e4696", green: "#3c8250", olive: "#6e703c", khaki: "#b0a06e", yellow: "#eec83c", mustard: "#cda028",
  orange: "#e47828", brown: "#6e482c", tan: "#c49664", camel: "#c19a6b", beige: "#dcc8aa", cream: "#f0e6cd",
  ecru: "#e8e0c8", stone: "#c8beaa", silver: "#bec0c4", gold: "#d2af46", teal: "#288080",
};

export function colourCss(name: string): string | null {
  const key = name.toLowerCase();
  if (COLOURS[key]) return COLOURS[key];
  const partial = Object.keys(COLOURS).find((c) => key.includes(c));
  return partial ? COLOURS[partial] : null;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("en-IE", {
    timeZone: TIMEZONE,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("en-IE", { timeZone: TIMEZONE, day: "numeric", month: "short", year: "numeric" }).format(
    new Date(iso),
  );
}

export function daysAgo(iso: string | null): string {
  if (!iso) return "Never worn";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "Worn today";
  if (days === 1) return "Worn yesterday";
  return `Worn ${days} days ago`;
}

export function formatMoney(amount: number | null, currency: string | null, minorUnits = false): string {
  if (amount == null) return "";
  const value = minorUnits ? amount / 100 : amount;
  return new Intl.NumberFormat("en-IE", { style: "currency", currency: (currency || "EUR").toUpperCase() }).format(value);
}

export function titleCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
