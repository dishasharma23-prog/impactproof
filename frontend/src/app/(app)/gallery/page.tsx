"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import DeletePanel from "@/components/DeletePanel";
import { PhotoRecord } from "@/components/system";
import { btn, btnGhost, Empty, ErrorBox, Loading, PageHeader, StatusTag, Toast } from "@/components/ui";
import { api, EvidenceLight, fmtDate, STATUS_LABEL, STATUS_ORDER } from "@/lib/api";
import { useProject } from "@/lib/project";

type Group = "stage" | "category" | "site" | "date";
interface Section { key: string; title: string; items: EvidenceLight[]; counts: Record<string, number> }
interface Gallery { group: Group; total: number; sections: Section[] }

const GROUPS: { key: Group; label: string; hint: string }[] = [
  { key: "stage", label: "Before, during, after", hint: "The AI places each photo in the story of the work. You can correct it on any photo." },
  { key: "category", label: "By activity", hint: "Grouped by what the photo shows: waste, planting, water, construction and more." },
  { key: "site", label: "By site", hint: "Grouped by the project site each photo was taken at, matched from its location." },
  { key: "date", label: "By day", hint: "A timeline of the project, newest day first." },
];
const STAGE_NOTE: Record<string, string> = {
  before: "The problem, untouched",
  during: "People doing the work",
  after: "The result",
  other: "Not clearly part of the work",
};

export default function GalleryPage() {
  const { project } = useProject();
  const [group, setGroup] = useState<Group>("stage");
  const [data, setData] = useState<Gallery | null>(null);
  const [onlyGood, setOnlyGood] = useState(false);
  const [error, setError] = useState("");
  const [selecting, setSelecting] = useState(false);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [reload, setReload] = useState(0);
  const [toast, setToast] = useState("");
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 3200); };
  const toggle = (id: number) => setSel((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const stopSelecting = () => { setSelecting(false); setSel(new Set()); setConfirming(false); };

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("deleted")) {
      flash("Photo deleted");
      window.history.replaceState(null, "", "/gallery");
    }
  }, []);

  useEffect(() => {
    try { const g = localStorage.getItem("ip.gallery") as Group | null; if (g) setGroup(g); } catch {}
  }, []);
  useEffect(() => {
    if (!project) return;
    setData(null);
    api<Gallery>(`/api/projects/${project.id}/gallery?group=${group}`).then(setData).catch((e) => setError(e.message));
  }, [project, group, reload]);

  const pick = (g: Group) => { setGroup(g); try { localStorage.setItem("ip.gallery", g); } catch {} };

  if (error) return <ErrorBox message={error} />;
  if (!project) return <Loading />;
  const hint = GROUPS.find((g) => g.key === group)!.hint;

  return (
    <div>
      <PageHeader title="Gallery" lead={<>Every photo in <b className="text-paper">{project.name}</b>, arranged automatically. {hint}</>}>
        {selecting
          ? <button onClick={stopSelecting} className={btnGhost}>Done</button>
          : <button onClick={() => setSelecting(true)} className={btnGhost}>Select</button>}
        <Link href="/upload" className={btn}>Add evidence</Link>
      </PageHeader>

      <div className="flex flex-wrap items-center gap-3 mb-8">
        <div role="tablist" aria-label="Arrange photos" className="flex flex-wrap gap-6 border-b border-line">
          {GROUPS.map((g) => (
            <button key={g.key} role="tab" aria-selected={group === g.key} onClick={() => pick(g.key)}
              className={`pb-3 -mb-px text-sm border-b transition-colors ${group === g.key ? "text-paper border-paper" : "text-paper/55 font-light border-transparent hover:text-paper"}`}>
              {g.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-muted ml-auto">
          <input type="checkbox" checked={onlyGood} onChange={(e) => setOnlyGood(e.target.checked)} />
          Corroborated only
        </label>
      </div>

      {!data ? <Loading /> : data.total === 0 ? (
        <Empty title="No photos yet" action={{ href: "/upload", label: "Add evidence" }}>Upload field photos and they will be sorted here automatically.</Empty>
      ) : (
        <div className="space-y-16">
          {data.sections.map((sec) => {
            const items = onlyGood ? sec.items.filter((e) => e.integrity_status === "CORROBORATED") : sec.items;
            return (
              <section key={sec.key} aria-labelledby={`sec-${sec.key}`}>
                <div className="flex flex-wrap items-end gap-x-5 gap-y-1 border-t border-line pt-4 mb-7">
                  <div>
                    {group === "stage" && STAGE_NOTE[sec.key] && <p className="t-label mb-2">{STAGE_NOTE[sec.key]}</p>}
                    <h2 id={`sec-${sec.key}`} className="t-title">{sec.title}</h2>
                  </div>
                  <span className="ml-auto flex flex-wrap gap-4 text-sm">
                    <span className="t-meta text-[11px] text-faint uppercase">{sec.items.length} record{sec.items.length === 1 ? "" : "s"}</span>
                    {STATUS_ORDER.filter((s) => sec.counts[s]).map((s) => (
                      <span key={s} className={`v-${s} dot t-meta text-[11px] uppercase`} style={{ color: "var(--v)" }}>{sec.counts[s]} {STATUS_LABEL[s]}</span>
                    ))}
                  </span>
                </div>
                {items.length === 0 ? <p className="text-muted text-sm">No corroborated photos in this section yet.</p> : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-5 gap-y-9">
                    {items.map((e) => selecting
                      ? <PhotoRecord key={e.id} e={e} selected={sel.has(e.id)} onClick={() => toggle(e.id)} />
                      : <PhotoRecord key={e.id} e={e} href={`/evidence/${e.id}`} />)}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {selecting && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[1500] w-[min(640px,calc(100vw-32px))] bg-surface border border-line rounded-2xl shadow-2xl p-4">
          {confirming && sel.size > 0 ? (
            <DeletePanel ids={[...sel]} label={`Delete ${sel.size} photo${sel.size === 1 ? "" : "s"}`} compact
              onCancel={() => setConfirming(false)}
              onDone={(n) => { stopSelecting(); setReload((r) => r + 1); flash(`${n} photo${n === 1 ? "" : "s"} deleted`); }} />
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm">{sel.size ? <b>{sel.size} selected</b> : "Tap photos to select them"}</span>
              <button onClick={() => setSel(new Set(data?.sections.flatMap((x) => x.items.map((i) => i.id)) ?? []))} className="text-sm text-muted underline underline-offset-2 hover:text-paper">Select all</button>
              {sel.size > 0 && <button onClick={() => setSel(new Set())} className="text-sm text-muted underline underline-offset-2 hover:text-paper">Clear</button>}
              <button onClick={() => setConfirming(true)} disabled={!sel.size} className={`${btn} ml-auto !bg-bad disabled:!bg-bad/40`}>Delete…</button>
            </div>
          )}
        </div>
      )}
      {toast && <Toast message={toast} />}
    </div>
  );
}
