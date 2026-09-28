"use client";
import { useState } from "react";
import { EvidenceFull, api } from "@/lib/api";

const STAGES: Record<string, string> = { before: "Before the work", during: "During the work", after: "After the work", other: "Other" };
const CATS: Record<string, string> = {
  waste: "Waste and litter", planting: "Planting and greenery", water: "Water and sanitation",
  construction: "Construction and repair", education: "Education and training", health: "Health and care",
  community: "People and community", site: "Site overview", other: "Other",
};
const SOURCE: Record<string, string> = { ai: "AI", rules: "rules", person: "set by a person" };

export default function ClassificationBox({ e, onDone }: { e: EvidenceFull; onDone: (e: EvidenceFull) => void }) {
  const [busy, setBusy] = useState(false);
  async function set(field: "stage" | "category", value: string) {
    setBusy(true);
    let reviewer = "";
    try { reviewer = localStorage.getItem("ip.reviewer") || ""; } catch {}
    try {
      onDone(await api<EvidenceFull>(`/api/evidence/${e.id}/classification`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [field]: value, reviewer }),
      }));
    } finally { setBusy(false); }
  }
  const sel = "w-full bg-ink border border-line rounded-lg px-2.5 py-2 text-sm";
  return (
    <div className="border-t border-line pt-5">
      <p className="t-label mb-2">Gallery placement</p>
      <p className="text-sm text-muted mt-1">Where this photo appears in the gallery. Correct it if the AI got it wrong.</p>
      <div className="grid grid-cols-2 gap-3 mt-4">
        <label className="text-sm">
          <span className="block mb-1">Stage <span className="text-faint">({SOURCE[e.stage_source]})</span></span>
          <select disabled={busy} className={sel} value={e.stage} onChange={(x) => set("stage", x.target.value)}>
            {Object.entries(STAGES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="block mb-1">Activity <span className="text-faint">({SOURCE[e.category_source]})</span></span>
          <select disabled={busy} className={sel} value={e.category} onChange={(x) => set("category", x.target.value)}>
            {Object.entries(CATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>
    </div>
  );
}
