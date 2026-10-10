import {
  Bike,
  Bus,
  Car,
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudSnow,
  CloudSun,
  Footprints,
  HelpCircle,
  Info,
  RefreshCw,
  Sun,
  ThumbsDown,
  ThumbsUp,
  TrainFront,
  Umbrella,
  Wind,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import type { Outfit, Slot, Weather } from "../api/types";
import { useToast } from "../context";
import { OCCASION_LABELS, SLOT_LABELS, TIMEZONE } from "../lib/format";
import { Button, IconButton } from "./ui";

const TRAVEL: Record<string, { icon: LucideIcon; label: string }> = {
  walk: { icon: Footprints, label: "Walking" },
  cycle: { icon: Bike, label: "Cycling" },
  bus: { icon: Bus, label: "Bus" },
  train: { icon: TrainFront, label: "Train / Luas" },
  car: { icon: Car, label: "Car" },
  unknown: { icon: HelpCircle, label: "Travel not given" },
};

export function weatherIcon(code: number | null): LucideIcon {
  if (code === null) return Cloud;
  if (code === 0 || code === 1) return Sun;
  if (code === 2) return CloudSun;
  if (code === 3) return Cloud;
  if (code === 45 || code === 48) return CloudFog;
  if (code >= 51 && code <= 57) return CloudDrizzle;
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return CloudRain;
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return CloudSnow;
  if (code >= 95) return CloudLightning;
  return Cloud;
}

function when(iso: string): string {
  return new Intl.DateTimeFormat("en-IE", { timeZone: TIMEZONE, weekday: "long", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(
    new Date(iso),
  );
}

export function WeatherBlock({ weather }: { weather: Weather }) {
  const Icon = weatherIcon(weather.weather_code);
  return (
    <div className="flex items-center gap-4">
      <Icon className="h-9 w-9 text-ink-2" strokeWidth={1.25} />
      <div>
        <p className="display text-[32px] leading-none">{Math.round(weather.temperature_c)}°</p>
        <p className="mt-1 text-xs text-muted">{weather.description}</p>
      </div>
      <dl className="space-y-1 border-l border-line pl-4 font-mono text-[11px] text-ink-2">
        <div className={`flex items-center gap-1.5 ${weather.is_wet ? "text-info" : ""}`}>
          <Umbrella className="h-3 w-3" /> <dt className="sr-only">Rain chance</dt>
          <dd>{weather.precipitation_probability ?? 0}%</dd>
        </div>
        {weather.wind_kmh != null && (
          <div className="flex items-center gap-1.5">
            <Wind className="h-3 w-3" /> <dt className="sr-only">Wind</dt>
            <dd>{Math.round(weather.wind_kmh)} km/h</dd>
          </div>
        )}
        <div className="truncate text-muted">{weather.location_name}</div>
      </dl>
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
  const travel = TRAVEL[p.travel_mode] ?? TRAVEL.unknown;
  const TravelIcon = travel.icon;

  return (
    <article className="animate-rise overflow-hidden rounded-xl border border-line bg-card shadow-[var(--shadow-card)]">
      {/* Headline: the occasion, when/where, and the weather that shaped the pick */}
      <header className="flex flex-col gap-5 border-b border-line bg-[linear-gradient(180deg,rgb(238_237_254/0.55),rgb(255_255_255/0))] p-5 md:flex-row md:items-end md:justify-between md:p-7">
        <div className="min-w-0">
          <p className="eyebrow mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>The look</span>
            {outfit.used_fallback && (
              <span className="tag bg-warn-soft text-warn" title="The AI's answer wasn't usable, so StripeFit's rules picked this outfit">
                Rule-based pick
              </span>
            )}
          </p>
          <h2 className="display text-[30px] md:text-[36px]">{OCCASION_LABELS[p.occasion] ?? p.occasion}</h2>
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-ink-2">
            <span>{when(p.datetime_iso)}</span>
            {p.destination && <span>· {p.destination}</span>}
            <span className="inline-flex items-center gap-1">
              · <TravelIcon className="h-3.5 w-3.5" /> {travel.label}
            </span>
            {p.dress_code && <span>· {p.dress_code}</span>}
          </p>
        </div>
        {outfit.weather ? (
          <WeatherBlock weather={outfit.weather} />
        ) : (
          <p className="text-[13px] text-muted">No forecast; weather ignored</p>
        )}
      </header>

      <div className="space-y-5 p-5 md:p-7">
        <blockquote className="border-l-2 border-accent pl-4 text-[16.5px] leading-relaxed text-ink">{outfit.explanation}</blockquote>

        {outfit.notices.length > 0 && (
          <ul className="space-y-1">
            {outfit.notices.map((n) => (
              <li key={n} className="flex items-start gap-2 text-[13px] text-muted">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {n}
              </li>
            ))}
          </ul>
        )}

        {outfit.slots.length > 0 && (
          <ul className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3 lg:grid-cols-5">
            {outfit.slots.map(({ slot, item }) => (
              <li key={`${slot}-${item.id}`} className="group">
                <div className="relative aspect-[4/5] overflow-hidden rounded-md bg-sunk">
                  {item.thumb_url && <img src={item.thumb_url} alt="" className="h-full w-full object-cover" />}
                  <IconButton
                    icon={RefreshCw}
                    label={`Swap ${SLOT_LABELS[slot].toLowerCase()}`}
                    spinning={busy === `swap-${slot}`}
                    disabled={busy !== null}
                    onClick={() => act(`swap-${slot}`, () => api.swap(outfit.id, slot as Slot))}
                    className="absolute bottom-2 right-2 h-8 w-8 bg-card/95 shadow-sm hover:bg-card"
                  />
                </div>
                <p className="kicker mt-2.5">{SLOT_LABELS[slot]}</p>
                <p className="mt-0.5 line-clamp-2 text-[14px] font-medium leading-snug">{item.name}</p>
              </li>
            ))}
          </ul>
        )}

        {outfit.gaps.length > 0 && (
          <section className="rounded-md border border-warn/35 bg-warn-soft px-4 py-3">
            <h3 className="kicker mb-1.5 text-warn">Missing pieces</h3>
            <ul className="space-y-1 text-sm text-ink">
              {outfit.gaps.map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <footer className="flex items-center gap-2 border-t border-line bg-[#fafbfd] px-5 py-3.5 md:px-7">
        <Button
          onClick={() => act("wear", () => api.wear(outfit.id), "Have a good one. Those items are now marked as worn.")}
          loading={busy === "wear"}
          disabled={outfit.worn || outfit.slots.length === 0 || busy !== null}
        >
          {outfit.worn ? "Worn today" : "Wear this"}
        </Button>
        <p className="hidden flex-1 text-xs text-muted sm:block">{outfit.worn ? "These items are in your worn pile." : "Marks these items as worn so they rest a while."}</p>
        <div className="ml-auto flex gap-1" role="group" aria-label="Rate this outfit">
          {(["up", "down"] as const).map((f) => {
            const Icon = f === "up" ? ThumbsUp : ThumbsDown;
            const active = outfit.feedback === f;
            return (
              <button
                key={f}
                onClick={() => act(`fb-${f}`, () => api.feedback(outfit.id, active ? null : f))}
                aria-pressed={active}
                aria-label={f === "up" ? "Good outfit" : "Not for me"}
                className={`grid h-10 w-10 place-items-center rounded-md border transition ${
                  active ? "border-accent bg-accent-soft text-accent" : "border-line-strong bg-card text-ink-2 shadow-[var(--shadow-xs)] hover:border-[#b5c0cc] hover:text-ink"
                }`}
              >
                <Icon className="h-4 w-4" strokeWidth={1.75} />
              </button>
            );
          })}
        </div>
      </footer>
    </article>
  );
}
