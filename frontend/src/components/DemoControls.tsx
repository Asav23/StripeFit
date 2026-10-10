import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DemoEvent } from "../api/types";
import { useToast } from "../context";
import { Choice } from "./ui";

const WEATHER_PRESETS: { value: string | null; label: string }[] = [
  { value: null, label: "Real forecast" },
  { value: "rain", label: "Rain, 9°C" },
  { value: "cold", label: "Cold, 2°C" },
  { value: "hot", label: "Hot, 25°C" },
];

const CALENDAR_PRESETS: { key: string; label: string; events: DemoEvent[] | null }[] = [
  { key: "real", label: "Real calendar", events: null },
  {
    key: "interview",
    label: "Interview + football",
    events: [
      { title: "Interview at Accenture", start: "10:00", end: "11:00", location: "Grand Canal Dock" },
      { title: "Five-a-side", start: "19:00", end: "20:00", location: "Belfield" },
    ],
  },
  {
    key: "uni",
    label: "Lectures + night out",
    events: [
      { title: "COMP30010 lecture", start: "09:00", end: "13:00", location: "UCD" },
      { title: "Night out in town", start: "21:00", end: "23:59", location: "Temple Bar" },
    ],
  },
  { key: "wedding", label: "Wedding", events: [{ title: "Cousin's wedding", start: "13:00", end: "23:00", location: "Kilkenny" }] },
  { key: "free", label: "Nothing on", events: [] },
];

/** Switches for showing the rules and fallbacks live, whatever today's weather or AI is doing. */
export default function DemoControls({ mockAi }: { mockAi: boolean }) {
  const { notify, showError } = useToast();
  const [weather, setWeather] = useState<string | null>(null);
  const [invalidPick, setInvalidPick] = useState(false);
  const [calendarPreset, setCalendarPreset] = useState("real");

  useEffect(() => {
    api.weatherOverride().then((w) => setWeather(w.preset)).catch(() => undefined);
    api
      .demoCalendar()
      .then((c) => {
        const match = CALENDAR_PRESETS.find((p) => JSON.stringify(p.events) === JSON.stringify(c.events));
        setCalendarPreset(match ? match.key : c.events ? "custom" : "real");
      })
      .catch(() => undefined);
    if (mockAi) api.mockOverrides().then((m) => setInvalidPick(m.overrides.pick_outfit === "invalid")).catch(() => undefined);
  }, [mockAi]);

  const chooseWeather = async (preset: string | null) => {
    try {
      await api.setWeatherOverride(preset);
      setWeather(preset);
      notify(preset ? `Demo weather: ${preset}. Plan an outfit to see the rules.` : "Using the real forecast again.", "info");
    } catch (e) {
      showError(e);
    }
  };

  const chooseCalendar = async (key: string) => {
    const preset = CALENDAR_PRESETS.find((p) => p.key === key)!;
    try {
      await api.setDemoCalendar(preset.events);
      setCalendarPreset(key);
      notify(preset.events ? `Demo calendar: ${preset.label.toLowerCase()} (any day). See the Today tab.` : "Using your real calendar again.", "info");
    } catch (e) {
      showError(e);
    }
  };

  const toggleInvalidPick = async () => {
    try {
      await api.setMockOverride("pick_outfit", invalidPick ? null : "invalid");
      setInvalidPick(!invalidPick);
      notify(invalidPick ? "Stylist mock back to normal." : "The stylist will now return item IDs you don't own.", "info");
    } catch (e) {
      showError(e);
    }
  };

  return (
    <section className="space-y-4 rounded-xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
      <div>
        <p className="mb-2 text-[13px] font-medium">Weather used by the outfit planner</p>
        <div className="flex flex-wrap gap-1.5">
          {WEATHER_PRESETS.map((p) => (
            <Choice key={p.label} active={weather === p.value} onClick={() => chooseWeather(p.value)}>
              {p.label}
            </Choice>
          ))}
        </div>
      </div>
      <div className="border-t border-line pt-4">
        <p className="mb-2 text-[13px] font-medium">Calendar used by the Today tab</p>
        <div className="flex flex-wrap gap-1.5">
          {CALENDAR_PRESETS.map((p) => (
            <Choice key={p.key} active={calendarPreset === p.key} onClick={() => chooseCalendar(p.key)}>
              {p.label}
            </Choice>
          ))}
        </div>
      </div>
      {mockAi && (
        <label className="flex cursor-pointer items-start gap-2.5 border-t border-line pt-4 text-[13px] text-ink-2">
          <input type="checkbox" checked={invalidPick} onChange={toggleInvalidPick} className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]" />
          <span>
            <span className="font-medium text-ink">Make the AI stylist misbehave.</span> It returns item IDs you don't own, so you can see
            validation reject them and the rule-based fallback take over.
          </span>
        </label>
      )}
    </section>
  );
}
