"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight } from "lucide-react";
import EvidenceMap from "@/components/EvidenceMap";
import { SdgBadge } from "@/components/Sdg";
import { EvidenceGrid, EvidenceRow, PhotoRecord, SectionHeading, Stat, Timeline } from "@/components/system";
import { btn, btnGhost, Empty, ErrorBox, input, Loading, PageHeader } from "@/components/ui";
import { api, AuditEvent, Coverage, EvidenceLight, fmtDate, postJSON, SdgInfo, Site, STATUS_HELP, STATUS_ORDER } from "@/lib/api";
import { useProject } from "@/lib/project";

interface Overview {
  counts: Record<string, number>;
  total: number;
  sites: Site[];
  coverage: Coverage;
  evidence: EvidenceLight[];
  review_count: number;
  claims: number;
  sdgs: SdgInfo[];
}

const STAT_LABEL: Record<string, string> = {
  CORROBORATED: "Corroborated", NEEDS_REVIEW: "Pending review", SUSPICIOUS: "Flagged", UNVERIFIABLE: "Unverifiable",
};
const ACTION_TONE: Record<string, string> = { verdict: "bg-teal", review: "bg-gold", delete: "bg-bad", upload: "bg-paper/60" };

function stamp(iso: string) {
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z");
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Activity lines, without file hashes and generated file names. */
function tidy(s: string) {
  const t = s
    .replace(/\s*\([0-9a-f]{8}-[0-9a-f-]{27,}\.\w+\)/gi, "")
    .replace(/,\s*SHA-256 [0-9a-f]+(?:…|\.\.\.)?;?/gi, ";")
    .replace(/\.?\s*SHA-256 [0-9a-f]+(?:…|\.\.\.)?\.?/gi, ".")
    .replace(/Received capture-\d+\.\w+/i, "Received a live capture")
    .replace(/Received [0-9a-f-]{20,}\.\w+/i, "Received a photo")
    .trim();
  return t.length > 130 ? t.slice(0, 130) + "…" : t;
}

export default function Dashboard() {
  const { project } = useProject();
  const [data, setData] = useState<Overview | null>(null);
  const [activity, setActivity] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ mode: string; items: EvidenceLight[] } | null>(null);
  const [searching, setSearching] = useState(false);

  const load = useCallback(async () => {
    if (!project) return;
    try {
      const [ov, act] = await Promise.all([
        api<Overview>(`/api/projects/${project.id}/overview`),
        api<AuditEvent[]>(`/api/audit?project_id=${project.id}&limit=9`).catch(() => []),
      ]);
      setData(ov); setActivity(act); setError("");
    } catch (e: any) {
      setError(e.message);
    }
  }, [project]);
  useEffect(() => { setData(null); setResults(null); setFilter(null); load(); }, [load]);

  async function search(ev: React.FormEvent) {
    ev.preventDefault();
    if (!query.trim() || !project) return setResults(null);
    setSearching(true);
    try {
      const r = await postJSON<any>("/api/evidence/search", { query, project_id: project.id, limit: 24 });
      setResults({ mode: r.mode, items: r.results });
    } catch (e: any) { setError(e.message); }
    setSearching(false);
  }

  const shown = useMemo(() => {
    const base = results ? results.items : data?.evidence || [];
    return filter ? base.filter((e) => e.integrity_status === filter) : base;
  }, [data, results, filter]);

  if (!project) return <Loading />;
  if (error && !data) return <ErrorBox message={error} />;
  if (!data) return <Loading />;

  const staleIds = new Set(data.coverage.sites.filter((s) => s.stale).map((s) => s.site_id));
  const period = project.start_date || project.end_date ? `${fmtDate(project.start_date)} – ${fmtDate(project.end_date)}` : null;
  const recent = [...data.evidence].sort((a, b) => (b.uploaded_at || "").localeCompare(a.uploaded_at || "")).slice(0, 6);

  return (
    <div>
      <PageHeader label={`Evidence control room${project.organization ? ` · ${project.organization}` : ""}`} title={project.name}
        lead={<span className="t-meta text-[12px] uppercase text-faint">
          {[period || "No project period set", `${data.sites.length} site${data.sites.length === 1 ? "" : "s"}`,
            `${data.total} field record${data.total === 1 ? "" : "s"}`, `${data.claims} claim${data.claims === 1 ? "" : "s"}`].join("  ·  ")}
        </span>}>
        <Link href="/capture" className={btnGhost}>Open camera</Link>
        <Link href="/upload" className={btn}>Add evidence</Link>
      </PageHeader>

      {(!period || data.sites.every((s) => s.latitude == null)) && (
        <p className="border-l-2 border-gold pl-4 mb-12 text-[15px] text-paper/85 max-w-3xl">
          Photos are checked against the project&apos;s sites and dates. Set them in{" "}
          <Link href="/project" className="underline underline-offset-4 decoration-gold">project settings</Link> so location and date checks can run.
        </p>
      )}

      {/* ---------------- impact overview */}
      <section className="mb-16">
        <SectionHeading label="Impact overview" className="!border-t-0 !pt-0">
          {filter && <button onClick={() => setFilter(null)} className="text-muted underline underline-offset-4 hover:text-paper">Show all</button>}
        </SectionHeading>
        <div role="group" aria-label="Filter by verdict" className="grid grid-cols-2 lg:grid-cols-4 gap-y-10">
          {STATUS_ORDER.map((s, i) => (
            <button key={s} onClick={() => setFilter(filter === s ? null : s)} aria-pressed={filter === s}
              className={`text-left pr-6 ${i % 2 ? "pl-6 border-l border-line" : ""} ${i === 2 ? "lg:pl-6 lg:border-l border-line" : ""} ${filter && filter !== s ? "opacity-40" : ""} transition-opacity`}>
              <Stat value={data.counts[s] || 0} label={STAT_LABEL[s]} status={s} note={STATUS_HELP[s]} />
            </button>
          ))}
        </div>
        {data.sdgs.length > 0 && (
          <div className="mt-10 flex flex-wrap items-center gap-2">
            <span className="t-label mr-2">Supports</span>
            {data.sdgs.map((g) => <SdgBadge key={g.number} g={g} size="sm" count={g.photos} />)}
          </div>
        )}
      </section>

      {/* ---------------- recent evidence + activity */}
      {data.total > 0 && (
        <section className="grid lg:grid-cols-[1.35fr_1fr] gap-x-14 gap-y-14 mb-16">
          <div>
            <SectionHeading label="Recent evidence">
              <Link href="/gallery" className="text-muted hover:text-paper inline-flex items-center gap-1">Gallery <ArrowRight size={14} /></Link>
            </SectionHeading>
            <div className="-mt-3">{recent.map((e) => <EvidenceRow key={e.id} e={e} href={`/evidence/${e.id}`} />)}</div>
          </div>
          <div>
            <SectionHeading label="Verification activity" />
            {data.review_count > 0 && (
              <Link href="/review" className="group flex items-baseline justify-between border-b border-line pb-4 mb-6">
                <span><span className="t-num text-4xl text-review">{data.review_count}</span>
                  <span className="ml-3 text-sm text-muted">record{data.review_count === 1 ? "" : "s"} waiting for a reviewer</span></span>
                <ArrowRight size={16} className="text-muted group-hover:translate-x-0.5 transition-transform" />
              </Link>
            )}
            {activity.length ? (
              <Timeline items={activity.map((a) => ({ key: a.id, time: stamp(a.created_at), by: a.actor !== "system" ? a.actor : undefined,
                text: tidy(a.summary), tone: ACTION_TONE[a.action] }))} />
            ) : <p className="text-sm text-muted">No activity yet.</p>}
          </div>
        </section>
      )}

      {/* ---------------- geography */}
      <section className="mb-16">
        <SectionHeading label="Where the evidence was captured" />
        <div className="grid lg:grid-cols-[1fr_280px] gap-x-10 gap-y-8">
          <EvidenceMap sites={data.sites.map((s) => ({ ...s, stale: staleIds.has(s.id) }))} points={data.evidence} height={380} />
          <div>
            <p className="t-label mb-3">Site coverage</p>
            <p className="text-sm text-paper/85">{data.coverage.summary}</p>
            <ul className="mt-4 border-t border-line">
              {data.coverage.sites.map((s) => (
                <li key={s.site_id} className="flex justify-between gap-3 py-2.5 border-b border-line text-sm">
                  <span className={s.stale ? "text-review" : ""}>{s.site_name}</span>
                  <span className="t-meta text-[11px] text-faint uppercase whitespace-nowrap">{s.last_evidence ? fmtDate(s.last_evidence) : "No evidence"}</span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-faint mt-3 leading-relaxed">Listed so reports can&apos;t quietly skip sites that went quiet.</p>
          </div>
        </div>
      </section>

      {/* ---------------- all field records */}
      <section>
        <SectionHeading label="Field records">
          <span className="t-meta text-[11px] text-faint uppercase">
            {results ? `${results.mode === "semantic" ? "Semantic" : "Keyword"} search · ` : ""}{shown.length} of {data.total}
          </span>
        </SectionHeading>
        <form onSubmit={search} className="flex flex-wrap items-center gap-3 mb-10">
          <input value={query} onChange={(e) => { setQuery(e.target.value); if (!e.target.value) setResults(null); }}
            placeholder="Search by meaning, e.g. water tank with people collecting water" className={`${input} max-w-xl`} aria-label="Search evidence" />
          <button className={btnGhost} disabled={searching}>{searching ? "Searching…" : "Search"}</button>
          {results && <button type="button" className="text-sm text-muted underline underline-offset-4" onClick={() => { setResults(null); setQuery(""); }}>Clear</button>}
        </form>
        {data.total === 0 ? (
          <Empty title="No evidence yet" action={{ href: "/upload", label: "Add evidence" }}>
            Add field photos or take them with the in-app camera. Each one is checked for place, time, reuse, AI generation and content.
          </Empty>
        ) : shown.length === 0 ? <p className="text-muted">Nothing matches.</p> : (
          <EvidenceGrid dense>{shown.map((e) => <PhotoRecord key={e.id} e={e} href={`/evidence/${e.id}`} size="sm" />)}</EvidenceGrid>
        )}
      </section>
    </div>
  );
}
