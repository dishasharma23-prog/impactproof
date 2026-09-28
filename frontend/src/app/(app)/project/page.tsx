"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import EvidenceMap from "@/components/EvidenceMap";
import { SdgPicker } from "@/components/Sdg";
import { btn, btnDanger, btnGhost, ErrorBox, input, label, Loading, PageHeader, Toast } from "@/components/ui";
import { api, postJSON, Project, SdgInfo, Site } from "@/lib/api";
import { useProject } from "@/lib/project";

export default function ProjectPageWrapper() {
  return <Suspense fallback={<Loading />}><ProjectPage /></Suspense>;
}

function ProjectPage() {
  const { project, reload, setProjectId } = useProject();
  const params = useSearchParams();
  const [form, setForm] = useState<Partial<Project>>({});
  const [sites, setSites] = useState<Site[]>([]);
  const [suggest, setSuggest] = useState<any[]>([]);
  const [draft, setDraft] = useState<{ name: string; lat: number | null; lng: number | null; radius: number }>({ name: "", lat: null, lng: null, radius: 300 });
  const [toast, setToast] = useState("");
  const [err, setErr] = useState("");
  const [newProject, setNewProject] = useState({ name: "", description: "" });
  const [allSdgs, setAllSdgs] = useState<SdgInfo[]>([]);
  const [goals, setGoals] = useState<number[]>([]);
  useEffect(() => { api<SdgInfo[]>("/api/sdgs").then(setAllSdgs).catch(() => {}); }, []);

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 3500); };
  const load = useCallback(async () => {
    if (!project) return;
    setForm(project);
    setGoals((project.sdgs || []).map((g) => g.number));
    const p = await api<any>(`/api/projects/${project.id}`);
    setSites(p.sites);
    api<any[]>(`/api/projects/${project.id}/suggest-sites`).then(setSuggest).catch(() => {});
  }, [project]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const lat = params.get("lat"), lng = params.get("lng");
    if (lat && lng) setDraft((d) => ({ ...d, lat: Number(lat), lng: Number(lng) }));
  }, [params]);

  if (!project) return <Loading />;

  async function save(ev: React.FormEvent) {
    ev.preventDefault(); setErr("");
    try {
      await postJSON(`/api/projects/${project!.id}`, {
        name: form.name, description: form.description || "", organization: form.organization || null,
        start_date: form.start_date || null, end_date: form.end_date || null, sdgs: goals,
      }, "PUT");
      await reload();
      flash("Saved. All evidence was checked again.");
    } catch (e: any) { setErr(e.message); }
  }

  async function addSite(ev: React.FormEvent) {
    ev.preventDefault(); setErr("");
    if (draft.lat == null || draft.lng == null) return setErr("Click the map to place the site first.");
    try {
      await postJSON(`/api/projects/${project!.id}/sites`, {
        name: draft.name.trim() || `Site ${sites.length + 1}`, latitude: draft.lat, longitude: draft.lng, radius_m: draft.radius,
      });
      setDraft({ name: "", lat: null, lng: null, radius: 300 });
      await load();
      flash("Site added. All evidence was checked again.");
    } catch (e: any) { setErr(e.message); }
  }

  async function updateSite(s: Site) {
    try {
      await postJSON(`/api/sites/${s.id}`, { name: s.name, latitude: s.latitude, longitude: s.longitude, radius_m: s.radius_m, description: s.description }, "PUT");
      await load(); flash("Site updated.");
    } catch (e: any) { setErr(e.message); }
  }

  async function removeSite(s: Site) {
    if (!confirm(`Remove ${s.name}? Its photos stay, but they will no longer match a site.`)) return;
    await api(`/api/sites/${s.id}`, { method: "DELETE" });
    await load(); flash("Site removed.");
  }

  async function createProject(ev: React.FormEvent) {
    ev.preventDefault();
    if (!newProject.name.trim()) return;
    const p = await postJSON<Project>("/api/projects", newProject);
    await reload(); setProjectId(p.id); setNewProject({ name: "", description: "" });
    flash(`${p.name} created and selected.`);
  }

  return (
    <div className="max-w-5xl">
      <Toast message={toast} />
      <PageHeader title="Project settings" lead="Every photo is checked against the sites and the project period set here. Changing them re-checks all evidence." />
      {err && <div className="mb-6"><ErrorBox message={err} /></div>}

      <form onSubmit={save} className="grid md:grid-cols-2 gap-5">
        <div className="md:col-span-2"><label className={label} htmlFor="pn">Project name</label>
          <input id="pn" className={input} value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div className="md:col-span-2"><label className={label} htmlFor="pd">What the project does</label>
          <textarea id="pd" rows={2} className={input} value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <p className="text-xs text-muted mt-1">The AI uses this to judge whether a photo shows the project&apos;s kind of work.</p></div>
        <div><label className={label} htmlFor="po">Organisation</label>
          <input id="po" className={input} value={form.organization || ""} onChange={(e) => setForm({ ...form, organization: e.target.value })} placeholder="e.g. Green Hands Foundation" />
          <p className="text-xs text-muted mt-1">Photos showing another organisation&apos;s name are flagged for review.</p></div>
        <div className="grid grid-cols-2 gap-4">
          <div><label className={label} htmlFor="ps">Start date</label>
            <input id="ps" type="date" className={input} value={form.start_date || ""} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></div>
          <div><label className={label} htmlFor="pe">End date</label>
            <input id="pe" type="date" className={input} value={form.end_date || ""} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></div>
        </div>
        <div className="md:col-span-2">
          <span className={label}>Sustainable Development Goals</span>
          <p className="text-xs text-muted mb-3">Pick the UN goals this project works towards. The AI tags each photo with the goals it visibly supports, and reports count verified evidence per goal.</p>
          {allSdgs.length > 0 && <SdgPicker all={allSdgs} selected={goals} onChange={setGoals} />}
        </div>
        <div><button className={btn}>Save project</button></div>
      </form>

      <section className="mt-16">
        <h2 className="font-serif text-3xl">Sites</h2>
        <p className="text-muted mt-2 mb-5">A photo passes the location check when it was taken inside a site&apos;s circle. Click the map to place a new site.</p>
        <EvidenceMap height={420} sites={sites} onPick={(lat, lng) => setDraft((d) => ({ ...d, lat, lng }))}
          draft={draft.lat != null && draft.lng != null ? { lat: draft.lat, lng: draft.lng, radius: draft.radius } : null} />

        <form onSubmit={addSite} className="grid md:grid-cols-[1fr_150px_auto] gap-4 items-end mt-5 border border-line rounded-md p-4">
          <div><label className={label} htmlFor="sn">New site name</label>
            <input id="sn" className={input} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder={`Site ${sites.length + 1}`} />
            <p className="text-xs text-muted mt-1">{draft.lat != null ? `Placed at ${draft.lat.toFixed(5)}, ${draft.lng!.toFixed(5)}` : "Not placed yet: click the map."}</p></div>
          <div><label className={label} htmlFor="sr">Radius (m)</label>
            <input id="sr" type="number" min={30} step={10} className={input} value={draft.radius} onChange={(e) => setDraft({ ...draft, radius: Number(e.target.value) || 300 })} /></div>
          <button className={btn}>Add site</button>
        </form>

        {suggest.length > 0 && (
          <div className="mt-5 border-l-4 border-teal bg-teal/10 px-4 py-3">
            <p className="text-sm font-medium">Your photos cluster in {suggest.length} place{suggest.length === 1 ? "" : "s"} without a site:</p>
            <div className="flex flex-wrap gap-2 mt-2">
              {suggest.map((s, i) => (
                <button key={i} type="button" className={btnGhost}
                  onClick={() => setDraft({ name: `Site ${sites.length + 1}`, lat: s.latitude, lng: s.longitude, radius: s.radius_m })}>
                  {s.photos} photos near {s.latitude.toFixed(3)}, {s.longitude.toFixed(3)}
                </button>
              ))}
            </div>
          </div>
        )}

        <ul className="mt-8 divide-y divide-line border-y border-line">
          {sites.map((s) => <SiteRow key={s.id} site={s} onSave={updateSite} onDelete={removeSite} />)}
          {sites.length === 0 && <li className="py-4 text-muted text-sm">No sites yet.</li>}
        </ul>
      </section>

      <section className="mt-16">
        <h2 className="font-serif text-3xl">New project</h2>
        <p className="text-muted mt-2 mb-5">Useful for showing reuse across projects, e.g. a photo from last year&apos;s drive submitted again.</p>
        <form onSubmit={createProject} className="grid md:grid-cols-[1fr_1.5fr_auto] gap-4 items-end">
          <div><label className={label} htmlFor="nn">Name</label><input id="nn" className={input} value={newProject.name} onChange={(e) => setNewProject({ ...newProject, name: e.target.value })} /></div>
          <div><label className={label} htmlFor="nd">What it does</label><input id="nd" className={input} value={newProject.description} onChange={(e) => setNewProject({ ...newProject, description: e.target.value })} /></div>
          <button className={btnGhost}>Create project</button>
        </form>
      </section>
    </div>
  );
}

function SiteRow({ site, onSave, onDelete }: { site: Site; onSave: (s: Site) => void; onDelete: (s: Site) => void }) {
  const [s, setS] = useState(site);
  useEffect(() => setS(site), [site]);
  const dirty = s.name !== site.name || s.radius_m !== site.radius_m;
  return (
    <li className="py-4 grid md:grid-cols-[1fr_120px_auto] gap-4 items-center">
      <div>
        <input className={input} value={s.name} onChange={(e) => setS({ ...s, name: e.target.value })} aria-label="Site name" />
        <p className="text-xs text-muted mt-1">
          {s.latitude?.toFixed(5)}, {s.longitude?.toFixed(5)}. {s.evidence_count} photos, {s.corroborated_count} corroborated.
        </p>
      </div>
      <input type="number" className={input} value={s.radius_m} onChange={(e) => setS({ ...s, radius_m: Number(e.target.value) })} aria-label="Radius in metres" />
      <div className="flex gap-2">
        <button type="button" className={btnGhost} disabled={!dirty} onClick={() => onSave(s)}>Save</button>
        <button type="button" className={btnDanger} onClick={() => onDelete(site)}>Remove</button>
      </div>
    </li>
  );
}
