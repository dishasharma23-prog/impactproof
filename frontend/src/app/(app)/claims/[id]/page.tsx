"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EvidenceChain, EvidenceGrid, PhotoRecord, recordNo, SectionHeading } from "@/components/system";
import { btn, btnGhost, ErrorBox, Loading, StatusTag, Toast } from "@/components/ui";
import { api, EvidenceLight, fmtDate, postJSON, Support, SUPPORT_COLOR } from "@/lib/api";

interface ClaimDetail {
  id: number; text: string; project_id: number; created_at: string; support: Support; verify_url: string;
  evidence: (EvidenceLight & { flag_reasons: string[] })[];
}

export default function ClaimPage() {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState("");
  const [picking, setPicking] = useState(false);
  const [toast, setToast] = useState("");
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 3000); };

  const load = useCallback(() => api<ClaimDetail>(`/api/claims/${id}`).then(setClaim).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorBox message={error} />;
  if (!claim) return <Loading />;

  async function unlink(eid: number) {
    await api(`/api/claims/${id}/evidence/${eid}`, { method: "DELETE" });
    await load(); flash("Removed from this claim");
  }

  const counts = claim.support.counts || {};
  const flagged = (counts.SUSPICIOUS || 0) + (counts.REJECTED || 0);
  const onCloud = claim.evidence.filter((e) => e.cloudinary_public_id).length;
  const rank: Record<string, number> = { CORROBORATED: 0, NEEDS_REVIEW: 1, UNVERIFIABLE: 2, SUSPICIOUS: 3, REJECTED: 4 };
  const ordered = [...claim.evidence].sort((a, b) => (rank[a.integrity_status] ?? 5) - (rank[b.integrity_status] ?? 5));
  const supportTone = { SUPPORTED: "done", PARTIAL: "warn", CONTESTED: "bad", UNSUPPORTED: "none" }[claim.support.state] as "done" | "warn" | "bad" | "none";

  return (
    <div>
      <Toast message={toast} />
      <header className="pb-2">
        <p className="t-label"><Link href="/claims" className="hover:text-paper">Claim</Link> / {recordNo(claim)} · dossier</p>
        <h1 className="t-display mt-5 max-w-5xl">&ldquo;{claim.text.replace(/\.$/, "")}.&rdquo;</h1>
        <p className="t-meta text-[12px] text-faint uppercase mt-5">Recorded {fmtDate(claim.created_at)}</p>
      </header>

      <section className="mt-10">
        <EvidenceChain steps={[
          { k: "Claim", v: "Stated by the organisation", state: "done" },
          { k: "Evidence", v: claim.evidence.length ? `${claim.evidence.length} field record${claim.evidence.length === 1 ? "" : "s"} linked` : "Nothing linked yet", state: claim.evidence.length ? "done" : "none" },
          { k: "Verification", v: `${claim.support.corroborated} corroborated${flagged ? `, ${flagged} flagged` : ""}`, state: flagged ? "bad" : claim.support.corroborated ? "done" : "none" },
          { k: "Provenance", v: claim.evidence.length ? `Fingerprinted at intake${onCloud ? `; ${onCloud} on Cloudinary` : ""}` : "—", state: claim.evidence.length ? "done" : "none" },
          { k: "Impact", v: claim.support.label, state: supportTone },
        ]} />
        <div className="flex flex-wrap items-end justify-between gap-6 mt-8">
          <p className="max-w-[62ch] text-[15px] text-paper/85 leading-relaxed">
            <span className="t-title block mb-2" style={{ color: SUPPORT_COLOR[claim.support.state] }}>{claim.support.label}</span>
            {claim.support.reason}
          </p>
          <div className="flex flex-wrap gap-3">
            <button onClick={() => setPicking(true)} className={btnGhost}>Link evidence</button>
            <Link href={`/claims/${claim.id}/report`} className={btn}>Impact brief &amp; QR</Link>
          </div>
        </div>
      </section>

      <section className="mt-16">
        <SectionHeading label="Field evidence">
          <span className="t-meta text-[11px] text-faint uppercase">Corroborated first</span>
        </SectionHeading>
        {claim.evidence.length === 0 ? (
          <p className="text-muted">No evidence linked yet. Link photos that show this claim happened.</p>
        ) : (
          <EvidenceGrid>
            {ordered.map((e) => (
              <div key={e.id}>
                <PhotoRecord e={e} href={`/evidence/${e.id}`} />
                {e.flag_reasons.length > 0 && (
                  <ul className={`v-${e.integrity_status} mt-2 text-[13px] leading-snug space-y-1`}>
                    {e.flag_reasons.map((r, i) => <li key={i} style={{ color: "var(--v)" }}>{r}</li>)}
                  </ul>
                )}
                <button onClick={() => unlink(e.id)} className="mt-2 t-label !text-[10px] hover:!text-bad">Remove from claim</button>
              </div>
            ))}
          </EvidenceGrid>
        )}
      </section>

      {picking && <Picker claim={claim} onClose={() => setPicking(false)} onDone={async (n) => { setPicking(false); await load(); flash(`Linked ${n} photo${n === 1 ? "" : "s"}`); }} />}
    </div>
  );
}

