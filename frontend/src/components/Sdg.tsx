import type { SdgInfo } from "@/lib/api";

/** A UN Sustainable Development Goal: its official colour is kept to a small number tile, the rest stays quiet. */
export function SdgBadge({ g, size = "md", count }: { g: SdgInfo; size?: "sm" | "md"; count?: number }) {
  const sm = size === "sm";
  return (
    <span className={`inline-flex items-center gap-2 border border-line rounded-full text-paper/85 ${sm ? "text-[12px] pl-1 pr-3 py-0.5" : "text-sm pl-1 pr-3.5 py-1"}`}
      title={`SDG ${g.number}: ${g.name}`}>
      <span className={`rounded-full grid place-items-center font-semibold text-white ${sm ? "w-5 h-5 text-[10px]" : "w-6 h-6 text-[11px]"}`} style={{ background: g.color }}>{g.number}</span>
      <span>{g.name}</span>
      {count != null && <span className="t-meta text-[11px] text-faint">{count}</span>}
    </span>
  );
}

export function SdgPicker({ all, selected, onChange }: { all: SdgInfo[]; selected: number[]; onChange: (v: number[]) => void }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
      {all.map((g) => {
        const on = selected.includes(g.number);
        return (
          <button key={g.number} type="button" aria-pressed={on}
            onClick={() => onChange(on ? selected.filter((n) => n !== g.number) : [...selected, g.number])}
            className={`flex items-center gap-2.5 text-left rounded-md p-2 pr-2.5 text-[13px] border transition ${on ? "border-paper/70 text-paper bg-paper/5" : "border-line text-muted hover:text-paper"}`}>
            <span className="w-7 h-7 shrink-0 rounded-full grid place-items-center font-semibold text-white text-[12px]" style={{ background: g.color, opacity: on ? 1 : 0.55 }}>{g.number}</span>
            <span className="leading-tight">{g.name}</span>
          </button>
        );
      })}
    </div>
  );
}
