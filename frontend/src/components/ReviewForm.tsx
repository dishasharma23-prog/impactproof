"use client";
import { useEffect, useState } from "react";
import { btnAccent as btn, btnDanger, btnGhost, input } from "./ui";
import { EvidenceFull, postJSON } from "@/lib/api";

export default function ReviewForm({ evidence, onDone, compact = false }: {
  evidence: EvidenceFull | { id: number; integrity_status: string; review_status: string | null };
  onDone: (e: EvidenceFull) => void;
  compact?: boolean;
}) {
  const [reason, setReason] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    try { setReviewer(localStorage.getItem("ip.reviewer") || ""); } catch {}
  }, []);

  const status = "integrity" in evidence && evidence.integrity ? evidence.integrity.status : (evidence as any).integrity_status;
  const decided = !!evidence.review_status;

  async function decide(decision: "APPROVED" | "REJECTED" | "REOPENED") {
    setBusy(decision); setErr("");
    try {
      try { localStorage.setItem("ip.reviewer", reviewer); } catch {}
      const out = await postJSON<EvidenceFull>(`/api/evidence/${evidence.id}/review`, { decision, reason, reviewer });
      setReason("");
      onDone(out);
    } catch (x: any) {
      setErr(x.message);
    }
    setBusy("");
  }

  return (
    <div className={compact ? "" : "border-t border-line pt-5"}>
      {!compact && <p className="t-label mb-2">{decided ? "Reviewer decision" : "Review"}</p>}
      {!compact && (
        <p className="text-sm text-muted mt-1">
          {decided
            ? `This evidence was ${evidence.review_status === "APPROVED" ? "approved" : "rejected"} by a reviewer. Reopen it to send it back to the checks' verdict.`
            : status === "CORROBORATED"
              ? "All checks agree. You can still reject it if you know something the checks don't."
              : "Decide after looking at the reasons. Every decision is recorded with your name and reason."}
        </p>
      )}
      <div className="grid sm:grid-cols-[1fr_180px] gap-3 mt-4">
        <textarea className={`${input} min-h-[70px]`} placeholder={decided ? "Why reopen it?" : "Reason, e.g. Confirmed with the site volunteer by phone"}
          value={reason} onChange={(x) => setReason(x.target.value)} aria-label="Reason for the decision" />
        <input className={input} placeholder="Your name" value={reviewer} onChange={(x) => setReviewer(x.target.value)} aria-label="Reviewer name" />
      </div>
      <div className="flex flex-wrap gap-3 mt-3">
        {decided ? (
          <button className={btnGhost} disabled={!!busy} onClick={() => decide("REOPENED")}>{busy ? "Saving…" : "Reopen"}</button>
        ) : (
          <>
            <button className={btn} disabled={!!busy} onClick={() => decide("APPROVED")}>{busy === "APPROVED" ? "Saving…" : "Approve"}</button>
            <button className={btnDanger} disabled={!!busy} onClick={() => decide("REJECTED")}>{busy === "REJECTED" ? "Saving…" : "Reject"}</button>
          </>
        )}
      </div>
      {err && <p className="text-bad text-sm mt-2">{err}</p>}
    </div>
  );
}
