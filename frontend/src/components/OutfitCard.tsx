import { useState } from "react";
import { api } from "../api/client";
import type { Outfit, Slot, Weather } from "../api/types";
import { useToast } from "../context";
import { OCCASION_LABELS, SLOT_LABELS, TRAVEL_LABELS, formatDateTime } from "../lib/format";
import { RefreshIcon } from "./Icons";
import { Button, Notice } from "./ui";

export function WeatherChip({ weather }: { weather: Weather }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-gradient-to-br from-sky-50 to-indigo-50 p-3 ring-1 ring-sky-100">
      <span className="text-3xl" aria-hidden>
        {weather.icon}
      </span>
      <div className="flex-1">
        <p className="text-lg font-bold leading-tight">{Math.round(weather.temperature_c)}°C</p>
        <p className="text-xs text-slate-600">
          {weather.description} · {weather.location_name}
        </p>
      </div>
      <div className="text-right text-xs text-slate-600">
        <p className={weather.is_wet ? "font-bold text-sky-700" : ""}>☔ {weather.precipitation_probability ?? 0}%</p>
        {weather.wind_kmh != null && <p>💨 {Math.round(weather.wind_kmh)} km/h</p>}
      </div>
    </div>
  );
}

export default function OutfitCard({ outfit, onChange }: { outfit: Outfit; onChange: (o: Outfit) => void }) {
  const { notify, showError } = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  const act = async (key: string, task: () => Promise<Outfit>, message?: string) => {
    setBusy(key);
    try {
      onChange(await task());
      if (message) notify(message, "success");
    } catch (e) {
      showError(e);
    } finally {
      setBusy(null);
    }
  };

  const p = outfit.parsed;
  return (
    <section className="space-y-4 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="rounded-full bg-indigo-600 px-2.5 py-1 font-semibold text-white">{OCCASION_LABELS[p.occasion] ?? p.occasion}</span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">{formatDateTime(p.datetime_iso)}</span>
        {p.destination && <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">📍 {p.destination}</span>}
        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">{TRAVEL_LABELS[p.travel_mode] ?? p.travel_mode}</span>
        {p.dress_code && <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">{p.dress_code}</span>}
        {outfit.used_fallback && (
          <span className="rounded-full bg-amber-100 px-2.5 py-1 font-semibold text-amber-800" title="The AI's answer wasn't usable, so rules picked this outfit">
            Fallback used
          </span>
        )}
      </div>

      {outfit.weather && <WeatherChip weather={outfit.weather} />}
      {outfit.notices.map((n) => (
        <Notice key={n} tone="info">
          {n}
        </Notice>
      ))}

      <p className="text-[15px] leading-relaxed text-slate-700">{outfit.explanation}</p>

      {outfit.slots.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {outfit.slots.map(({ slot, item }) => (
            <div key={`${slot}-${item.id}`} className="overflow-hidden rounded-2xl ring-1 ring-slate-200">
              <div className="relative aspect-square bg-slate-100">
                {item.thumb_url && <img src={item.thumb_url} alt={item.name} className="h-full w-full object-cover" />}
                <span className="absolute left-2 top-2 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-600">
                  {SLOT_LABELS[slot]}
                </span>
              </div>
              <div className="flex items-center justify-between gap-1 p-2">
                <p className="line-clamp-2 text-xs font-semibold text-slate-800">{item.name}</p>
                <button
                  onClick={() => act(`swap-${slot}`, () => api.swap(outfit.id, slot as Slot))}
                  disabled={busy !== null}
                  className="shrink-0 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-indigo-600 disabled:opacity-40"
                  title={`Swap ${SLOT_LABELS[slot].toLowerCase()}`}
                  aria-label={`Swap ${SLOT_LABELS[slot]}`}
                >
                  <RefreshIcon className={`h-4 w-4 ${busy === `swap-${slot}` ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {outfit.gaps.length > 0 && (
        <div className="space-y-1 rounded-2xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
          <p className="font-semibold">Missing pieces</p>
          <ul className="list-disc space-y-1 pl-5">
            {outfit.gaps.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button
          className="flex-1"
          onClick={() => act("wear", () => api.wear(outfit.id), "Enjoy! Items marked as worn.")}
          loading={busy === "wear"}
          disabled={outfit.worn || outfit.slots.length === 0}
        >
          {outfit.worn ? "Worn ✓" : "Wear this"}
        </Button>
        {(["up", "down"] as const).map((f) => (
          <button
            key={f}
            onClick={() => act(`fb-${f}`, () => api.feedback(outfit.id, outfit.feedback === f ? null : f))}
            className={`rounded-xl px-3 py-2 text-lg ring-1 ${
              outfit.feedback === f ? "bg-indigo-50 ring-indigo-400" : "bg-white ring-slate-200"
            }`}
            aria-label={f === "up" ? "Good outfit" : "Bad outfit"}
          >
            {f === "up" ? "👍" : "👎"}
          </button>
        ))}
      </div>
    </section>
  );
}
