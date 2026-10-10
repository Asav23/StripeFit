import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../context";
import { Choice } from "./ui";

const WEATHER_PRESETS: { value: string | null; label: string }[] = [
  { value: null, label: "Real forecast" },
  { value: "rain", label: "Rain, 9°C" },
  { value: "cold", label: "Cold, 2°C" },
  { value: "hot", label: "Hot, 25°C" },
];

/** Switches for showing the rules and fallbacks live, whatever today's weather or AI is doing. */
export default function DemoControls({ mockAi }: { mockAi: boolean }) {
  const { notify, showError } = useToast();
  const [weather, setWeather] = useState<string | null>(null);
  const [invalidPick, setInvalidPick] = useState(false);

  useEffect(() => {
    api.weatherOverride().then((w) => setWeather(w.preset)).catch(() => undefined);
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
