"use client";
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { postJSON } from "@/lib/api";
import { btnDanger, btnGhost, input } from "@/components/ui";

export function savedName(): string {
  try { return localStorage.getItem("ip-name") || ""; } catch { return ""; }
}
function rememberName(n: string) {
  try { localStorage.setItem("ip-name", n); } catch {}
}

/** Confirm-and-delete for one or more photos. The deletion is recorded in the audit log with the name given. */
export default function DeletePanel({ ids, label, onDone, onCancel, compact = false }: {
  ids: number[]; label: string; onDone: (n: number) => void; onCancel?: () => void; compact?: boolean;
}) {
  const [open, setOpen] = useState(!!onCancel);
  const [name, setName] = useState(savedName);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function go() {
    if (!name.trim()) { setErr("Add your name: deletions are recorded in the audit log."); return; }
    setBusy(true); setErr("");
    try {
      rememberName(name.trim());
      const r = await postJSON<{ deleted: unknown[] }>("/api/evidence/delete", { ids, actor: name.trim(), reason: reason.trim() });
      onDone(r.deleted.length);
    } catch (x: any) { setErr(x.message); setBusy(false); }
  }

  if (!open) {
    return <button onClick={() => setOpen(true)} className={btnDanger}><Trash2 size={15} /> {label}</button>;
  }
  return (
    <div className={`border border-bad/40 bg-bad/5 rounded-xl ${compact ? "p-3" : "p-4"}`}>
      <p className="text-sm">
        <b className="text-bad">{label}?</b> The photo{ids.length === 1 ? " is" : "s are"} removed from ImpactProof, Cloudinary, search and any
        claims. A record of the deletion stays in the audit log.
      </p>
      <div className="grid sm:grid-cols-2 gap-2 mt-3">
        <input className={input} placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Your name" />
        <input className={input} placeholder="Reason (optional), e.g. test upload" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Reason" />
      </div>
      {err && <p className="text-bad text-sm mt-2">{err}</p>}
      <div className="flex flex-wrap gap-2 mt-3">
        <button onClick={go} disabled={busy} className={`${btnDanger} !bg-bad !text-white !border-bad`}>
          <Trash2 size={15} /> {busy ? "Deleting…" : `Delete ${ids.length === 1 ? "photo" : `${ids.length} photos`}`}
        </button>
        <button onClick={() => { setOpen(false); onCancel?.(); }} disabled={busy} className={btnGhost}>Cancel</button>
      </div>
    </div>
  );
}
