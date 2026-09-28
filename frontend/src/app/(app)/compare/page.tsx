"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import BeforeAfter from "@/components/BeforeAfter";
import { btnGhost, Empty, ErrorBox, Loading, PageHeader, StatusTag } from "@/components/ui";
import { api, EvidenceLight, fmtDate, postJSON } from "@/lib/api";
import { useProject } from "@/lib/project";

interface Pair {
  key: string; before: number; after: number; label: string; site_name: string | null;
  photos_at_viewpoint: number; gap_days: number; gap_hours: number; distance_m: number | null;
  signal_changes: string[]; both_corroborated: boolean; description: any;
  before_evidence: EvidenceLight; after_evidence: EvidenceLight;
}

export default function ComparePage() {
  const { project } = useProject();
  const [pairs, setPairs] = useState<Pair[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!project) return;
    setPairs(null);
    api<Pair[]>(`/api/projects/${project.id}/pairs`).then(setPairs).catch((e) => setError(e.message));
  }, [project]);

  if (error) return <ErrorBox message={error} />;
  if (!pairs) return <Loading />;

  return (
    <div>
      <PageHeader title="Before and after"
        lead="Photos taken within a few metres of each other at different times are paired automatically: the earliest and the latest from each viewpoint. Suspicious and rejected photos are left out." />
      {pairs.length === 0 ? (
        <Empty title="No pairs yet" action={{ href: "/capture", label: "Open camera" }}>
          Add two photos with GPS from the same spot, at least 30 minutes apart. The camera&apos;s ghost overlay helps you match the angle.
        </Empty>
      ) : (
        <div className="divide-y divide-line">
          {pairs.map((p) => <PairRow key={p.key} p={p} />)}
        </div>
      )}
    </div>
  );
}

function PairRow({ p }: { p: Pair }) {
  const [desc, setDesc] = useState(p.description);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const a = p.before_evidence, b = p.after_evidence;
  const gap = p.gap_days >= 1 ? `${p.gap_days} days` : `${p.gap_hours} hours`;

  async function describe() {
    setBusy(true); setErr("");
    try { setDesc(await postJSON("/api/pairs/describe", { before: p.before, after: p.after })); }
    catch (e: any) { setErr(e.message); }
    setBusy(false);
  }

  return (
    <section className="grid lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] gap-8 py-10 first:pt-0">
      <BeforeAfter before={a.image_url || ""} after={b.image_url || ""} beforeLabel={fmtDate(a.capture_time)} afterLabel={fmtDate(b.capture_time)} />
      <div>
        <h2 className="font-serif text-3xl">{p.label}</h2>
        <p className="text-muted mt-2">
          {gap} apart{p.distance_m != null ? `, taken ${p.distance_m} m from each other` : ""}. {p.photos_at_viewpoint} photos from this viewpoint.
        </p>
        <div className="flex flex-wrap gap-x-6 gap-y-2 mt-4 text-sm">
          <Link href={`/evidence/${a.id}`} className="flex items-center gap-2"><span className="text-muted">Before</span><span className="font-mono underline">{a.code}</span><StatusTag status={a.integrity_status} /></Link>
          <Link href={`/evidence/${b.id}`} className="flex items-center gap-2"><span className="text-muted">After</span><span className="font-mono underline">{b.code}</span><StatusTag status={b.integrity_status} /></Link>
        </div>
        {!p.both_corroborated && <p className="text-sm text-review mt-3">Only corroborated pairs appear in reports. Review the other photo first.</p>}
        {p.signal_changes.length > 0 && (
          <>
            <h3 className="font-semibold mt-6">Detected changes</h3>
            <ul className="list-disc pl-5 text-sm mt-2 space-y-1 marker:text-faint">{p.signal_changes.map((c) => <li key={c}>{c}</li>)}</ul>
          </>
        )}
        {desc ? (
          <div className="mt-6">
            <h3 className="font-semibold">What changed</h3>
            <p className="text-[15px] mt-2 leading-relaxed">{desc.change_summary}</p>
            <p className={`text-sm mt-3 ${desc.same_site_likely ? "text-muted" : "text-bad"}`}>
              {desc.same_site_likely ? "Same view: " : "Possibly not the same view: "}{desc.same_site_reason} Confidence {desc.confidence}.
            </p>
          </div>
        ) : (
          <button onClick={describe} disabled={busy} className={`${btnGhost} mt-6`}>{busy ? "Comparing photos…" : "Describe the change with AI"}</button>
        )}
        {err && <p className="text-bad text-sm mt-2">{err}</p>}
      </div>
    </section>
  );
}
