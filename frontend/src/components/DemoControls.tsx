import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../context";
import { Chip } from "./ui";

const WEATHER_PRESETS: { value: string | null; label: string }[] = [
  { value: null, label: "Real forecast" },
  { value: "rain", label: "🌧️ Rain 9°C" },
  { value: "cold", label: "🥶 Cold 2°C" },
  { value: "hot", label: "☀️ Hot 25°C" },
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
    <div className="space-y-3 rounded-2xl bg-white p-3 ring-1 ring-slate-200">
      <p className="text-xs font-semibold text-slate-700">Demo controls</p>
      <div>
        <p className="mb-1.5 text-xs text-slate-500">Weather used by the outfit planner</p>
        <div className="flex flex-wrap gap-1.5">
          {WEATHER_PRESETS.map((p) => (
            <Chip key={p.label} active={weather === p.value} onClick={() => chooseWeather(p.value)} className="text-xs">
              {p.label}
            </Chip>
          ))}
        </div>
      </div>
      {mockAi && (
        <label className="flex items-center gap-2 text-xs text-slate-600">
          <input type="checkbox" checked={invalidPick} onChange={toggleInvalidPick} className="h-4 w-4 accent-indigo-600" />
          Make the AI stylist return invalid item IDs (shows validation + rule-based fallback)
        </label>
      )}
    </div>
  );
}
