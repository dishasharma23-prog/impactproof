"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { btnGhost, Loading, PageHeader, StatusTag } from "@/components/ui";
import { API, api, EvidenceLight, postJSON, Site } from "@/lib/api";
import { useProject } from "@/lib/project";

interface Row { key?: string; name: string; state: "waiting" | "checking" | "done" | "error"; evidence?: EvidenceLight; error?: string }

export default function UploadPage() {
  const { project } = useProject();
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState<string>("");
  const [rows, setRows] = useState<Row[]>([]);
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [widgetCfg, setWidgetCfg] = useState<{ enabled: boolean; cloud_name: string; api_key: string; folder: string } | null>(null);
  const [widgetErr, setWidgetErr] = useState("");
  useEffect(() => { api<any>("/api/cloudinary/widget-config").then(setWidgetCfg).catch(() => {}); }, []);

  useEffect(() => {
    if (project) api<any>(`/api/projects/${project.id}`).then((p) => setSites(p.sites)).catch(() => {});
  }, [project]);

  if (!project) return <Loading />;

  async function addFiles(files: File[]) {
    const start = rows.length;
    setRows((r) => [...r, ...files.map((f) => ({ name: f.name, state: "waiting" as const }))]);
    for (let i = 0; i < files.length; i++) {
      const idx = start + i;
      setRows((r) => r.map((x, j) => (j === idx ? { ...x, state: "checking" } : x)));
      const fd = new FormData();
      fd.append("file", files[i]);
      fd.append("project_id", String(project!.id));
      if (siteId) fd.append("site_id", siteId);
      try {
        const res = await fetch(`${API}/api/evidence/upload`, { method: "POST", body: fd });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Upload failed (${res.status})`);
        setRows((r) => r.map((x, j) => (j === idx ? { ...x, state: "done", evidence: data.evidence } : x)));
      } catch (e: any) {
        const msg = e.message === "Failed to fetch" ? "Can't reach the backend." : e.message;
        setRows((r) => r.map((x, j) => (j === idx ? { ...x, state: "error", error: msg } : x)));
      }
    }
  }

  async function loadWidgetScript(): Promise<any> {
    const w = window as any;
    if (w.cloudinary?.createUploadWidget) return w.cloudinary;
    await new Promise<void>((resolve, reject) => {
      const sc = document.createElement("script");
      sc.src = "https://upload-widget.cloudinary.com/latest/global/all.js";
      sc.onload = () => resolve();
      sc.onerror = () => reject(new Error("Could not load the Cloudinary Upload Widget. Check your internet connection."));
      document.body.appendChild(sc);
    });
    return w.cloudinary;
  }

  async function openWidget() {
    if (!widgetCfg?.enabled || !project) return;
    setWidgetErr("");
    let cld: any;
    try { cld = await loadWidgetScript(); } catch (e: any) { return setWidgetErr(e.message); }
    const widget = cld.createUploadWidget({
      cloudName: widgetCfg.cloud_name,
      apiKey: widgetCfg.api_key,
      uploadSignature: (cb: (sig: string) => void, params: Record<string, unknown>) => {
        postJSON<{ signature: string }>("/api/cloudinary/sign", { params_to_sign: params })
          .then((r) => cb(r.signature)).catch((e) => setWidgetErr(e.message));
      },
      folder: `${widgetCfg.folder}/project_${project.id}/field`,
      tags: ["impactproof", "via_widget"],
      sources: ["local", "camera", "url"],
      multiple: true,
      clientAllowedFormats: ["jpg", "jpeg", "png", "webp"],
      maxFileSize: 25_000_000,
      showPoweredBy: false,
      styles: { palette: { window: "#17100A", windowBorder: "#3A2E24", tabIcon: "#36D6B0", menuIcons: "#A99E91",
        textDark: "#100904", textLight: "#F4E8D8", link: "#36D6B0", action: "#36D6B0", inactiveTabIcon: "#6F665C",
        error: "#EF7D63", inProgress: "#36D6B0", complete: "#36D6B0", sourceBg: "#21170F" } },
    }, async (error: any, result: any) => {
      if (error) return setWidgetErr(error.statusText || error.message || "Upload failed");
      if (result?.event !== "success") return;
      const info = result.info;
      const name = `${info.original_filename || "photo"}.${info.format || "jpg"}`;
      const key = `${info.public_id}-${Date.now()}`;
      setRows((r) => [...r, { key, name, state: "checking" }]);
      try {
        const out = await postJSON<{ evidence: EvidenceLight }>("/api/evidence/from-cloudinary", {
          public_id: info.public_id, project_id: project.id, site_id: siteId ? Number(siteId) : null, original_filename: name,
        });
        setRows((r) => r.map((x) => (x.key === key ? { ...x, state: "done", evidence: out.evidence } : x)));
      } catch (e: any) {
        setRows((r) => r.map((x) => (x.key === key ? { ...x, state: "error", error: e.message } : x)));
      }
    });
    widget.open();
  }

  const done = rows.filter((r) => r.state === "done").length;

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Add evidence"
        lead={<>Photos go to <b className="text-paper">{project.name}</b>. Each one is stored untouched on Cloudinary, fingerprinted, described by AI and checked against the project&apos;s sites and dates.</>}
      />

      <div className="flex flex-wrap items-end gap-4 mb-5">
        <label className="text-sm">
          <span className="block font-medium mb-1.5">Site (optional)</span>
          <select value={siteId} onChange={(e) => setSiteId(e.target.value)} className="border border-line rounded-md px-3 py-2 min-w-[220px]">
            <option value="">Work it out from GPS</option>
            {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <p className="text-sm text-muted max-w-md">Photos with GPS are matched to the nearest site automatically. Pick a site only for photos without GPS.</p>
      </div>

      <label
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); inputRef.current?.click(); } }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); addFiles(Array.from(e.dataTransfer.files)); }}
        className={`block cursor-pointer rounded-md border-2 border-dashed px-6 py-14 text-center transition-colors ${over ? "border-gold bg-raised" : "border-line bg-surface hover:border-muted"}`}
      >
        <span className="font-serif text-3xl block">Drop field photos here</span>
        <span className="block text-muted mt-2">or click to choose. JPG, PNG or WEBP, up to 25 MB each.</span>
        <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden
          onChange={(e) => { addFiles(Array.from(e.target.files || [])); e.target.value = ""; }} />
      </label>

      {widgetCfg?.enabled && (
        <div className="flex flex-wrap items-center gap-4 mt-4 border border-line rounded-md bg-surface px-4 py-3">
          <button type="button" onClick={openWidget} className={btnGhost}>Upload with Cloudinary</button>
          <p className="text-sm text-muted flex-1 min-w-[240px]">
            Upload straight to Cloudinary from a phone, the camera or a web link. ImpactProof then fetches the stored original, confirms it
            matches Cloudinary&apos;s checksum and runs the same checks.
          </p>
          {widgetErr && <p className="text-bad text-sm w-full">{widgetErr}</p>}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4 mt-5 text-sm text-muted">
        <p><b className="text-paper">Keep the original files.</b> Photos sent through WhatsApp lose their GPS and date, so they can only be marked Unverifiable. Copy them by cable, Google Photos download or email attachment.</p>
        <p><b className="text-paper">Taking new photos?</b> Use the <Link href="/capture" className="text-gold underline underline-offset-2">in-app camera</Link>. It records live GPS and the time at capture, which is the strongest evidence.</p>
      </div>

      {rows.length > 0 && (
        <section className="mt-10">
          <h2 className="t-title mb-3">Checked {done} of {rows.length}</h2>
          <ul className="divide-y divide-line border-y border-line">
            {rows.map((r, i) => (
              <li key={i} className="flex items-center gap-4 py-3">
                {r.evidence?.thumb_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={r.evidence.thumb_url} alt="" className="w-16 h-12 object-cover rounded-sm" />
                ) : <span className="w-16 h-12 bg-raised rounded-sm" />}
                <div className="min-w-0 flex-1">
                  <div className="truncate">{r.name}</div>
                  {r.evidence && <div className="text-xs text-muted truncate">{r.evidence.headline_reasons[0] || r.evidence.activity || ""}</div>}
                  {r.error && <div className="text-xs text-bad">{r.error}</div>}
                </div>
                <div className="text-sm shrink-0">
                  {r.state === "waiting" && <span className="text-faint">Waiting</span>}
                  {r.state === "checking" && <span className="text-muted animate-pulse">Checking (10 to 30 s)…</span>}
                  {r.state === "error" && <span className="text-bad">Not added</span>}
                  {r.evidence && (
                    <Link href={`/evidence/${r.evidence.id}`} className="flex items-center gap-3">
                      <span className="font-mono underline underline-offset-2">{r.evidence.code}</span>
                      <StatusTag status={r.evidence.integrity_status} />
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
