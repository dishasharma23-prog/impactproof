"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import ReviewForm from "@/components/ReviewForm";
import { CheckLedger, Empty, ErrorBox, Loading, PageHeader, StatusTag } from "@/components/ui";
import { api, AuditEvent, EvidenceFull, EvidenceLight, fmtDate, fmtUtc, Signal, STATUS_HELP } from "@/lib/api";
import { useProject } from "@/lib/project";

const RANK: Record<string, number> = { fail: 0, warn: 1, pass: 2, unavailable: 3 };

export default function ReviewPage() {
  const { project } = useProject();
  const [queue, setQueue] = useState<EvidenceLight[] | null>(null);
  const [selected, setSelected] = useState<EvidenceFull | null>(null);
  const [decisions, setDecisions] = useState<any[]>([]);
  const [activity, setActivity] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async (keep?: number) => {
    if (!project) return;
    try {
      const [q, d, a] = await Promise.all([
        api<EvidenceLight[]>(`/api/review/queue?project_id=${project.id}`),
        api<any[]>(`/api/review/decisions?project_id=${project.id}&limit=12`),
        api<AuditEvent[]>(`/api/audit?limit=25`),
      ]);
      setQueue(q); setDecisions(d); setActivity(a);
      const next = q.find((x) => x.id === keep) || q[0];
      setSelected(next ? await api<EvidenceFull>(`/api/evidence/${next.id}`) : null);
    } catch (e: any) { setError(e.message); }
  }, [project]);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorBox message={error} />;
  if (!queue) return <Loading />;

  const signals: Signal[] = selected ? Object.values(selected.integrity?.signals || {}).filter((s: any) => s?.key)
    .sort((a, b) => RANK[a.status] - RANK[b.status]) : [];

  return (
    <div>
      <PageHeader title="Review"
        lead="AI observes, rules decide, people resolve. Anything the checks couldn't settle waits here. Every decision needs a name and a reason, and is kept in the audit log." />

      {queue.length === 0 ? (
        <Empty title="Nothing waiting">Every piece of evidence in this project is either corroborated or already has a reviewer decision.</Empty>
      ) : (
        <div className="grid lg:grid-cols-[300px_minmax(0,1fr)] gap-8 items-start">
          <ul className="border border-line rounded-md divide-y divide-line max-h-[75vh] overflow-y-auto scroll-thin">
            {queue.map((e) => (
              <li key={e.id}>
                <button onClick={async () => setSelected(await api(`/api/evidence/${e.id}`))}
                  className={`w-full text-left flex gap-3 p-3 hover:bg-raised ${selected?.id === e.id ? "bg-raised" : ""}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={e.thumb_url || ""} alt="" className="w-16 h-12 object-cover rounded-sm shrink-0" />
                  <span className="min-w-0">
                    <span className="flex gap-2 items-center"><span className="font-mono text-sm">{e.code}</span><StatusTag status={e.integrity_status} /></span>
                    <span className="block text-xs text-muted line-clamp-2 mt-0.5">{e.headline_reasons[0] || STATUS_HELP[e.integrity_status]}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>

          {selected && (
            <div className="grid xl:grid-cols-2 gap-8 items-start">
              <div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={selected.image_url || ""} alt="" className="w-full rounded-lg ring-1 ring-line" />
                {selected.duplicate_matches[0] && (
                  <div className="flex gap-3 items-center mt-4 text-sm">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={selected.duplicate_matches[0].thumb_url || ""} alt="" className="w-24 h-18 object-cover rounded-sm" />
                    <span>Looks like <Link className="underline font-mono" href={`/evidence/${selected.duplicate_matches[0].id}`}>{selected.duplicate_matches[0].code}</Link>,
                      taken {fmtDate(selected.duplicate_matches[0].captured_at)}.</span>
                  </div>
                )}
                <Link href={`/evidence/${selected.id}`} className="inline-block mt-4 text-sm text-gold underline underline-offset-2">Open full evidence record</Link>
              </div>
              <div>
                <div className="flex items-center justify-between gap-3">
                  <h2 className="font-serif text-3xl">{selected.code}</h2>
                  <StatusTag status={selected.integrity?.status || "UNVERIFIABLE"} />
                </div>
                <p className="text-sm text-muted mt-1">Trust score {selected.integrity?.score ?? "–"} from {selected.integrity?.available} of {selected.integrity?.total} checks</p>
                <div className="mt-4"><CheckLedger signals={signals} compact /></div>
                <div className="mt-6">
                  <ReviewForm compact evidence={selected} onDone={() => load()} />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-10 mt-16">
        <section>
          <h2 className="t-title mb-4">Recent decisions</h2>
          {decisions.length === 0 ? <p className="text-muted text-sm">No decisions yet.</p> : (
            <ul className="divide-y divide-line border-y border-line">
              {decisions.map((d, i) => (
                <li key={i} className="py-3 text-sm">
                  <Link href={`/evidence/${d.evidence.id}`} className="font-mono underline">{d.evidence.code}</Link>{" "}
                  <b className={d.decision === "REJECTED" ? "text-bad" : d.decision === "APPROVED" ? "text-ok" : "text-muted"}>{d.decision.toLowerCase()}</b>
                  {" "}by {d.reviewer}{d.engine_status_label ? ` (checks said ${d.engine_status_label.toLowerCase()})` : ""}
                  <div className="text-muted mt-0.5">“{d.reason}”</div>
                  <div className="text-xs text-faint mt-0.5">{fmtUtc(d.created_at)}</div>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h2 className="t-title mb-4">Audit log</h2>
          <ul className="divide-y divide-line border-y border-line text-sm">
            {activity.map((a) => (
              <li key={a.id} className="py-2.5 flex gap-3">
                <span className="text-xs text-faint w-28 shrink-0 pt-0.5">{fmtUtc(a.created_at)}</span>
                <span className="min-w-0">
                  {a.entity_type === "evidence" ? <Link href={`/evidence/${a.entity_id}`} className="font-mono underline">EV-{String(a.entity_id).padStart(4, "0")}</Link>
                    : a.entity_type === "claim" ? <Link href={`/claims/${a.entity_id}`} className="underline">Claim #{a.entity_id}</Link>
                      : <span className="text-muted capitalize">{a.entity_type}</span>}{" "}
                  <span className="text-muted">{a.summary}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
