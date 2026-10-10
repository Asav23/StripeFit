import { useId, useState } from "react";
import type { Category, ItemEdit, Owner } from "../api/types";
import { CATEGORY_LABELS, FORMALITY_LABELS, OWNER_LABELS, WARMTH_LABELS } from "../lib/format";
import { Choice, ColourDots, Field, NeedsInput, ScalePicker } from "./ui";

const CATEGORIES: Category[] = ["top", "bottom", "one_piece", "outerwear", "shoes", "accessory", "sportswear"];
const OWNERS: Owner[] = ["me", "child", "other", "unknown"];

/**
 * Edits the labels of one item. `missing` lists fields the AI left unknown: they're marked
 * "please fill in". `uncertain` tints the fields the AI guessed so the user double-checks them.
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
  const id = useId();
  const [colourText, setColourText] = useState((draft.colours ?? []).filter((c) => c !== "unknown").join(", "));
  const needs = (field: string) => missing.includes(field);
  const guessed = uncertain ? "bg-warn-soft/50" : "";

  const setColours = (text: string) => {
    setColourText(text);
    const colours = text
      .split(",")
      .map((c) => c.trim().toLowerCase())
      .filter(Boolean);
    onChange({ colours: colours.length ? colours : ["unknown"] });
  };

  return (
    <div className="space-y-5">
      <Field label="Name" htmlFor={`${id}-name`}>
        <input id={`${id}-name`} className={`field ${guessed}`} value={draft.name ?? ""} onChange={(e) => onChange({ name: e.target.value })} />
      </Field>

      <Field label="Category" hint={needs("category") ? <NeedsInput /> : undefined}>
        <div className={`flex flex-wrap gap-1.5 ${needs("category") ? "rounded-md p-1 ring-2 ring-warn/30" : ""}`}>
          {CATEGORIES.map((c) => (
            <Choice key={c} active={draft.category === c} onClick={() => onChange({ category: c })}>
              {CATEGORY_LABELS[c]}
            </Choice>
          ))}
        </div>
      </Field>

      <Field
        label="Colours"
        htmlFor={`${id}-colours`}
        hint={needs("colours") ? <NeedsInput /> : <ColourDots colours={draft.colours ?? ["unknown"]} />}
      >
        <input
          id={`${id}-colours`}
          className={`field ${guessed} ${needs("colours") ? "border-warn ring-2 ring-warn/20" : ""}`}
          placeholder="e.g. navy, white"
          value={colourText}
          onChange={(e) => setColours(e.target.value)}
        />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Formality" hint={needs("formality") ? <NeedsInput /> : undefined}>
          <ScalePicker
            name="Formality"
            value={draft.formality ?? null}
            onChange={(v) => onChange({ formality: v })}
            labels={FORMALITY_LABELS}
            highlight={needs("formality")}
          />
        </Field>
        <Field label="Warmth" hint={needs("warmth") ? <NeedsInput /> : undefined}>
          <ScalePicker
            name="Warmth"
            value={draft.warmth ?? null}
            onChange={(v) => onChange({ warmth: v })}
            labels={WARMTH_LABELS}
            highlight={needs("warmth")}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Waterproof" hint={needs("waterproof") ? <NeedsInput /> : undefined}>
          <div
            role="radiogroup"
            aria-label="Waterproof"
            className={`grid grid-cols-3 overflow-hidden rounded-md border ${needs("waterproof") ? "border-warn ring-2 ring-warn/20" : "border-line-strong"}`}
          >
            {[
              { v: true, l: "Yes" },
              { v: false, l: "No" },
              { v: null, l: "Unsure" },
            ].map(({ v, l }) => (
              <button
                key={l}
                type="button"
                role="radio"
                aria-checked={(draft.waterproof ?? null) === v}
                onClick={() => onChange({ waterproof: v })}
                className={`h-9 border-l border-line text-[13px] first:border-l-0 ${
                  (draft.waterproof ?? null) === v ? "bg-ink text-paper" : "bg-card text-ink-2 hover:bg-sunk"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Material" htmlFor={`${id}-material`}>
          <input
            id={`${id}-material`}
            className={`field ${guessed}`}
            placeholder="e.g. wool"
            value={draft.material ?? ""}
            onChange={(e) => onChange({ material: e.target.value || null })}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Size" htmlFor={`${id}-size`}>
          <input
            id={`${id}-size`}
            className="field"
            placeholder="e.g. M, 32"
            value={draft.size ?? ""}
            onChange={(e) => onChange({ size: e.target.value || null })}
          />
        </Field>
        {showOwner && (
          <Field label="Whose is it?" htmlFor={`${id}-owner`}>
            <select id={`${id}-owner`} className="field" value={draft.owner ?? "me"} onChange={(e) => onChange({ owner: e.target.value as Owner })}>
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
