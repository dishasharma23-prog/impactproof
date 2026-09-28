"use client";
import { useCallback, useEffect, useState } from "react";
import { SectionHeading } from "@/components/system";
import { btn, btnGhost, ErrorBox, input, label, Loading, PageHeader, Toast } from "@/components/ui";
import { api, fmtUtc, postJSON } from "@/lib/api";
import { useProject } from "@/lib/project";

interface Volunteer {
  id: number; name: string; phone: string; phone_masked: string; active: boolean; paired: boolean;
  device_name: string | null; code_pending: boolean; paired_at: string | null; last_upload_at: string | null; uploads: number;
}

export default function VolunteersPage() {
  const { project } = useProject();
  const [rows, setRows] = useState<Volunteer[] | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState<{ name: string; phone: string; code: string } | null>(null);
  const [toast, setToast] = useState("");
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 3000); };

  const load = useCallback(() => {
    if (!project) return;
    api<Volunteer[]>(`/api/volunteers?project_id=${project.id}`).then(setRows).catch((e) => setError(e.message));
  }, [project]);
  useEffect(() => { load(); }, [load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!project) return;
    setBusy(true); setError("");
    try {
      const v = await postJSON<Volunteer & { pairing_code: string }>("/api/volunteers", { name, phone, project_id: project.id });
      setCode({ name: v.name, phone: v.phone, code: v.pairing_code });
      setName(""); setPhone(""); load();
    } catch (x: any) { setError(x.message); }
    setBusy(false);
  }
  async function newCode(v: Volunteer) {
    const r = await postJSON<Volunteer & { pairing_code: string }>(`/api/volunteers/${v.id}/code`, {});
    setCode({ name: r.name, phone: r.phone, code: r.pairing_code }); load();
  }
  async function remove(v: Volunteer) {
    if (!confirm(`Remove ${v.name}? Their device will no longer be able to upload.`)) return;
    await api(`/api/volunteers/${v.id}`, { method: "DELETE" }); load(); flash(`${v.name} removed`);
  }

  if (!project) return <Loading />;
  const active = (rows || []).filter((v) => v.active);

  return (
    <div>
      <Toast message={toast} />
      <PageHeader label="Field team" title="Volunteers"
        lead="Register each volunteer by phone number. Their field device signs in once with the pairing code, and from then on every photo it uploads is attributed to them. Unregistered devices can't upload." />

      {error && <div className="mb-8"><ErrorBox message={error} /></div>}

      <section className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-14 gap-y-10 mb-16">
        <div>
          <SectionHeading label="Add a volunteer" />
          <form onSubmit={add} className="space-y-4 max-w-md">
            <div><label className={label} htmlFor="vn">Name</label>
              <input id="vn" className={input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Asha Verma" required /></div>
            <div><label className={label} htmlFor="vp">Phone number</label>
              <input id="vp" className={input} value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" placeholder="+91 98765 43210" required /></div>
            <button className={btn} disabled={busy}>{busy ? "Adding…" : "Add and create pairing code"}</button>
          </form>
        </div>
        <div>
          <SectionHeading label="Pairing code" />
          {code ? (
            <div>
              <p className="text-sm text-muted">For <b className="text-paper">{code.name}</b> · <span className="t-meta">{code.phone}</span></p>
              <p className="t-num text-7xl tracking-[.12em] mt-4">{code.code.slice(0, 3)} {code.code.slice(3)}</p>
              <ol className="mt-6 space-y-1.5 text-sm text-paper/85 list-decimal pl-5">
                <li>On the volunteer&apos;s phone, open the field app and go to <b>Sync</b>.</li>
                <li>Under <b>Volunteer</b>, enter this phone number and the code.</li>
                <li>The code works once and expires in 48 hours.</li>
              </ol>
              <p className="text-xs text-faint mt-4">Shown once. Send it to the volunteer directly; ImpactProof only keeps a hash of it.</p>
            </div>
          ) : <p className="text-sm text-muted">Add a volunteer, or make a new code for someone below. The code appears here.</p>}
        </div>
      </section>

      <section>
        <SectionHeading label={`Registered · ${active.length}`} />
        {!rows ? <Loading /> : active.length === 0 ? <p className="text-muted">No volunteers yet.</p> : (
          <ul className="border-t border-line">
            {active.map((v) => (
              <li key={v.id} className="grid grid-cols-1 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto] gap-x-6 gap-y-2 items-center py-4 border-b border-line">
                <div>
                  <p className="font-medium">{v.name}</p>
                  <p className="t-meta text-[12px] text-muted">{v.phone}</p>
                </div>
                <p className="t-meta text-[11px] uppercase text-faint">
                  {v.paired ? `Paired${v.device_name ? ` · ${v.device_name}` : ""}` : v.code_pending ? "Code sent · not paired yet" : "Not paired"}
                  {" · "}{v.uploads} upload{v.uploads === 1 ? "" : "s"}
                  {v.last_upload_at ? ` · last ${fmtUtc(v.last_upload_at)}` : ""}
                </p>
                <div className="flex gap-2 md:justify-end">
                  <button onClick={() => newCode(v)} className={`${btnGhost} !py-1.5 !px-4 !text-[13px]`}>{v.paired ? "Pair a new device" : "New code"}</button>
                  <button onClick={() => remove(v)} className="text-[13px] text-muted hover:text-bad px-2">Remove</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
