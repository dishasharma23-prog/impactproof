"use client";
import Link from "next/link";
import { STATUS_LABEL, Signal } from "@/lib/api";

/* Buttons follow the landing page: a warm-white pill for the main action, an outline pill for the rest.
   Teal (btnAccent) is kept for verification actions such as approving evidence. */
export const btn =
  "inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-medium rounded-full bg-paper text-ink hover:opacity-90 disabled:opacity-50 disabled:cursor-progress transition-opacity";
export const btnAccent =
  "inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-medium rounded-full bg-gold text-ink hover:bg-gold-hover disabled:opacity-50 transition-colors";
export const btnGhost =
  "inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-medium rounded-full border border-paper/25 text-paper hover:border-paper/50 hover:bg-paper/5 disabled:opacity-50 transition-colors";
export const btnDanger =
  "inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-medium rounded-full border border-bad/60 text-bad hover:bg-bad/10 disabled:opacity-50 transition-colors";
export const input =
  "w-full bg-transparent border border-line rounded-md px-3 py-2.5 text-paper placeholder:text-faint focus:border-paper/60 focus:outline-none";
export const label = "block t-label !text-paper/80 mb-2";

export function StatusTag({ status, className = "" }: { status: string; className?: string }) {
  return (
    <span className={`v-${status} inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[.12em] whitespace-nowrap ${className}`} style={{ color: "var(--v)" }}>
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "var(--v)" }} />
      {STATUS_LABEL[status] || status}
    </span>
  );
}

export function PageHeader({ title, lead, label, children }: { title: string; lead?: React.ReactNode; label?: string; children?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-6 pb-8 mb-10 border-b border-line">
      <div className="max-w-3xl">
        {label && <p className="t-label mb-4">{label}</p>}
        <h1 className="t-display">{title}</h1>
        {lead && <p className="text-muted mt-4 text-[15px] leading-relaxed max-w-[64ch]">{lead}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-3">{children}</div>}
    </header>
  );
}

export function Empty({ title, children, action }: { title: string; children?: React.ReactNode; action?: { href: string; label: string } }) {
  return (
    <div className="border-y border-line px-6 py-16 text-center">
      <h2 className="t-title">{title}</h2>
      {children && <p className="text-muted mt-2 max-w-[56ch] mx-auto">{children}</p>}
      {action && (
        <Link href={action.href} className={`${btn} mt-6`}>
          {action.label}
        </Link>
      )}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="border-l-4 border-bad bg-bad/10 px-4 py-3 rounded-r text-sm">
      <b className="text-bad">Something went wrong.</b> <span className="text-paper">{message}</span>
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="text-muted py-16 text-center animate-pulse">{label}</p>;
}

const MARK: Record<string, string> = { pass: "✓", warn: "!", fail: "✕", unavailable: "–" };
const MARK_COLOR: Record<string, string> = { pass: "text-ok", warn: "text-review", fail: "text-bad", unavailable: "text-faint" };
const MARK_WORD: Record<string, string> = { pass: "Passed", warn: "Check", fail: "Failed", unavailable: "No data" };

export function CheckMark({ status }: { status: string }) {
  return (
    <span aria-label={MARK_WORD[status] || status}
      className={`shrink-0 w-5 text-center font-mono text-[15px] font-semibold leading-6 ${MARK_COLOR[status]}`}>
      {MARK[status]}
    </span>
  );
}

/** Verification documented line by line: what was checked, the result, and why. */
export function CheckLedger({ signals, compact = false }: { signals: Signal[]; compact?: boolean }) {
  return (
    <ul className="border-t border-line">
      {signals.map((s) => (
        <li key={s.key} className={`grid grid-cols-[1.25rem_1fr] gap-x-3 border-b border-line ${compact ? "py-2.5" : "py-3.5"}`}>
          <CheckMark status={s.status} />
          <div className="min-w-0">
            <div className="flex items-baseline justify-between gap-3">
              <span className={`font-medium ${s.status === "unavailable" ? "text-muted" : ""}`}>{s.label}</span>
              <span className={`t-label !tracking-[.12em] !text-[10px] ${MARK_COLOR[s.status]}`}>{MARK_WORD[s.status]}</span>
            </div>
            <div className="text-sm text-muted leading-relaxed mt-0.5">{s.reason}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Toast({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div role="status" className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[3000] bg-paper text-ink px-5 py-2.5 rounded-full text-sm font-medium">
      {message}
    </div>
  );
}
