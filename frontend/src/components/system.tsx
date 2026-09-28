"use client";
/**
 * ImpactProof design system: the landing page's visual language, for the working app.
 * Editorial type (Instrument Serif for statements, Inter for everything functional), hairlines instead of card
 * stacks, photographs treated as evidence records, and metadata set in mono caps.
 */
import Link from "next/link";
import { EvidenceLight, STATUS_LABEL } from "@/lib/api";

const VERDICT_WORD: Record<string, string> = {
  CORROBORATED: "Corroborated", NEEDS_REVIEW: "Pending review", SUSPICIOUS: "Flagged",
  UNVERIFIABLE: "Unverifiable", REJECTED: "Rejected",
};

/** Small uppercase label with a coloured dot: the one place verdict colour appears in lists. */
export function Verdict({ status, className = "" }: { status: string; className?: string }) {
  return (
    <span className={`v-${status} inline-flex items-center gap-1.5 t-label !tracking-[.12em] whitespace-nowrap ${className}`} style={{ color: "var(--v)" }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--v)" }} />
      {VERDICT_WORD[status] || STATUS_LABEL[status] || status}
    </span>
  );
}

export function Label({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <p className={`t-label ${className}`}>{children}</p>;
}

/** A section opens with a hairline and a small label; the serif title is optional and used sparingly. */
export function SectionHeading({ label, title, children, className = "" }: {
  label: string; title?: React.ReactNode; children?: React.ReactNode; className?: string;
}) {
  return (
    <div className={`border-t border-line pt-4 mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-2 ${className}`}>
      <div>
        <p className="t-label">{label}</p>
        {title && <h2 className="t-title mt-3">{title}</h2>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-3 text-sm">{children}</div>}
    </div>
  );
}

/** Metadata as documentation: caps label over a mono value. */
export function Meta({ items, cols = 3, className = "" }: {
  items: { k: string; v: React.ReactNode }[]; cols?: 2 | 3 | 4 | 6; className?: string;
}) {
  const grid = { 2: "sm:grid-cols-2", 3: "sm:grid-cols-3", 4: "sm:grid-cols-2 lg:grid-cols-4", 6: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6" }[cols];
  return (
    <dl className={`grid grid-cols-2 ${grid} gap-x-6 gap-y-4 ${className}`}>
      {items.map((i) => (
        <div key={i.k} className="min-w-0">
          <dt className="t-label !text-[10px] !text-faint">{i.k}</dt>
          <dd className="t-meta mt-1 uppercase truncate">{i.v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A large serif number with a caps label: impact figures, not KPI tiles. */
export function Stat({ value, label, status, note }: { value: React.ReactNode; label: string; status?: string; note?: string }) {
  return (
    <div className={status ? `v-${status}` : ""}>
      <div className="t-num text-6xl md:text-7xl">{value}</div>
      <div className="mt-3 flex items-center gap-2 t-label" style={status ? { color: "var(--v)" } : undefined}>
        {status && <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--v)" }} />}
        {label}
      </div>
      {note && <p className="text-[13px] text-faint mt-1.5 leading-snug max-w-[26ch]">{note}</p>}
    </div>
  );
}

function when(iso: string | null) {
  if (!iso) return { day: "No date", time: "" };
  const d = new Date(iso);
  return {
    day: d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase(),
    time: d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
  };
}

export function recordNo(e: { id: number }) {
  return String(e.id).padStart(4, "0");
}

/** A photograph presented as a field record: number and verdict above, the picture, then where and when. */
export function PhotoRecord({ e, href, size = "md", selected, onClick }: {
  e: EvidenceLight; href?: string; size?: "sm" | "md" | "lg"; selected?: boolean; onClick?: () => void;
}) {
  const w = when(e.capture_time);
  const inner = (
    <figure className="group">
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 mb-2">
        <span className="t-meta text-[11px] text-muted whitespace-nowrap">
          {size === "sm" ? "REC." : <><span className="hidden sm:inline">FIELD RECORD /</span><span className="sm:hidden">REC.</span></>} {recordNo(e)}
        </span>
        <Verdict status={e.integrity_status} className="!text-[10px] !tracking-[.08em]" />
      </div>
      <div className={`photo aspect-[4/3] ${selected ? "outline outline-2 outline-offset-2 outline-gold" : ""}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {e.thumb_url && <img src={e.thumb_url} alt={e.activity || e.original_filename} loading="lazy" />}
      </div>
      <figcaption className="mt-2.5">
        {size !== "sm" && <p className="text-[14px] leading-snug text-paper/90 line-clamp-2">{e.activity || e.original_filename}</p>}
        <p className="t-meta text-[11px] text-faint mt-1 uppercase truncate">
          {[e.site_name || "No site", w.day, w.time, e.captured_by ? e.captured_by.name : e.capture_source === "in_app" ? "Live capture" : null].filter(Boolean).join(" · ")}
        </p>
      </figcaption>
    </figure>
  );
  if (onClick) return <button type="button" onClick={onClick} aria-pressed={selected} className="block text-left w-full">{inner}</button>;
  return href ? <Link href={href} className="block">{inner}</Link> : inner;
}

/** A contact sheet of field records. */
export function EvidenceGrid({ children, dense = false }: { children: React.ReactNode; dense?: boolean }) {
  return (
    <div className={`grid gap-x-5 gap-y-9 ${dense ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"}`}>
      {children}
    </div>
  );
}

/** One row per record: picture, what it shows, where and when, verdict. For lists of recent evidence. */
export function EvidenceRow({ e, href }: { e: EvidenceLight; href: string }) {
  const w = when(e.capture_time);
  return (
    <Link href={href} className="group grid grid-cols-[5.5rem_1fr] sm:grid-cols-[6.5rem_1fr_auto] gap-x-4 gap-y-1 items-center py-3.5 border-b border-line">
      <div className="photo aspect-[4/3] row-span-2 sm:row-span-1">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {e.thumb_url && <img src={e.thumb_url} alt="" loading="lazy" />}
      </div>
      <div className="min-w-0">
        <p className="t-meta text-[11px] text-muted">{e.code}</p>
        <p className="text-[15px] leading-snug truncate group-hover:underline underline-offset-4 decoration-paper/30">{e.activity || e.original_filename}</p>
        <p className="t-meta text-[11px] text-faint uppercase truncate mt-0.5">{[e.site_name || "No site", w.day, w.time].filter(Boolean).join(" · ")}</p>
      </div>
      <Verdict status={e.integrity_status} className="sm:justify-self-end" />
    </Link>
  );
}

/** Vertical hairline timeline. */
export function Timeline({ items }: { items: { key: string | number; time: string; text: React.ReactNode; by?: string; tone?: string }[] }) {
  return (
    <ol className="relative border-l border-line ml-1">
      {items.map((i) => (
        <li key={i.key} className="relative pl-5 pb-5 last:pb-0">
          <span className={`absolute -left-[4px] top-[7px] w-[7px] h-[7px] rounded-full ${i.tone || "bg-faint"}`} />
          <p className="t-meta text-[11px] text-faint uppercase">{i.time}{i.by ? ` · ${i.by}` : ""}</p>
          <p className="text-[14px] leading-snug mt-0.5 text-paper/90">{i.text}</p>
        </li>
      ))}
    </ol>
  );
}

/** The chain every claim follows. Each step shows its state in words. */
export function EvidenceChain({ steps }: { steps: { k: string; v: React.ReactNode; state?: "done" | "warn" | "bad" | "none" }[] }) {
  const tone = { done: "text-ok", warn: "text-review", bad: "text-bad", none: "text-faint" };
  return (
    <ol className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 border-y border-line">
      {steps.map((s, i) => (
        <li key={s.k} className="relative py-4 pr-4 lg:pl-4 lg:first:pl-0 border-line [&:not(:first-child)]:lg:border-l">
          <p className="t-label !text-[10px] flex items-center gap-2">
            <span className="t-meta text-faint">{String(i + 1).padStart(2, "0")}</span> {s.k}
          </p>
          <p className={`text-[14px] mt-2 leading-snug ${tone[s.state || "none"]}`}>{s.v}</p>
        </li>
      ))}
    </ol>
  );
}
