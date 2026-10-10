import { useState } from "react";
import type { Category, ItemEdit, Owner } from "../api/types";
import { CATEGORY_LABELS, FORMALITY_LABELS, OWNER_LABELS, WARMTH_LABELS } from "../lib/format";
import { ColourDots, Field, ScalePicker, inputClass } from "./ui";

const CATEGORIES: Category[] = ["top", "bottom", "one_piece", "outerwear", "shoes", "accessory", "sportswear"];
const OWNERS: Owner[] = ["me", "child", "other", "unknown"];

const PleaseFill = () => <span className="normal-case tracking-normal text-amber-600">please fill in</span>;

/**
 * Edits the labels of one item. `missing` lists fields the AI left unknown: they get an
 * amber "please fill in" marker. `uncertain` softly highlights everything the AI guessed.
 */
export default function ItemEditor({
  draft,
  onChange,
  missing = [],
  uncertain = false,
  showOwner = true,
}: {
  draft: ItemEdit;
  onChange: (patch: ItemEdit) => void;
  missing?: string[];
  uncertain?: boolean;
  showOwner?: boolean;
}) {
  const [colourText, setColourText] = useState((draft.colours ?? []).filter((c) => c !== "unknown").join(", "));
  const needs = (field: string) => missing.includes(field);
  const aiRing = uncertain ? "bg-amber-50/60" : "";

  const setColours = (text: string) => {
    setColourText(text);
    const colours = text
      .split(",")
      .map((c) => c.trim().toLowerCase())
      .filter(Boolean);
    onChange({ colours: colours.length ? colours : ["unknown"] });
  };

  return (
    <div className="space-y-4">
      <Field label="Name">
        <input className={`${inputClass} ${aiRing}`} value={draft.name ?? ""} onChange={(e) => onChange({ name: e.target.value })} />
      </Field>

      <Field label="Category" hint={needs("category") ? <PleaseFill /> : undefined}>
        <div className={`flex flex-wrap gap-1.5 rounded-xl ${needs("category") ? "p-1 ring-2 ring-amber-300" : ""}`}>
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => onChange({ category: c })}
              className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                draft.category === c ? "bg-indigo-600 text-white ring-indigo-600" : "bg-white text-slate-600 ring-slate-200"
              }`}
            >
              {CATEGORY_LABELS[c]}
            </button>
          ))}
        </div>
      </Field>

      <Field label="Colours" hint={needs("colours") ? <PleaseFill /> : <ColourDots colours={draft.colours ?? ["unknown"]} />}>
        <input
          className={`${inputClass} ${aiRing} ${needs("colours") ? "ring-2 ring-amber-300" : ""}`}
          placeholder="e.g. navy, white"
          value={colourText}
          onChange={(e) => setColours(e.target.value)}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Formality" hint={needs("formality") ? <PleaseFill /> : undefined}>
          <ScalePicker
            value={draft.formality ?? null}
            onChange={(v) => onChange({ formality: v })}
            labels={FORMALITY_LABELS}
            highlight={needs("formality")}
          />
        </Field>
        <Field label="Warmth" hint={needs("warmth") ? <PleaseFill /> : undefined}>
          <ScalePicker value={draft.warmth ?? null} onChange={(v) => onChange({ warmth: v })} labels={WARMTH_LABELS} highlight={needs("warmth")} />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Waterproof" hint={needs("waterproof") ? <PleaseFill /> : undefined}>
          <div className={`grid grid-cols-3 gap-1 rounded-xl ${needs("waterproof") ? "ring-2 ring-amber-300 ring-offset-2" : ""}`}>
            {[
              { v: true, l: "Yes" },
              { v: false, l: "No" },
              { v: null, l: "?" },
            ].map(({ v, l }) => (
              <button
                key={l}
                type="button"
                onClick={() => onChange({ waterproof: v })}
                className={`rounded-lg py-1.5 text-sm font-semibold ring-1 ${
                  (draft.waterproof ?? null) === v ? "bg-indigo-600 text-white ring-indigo-600" : "bg-white text-slate-600 ring-slate-200"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Material">
          <input
            className={`${inputClass} ${aiRing}`}
            placeholder="e.g. wool, suede"
            value={draft.material ?? ""}
            onChange={(e) => onChange({ material: e.target.value || null })}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Size">
          <input className={inputClass} placeholder="e.g. M, 32" value={draft.size ?? ""} onChange={(e) => onChange({ size: e.target.value || null })} />
        </Field>
        {showOwner && (
          <Field label="Whose is it?">
            <select className={inputClass} value={draft.owner ?? "me"} onChange={(e) => onChange({ owner: e.target.value as Owner })}>
              {OWNERS.map((o) => (
                <option key={o} value={o}>
                  {OWNER_LABELS[o]}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>
    </div>
  );
}
