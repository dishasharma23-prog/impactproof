"use client";
import { useState } from "react";

export default function BeforeAfter({ before, after, beforeLabel, afterLabel, className = "" }: {
  before: string; after: string; beforeLabel: string; afterLabel: string; className?: string;
}) {
  const [pos, setPos] = useState(50);
  return (
    <div className={`ba rounded-lg aspect-[4/3] ${className}`} style={{ ["--pos" as any]: `${pos}%` }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={after} alt={`After: ${afterLabel}`} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={before} alt={`Before: ${beforeLabel}`} className="ba-before" />
      <div className="ba-handle" />
      <span className="absolute bottom-2.5 left-2.5 bg-ink/85 text-xs px-2 py-1 rounded-sm pointer-events-none">Before, {beforeLabel}</span>
      <span className="absolute bottom-2.5 right-2.5 bg-ink/85 text-xs px-2 py-1 rounded-sm pointer-events-none">After, {afterLabel}</span>
      <input type="range" min={0} max={100} value={pos} onChange={(ev) => setPos(Number(ev.target.value))}
        aria-label="Drag to compare before and after" />
    </div>
  );
}