function Picker({ claim, onClose, onDone }: { claim: ClaimDetail; onClose: () => void; onDone: (n: number) => void }) {
  const [all, setAll] = useState<EvidenceLight[]>([]);
  const [suggested, setSuggested] = useState<(EvidenceLight & { similarity: number })[]>([]);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<EvidenceLight[]>(`/api/evidence?project_id=${claim.project_id}`).then(setAll).catch(() => {});
    api<any[]>(`/api/claims/${claim.id}/candidates`).then(setSuggested).catch(() => {});
  }, [claim]);
  const linked = new Set(claim.evidence.map((e) => e.id));
  const sugIds = new Set(suggested.map((s) => s.id));
  const [onlyGood, setOnlyGood] = useState(true);
  const rank: Record<string, number> = { CORROBORATED: 0, NEEDS_REVIEW: 1, UNVERIFIABLE: 2, SUSPICIOUS: 3, REJECTED: 4 };
  const rest = all
    .filter((e) => !linked.has(e.id) && !sugIds.has(e.id))
    .filter((e) => !onlyGood || e.integrity_status === "CORROBORATED")
    .sort((a, b) => (rank[a.integrity_status ?? ""] ?? 5) - (rank[b.integrity_status ?? ""] ?? 5));
  const toggle = (id: number) => setSel((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  async function attach() {
    setBusy(true);
    for (const eid of sel) await postJSON(`/api/claims/${claim.id}/evidence`, { evidence_id: eid }).catch(() => {});
    onDone(sel.size);
  }

  const tile = (e: EvidenceLight, extra?: string) => (
    <button key={e.id} onClick={() => toggle(e.id)} aria-pressed={sel.has(e.id)}
      className={`text-left p-2 rounded-sm border-2 transition-colors ${sel.has(e.id) ? "border-gold bg-raised" : "border-transparent hover:border-line"}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={e.thumb_url || ""} alt="" className="w-full aspect-[4/3] object-cover rounded-sm" />
      <span className="flex justify-between items-center mt-1.5 gap-2"><span className="font-mono text-xs">{e.code}</span><StatusTag status={e.integrity_status} className="!text-[11px]" /></span>
      {extra && <span className="block text-[11px] text-teal mt-0.5">{extra}</span>}
    </button>
  );

  return (
    <div className="fixed inset-0 z-[2000] bg-black/80 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Link evidence">
      <div className="border border-line rounded-md w-full max-w-5xl h-[85vh] flex flex-col">
        <div className="flex justify-between items-center p-5 border-b border-line">
          <h2 className="t-title">Link evidence</h2>
          <button onClick={onClose} className="text-sm text-muted hover:text-paper">Cancel</button>
        </div>
        <div className="flex-1 overflow-y-auto scroll-thin p-5 space-y-8">
          {suggested.filter((s) => !linked.has(s.id)).length > 0 && (
            <section>
              <h3 className="font-semibold">Suggested by meaning</h3>
              <p className="text-xs text-muted mb-3">Found by semantic search on the claim&apos;s wording (Qdrant).</p>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {suggested.filter((s) => !linked.has(s.id)).map((s) => tile(s, `${Math.round(s.similarity * 100)}% match`))}
              </div>
            </section>
          )}
          <section>
            <div className="flex justify-between items-center mb-3 gap-4">
              <h3 className="font-semibold">{onlyGood ? "Corroborated evidence in this project" : "All evidence in this project"}</h3>
              <label className="text-sm text-muted flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={onlyGood} onChange={(ev) => setOnlyGood(ev.target.checked)} /> Corroborated only
              </label>
            </div>
            {rest.length === 0 ? <p className="text-muted text-sm">{onlyGood ? "No other corroborated photos. Untick \"Corroborated only\" to see the rest." : "Nothing else to link."}</p> : (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">{rest.map((e) => tile(e))}</div>
            )}
          </section>
        </div>
        <div className="flex justify-between items-center p-5 border-t border-line">
          <span className="text-sm text-muted">{sel.size} selected. Only corroborated photos will count as support.</span>
          <button onClick={attach} disabled={!sel.size || busy} className={btn}>{busy ? "Linking…" : "Link selected"}</button>
        </div>
      </div>
    </div>
  );
}
