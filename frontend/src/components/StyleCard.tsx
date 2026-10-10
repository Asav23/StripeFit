import { Palette } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { StyleProfile } from "../api/types";
import { useToast } from "../context";
import { colourCss } from "../lib/format";
import { Button } from "./ui";

const PALETTE = ["black", "white", "grey", "navy", "blue", "light blue", "denim", "green", "olive", "khaki", "beige", "camel",
  "brown", "burgundy", "red", "pink", "purple", "yellow", "mustard", "orange"];

type Pref = "love" | "avoid" | null;

/** "My style": colours you love or avoid, a note, and what StripeFit has learned from your thumbs and swaps. */
export default function StyleCard() {
  const { notify, showError } = useToast();
  const [profile, setProfile] = useState<StyleProfile | null>(null);
  const [prefs, setPrefs] = useState<Record<string, Pref>>({});
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = () =>
    api
      .styleProfile()
      .then((p) => {
        setProfile(p);
        const next: Record<string, Pref> = {};
        p.stated.favourite_colours.forEach((c) => (next[c] = "love"));
        p.stated.avoid_colours.forEach((c) => (next[c] = "avoid"));
        setPrefs(next);
        setNotes(p.stated.style_notes ?? "");
        setDirty(false);
      })
      .catch(() => undefined);

  useEffect(() => {
    void load();
  }, []);

  const cycle = (colour: string) => {
    setPrefs((p) => ({ ...p, [colour]: p[colour] === null || p[colour] === undefined ? "love" : p[colour] === "love" ? "avoid" : null }));
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.saveStylePreferences({
        favourite_colours: Object.keys(prefs).filter((c) => prefs[c] === "love"),
        avoid_colours: Object.keys(prefs).filter((c) => prefs[c] === "avoid"),
        style_notes: notes.trim() || null,
      });
      notify("Saved. Your next outfits will lean this way.", "success");
      await load();
    } catch (e) {
      showError(e);
    } finally {
      setSaving(false);
    }
  };

  const learned = profile?.learned;
  const learnedBits = [
    learned?.liked_colours.length ? `you like ${learned.liked_colours.join(", ")}` : null,
    learned?.disliked_colours.length ? `you skip ${learned.disliked_colours.join(", ")}` : null,
    learned?.lean_for_this_occasion ? `you dress ${learned.lean_for_this_occasion} for casual days` : null,
  ].filter(Boolean);

  return (
    <section className="rounded-xl border border-line bg-card p-4 shadow-[var(--shadow-card)]" aria-labelledby="style-title">
      <h2 id="style-title" className="mb-1 flex items-center gap-2 text-[14px] font-semibold">
        <Palette className="h-4 w-4 text-accent" /> My style
      </h2>
      <p className="mb-3 text-[12.5px] text-ink-2">Tap a colour once to love it, twice to avoid it.</p>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Colour preferences">
        {PALETTE.map((c) => {
          const state = prefs[c] ?? null;
          return (
            <button
              key={c}
              type="button"
              onClick={() => cycle(c)}
              aria-label={`${c}: ${state === "love" ? "loved" : state === "avoid" ? "avoided" : "no preference"}`}
              title={c}
              className={`relative h-7 w-7 rounded-full border transition ${
                state === "love" ? "ring-2 ring-accent ring-offset-2" : state === "avoid" ? "opacity-35" : "border-black/15"
              }`}
              style={{ backgroundColor: colourCss(c) ?? undefined }}
            >
              {state === "avoid" && <span className="absolute left-1/2 top-1/2 h-[2px] w-8 -translate-x-1/2 -translate-y-1/2 rotate-45 bg-danger" />}
            </button>
          );
        })}
      </div>
      <label className="mt-3 block">
        <span className="sr-only">Style notes</span>
        <input
          className="field h-9 text-[13px]"
          maxLength={300}
          placeholder="Anything else? e.g. I prefer relaxed fits"
          value={notes}
          onChange={(e) => {
            setNotes(e.target.value);
            setDirty(true);
          }}
        />
      </label>
      {dirty && (
        <Button size="sm" className="mt-3 w-full" onClick={save} loading={saving}>
          Save my style
        </Button>
      )}
      <p className="mt-3 text-[11.5px] leading-snug text-muted">
        {profile && profile.signals > 0
          ? `Learned from ${profile.signals} item${profile.signals === 1 ? "" : "s"} you rated, swapped or wore${learnedBits.length ? `: ${learnedBits.join("; ")}` : ""}.`
          : "Thumbs, swaps and “Wear this” teach StripeFit your taste over time."}
      </p>
    </section>
  );
}
