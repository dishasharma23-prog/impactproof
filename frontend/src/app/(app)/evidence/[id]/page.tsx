"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Fragment, useCallback, useEffect, useState } from "react";
import ClassificationBox from "@/components/ClassificationBox";
import DeletePanel from "@/components/DeletePanel";
import ReviewForm from "@/components/ReviewForm";
import { SdgBadge } from "@/components/Sdg";
import { Meta, recordNo, SectionHeading, Verdict } from "@/components/system";
import { btn, btnGhost, CheckLedger, ErrorBox, input, Loading, StatusTag, Toast } from "@/components/ui";
import { api, AuditEvent, EvidenceFull, fmtDate, fmtSize, fmtUtc, postJSON, Signal } from "@/lib/api";

const RANK: Record<string, number> = { fail: 0, warn: 1, pass: 2, unavailable: 3 };

export default function EvidencePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [e, setE] = useState<EvidenceFull | null>(null);
  const [history, setHistory] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 3200); };
  const load = useCallback(async () => {
    try {
      const [ev, h] = await Promise.all([api<EvidenceFull>(`/api/evidence/${id}`), api<AuditEvent[]>(`/api/evidence/${id}/history`)]);
      setE(ev);
      setHistory(h);
    } catch (err: any) {
      setError(err.message);
    }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorBox message={error} />;
  if (!e) return <Loading label="Loading evidence record…" />;

  const integ = e.integrity;
  const status = integ?.status || "UNVERIFIABLE";
  const signals: Signal[] = Object.values(integ?.signals || {}).filter((s: any) => s && s.key)
    .sort((a, b) => RANK[a.status] - RANK[b.status]);
  const ai = e.ai_analysis;
  const d = ai?.details || {};
  const overridden = integ && integ.engine_status && integ.engine_status !== integ.status;

  async function recheck() {
    setBusy(true);
    try {
      setE(await postJSON<EvidenceFull>(`/api/evidence/${id}/recheck`, {}));
      setHistory(await api(`/api/evidence/${id}/history`));
      flash("Checks run again");
    } catch (err: any) {
      flash(err.message);
    }
    setBusy(false);
  }

  return (
    <div>
      <Toast message={toast} />
      <header className="mb-10 pb-8 border-b border-line">
        <p className="t-label"><Link href="/dashboard" className="hover:text-paper">Field evidence</Link> / {recordNo(e)}</p>
        <h1 className="t-display mt-4 max-w-4xl">{d.activity ? d.activity.charAt(0).toUpperCase() + d.activity.slice(1) : e.code}</h1>
        <p className="t-meta text-[12px] text-faint uppercase mt-4 truncate" title={e.original_filename}>
          {e.code} · {e.capture_source === "in_app" ? "ImpactProof camera" : e.original_filename} · received {fmtUtc(e.uploaded_at)}
        </p>
      </header>

      <div className="grid lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] gap-x-14 gap-y-12 items-start">
        {/* LEFT: the photo and what is known about it */}
        <div className="space-y-14 min-w-0">
          <figure>
            <a href={e.image_url || "#"} target="_blank" rel="noreferrer" className="block photo">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={e.image_url || ""} alt={d.description || e.original_filename} className="!h-auto" />
            </a>
            <figcaption className="pt-5">
              <Meta cols={3} items={[
                { k: "Location", v: e.site_name || (e.latitude != null ? `${e.latitude.toFixed(4)}, ${e.longitude!.toFixed(4)}` : "Not in file") },
                { k: "Date", v: e.capture_time ? new Date(e.capture_time).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "Not in file" },
                { k: "Time", v: e.capture_time ? new Date(e.capture_time).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "—" },
                { k: "Weather", v: e.weather && !e.weather.error ? `${e.weather.precip_24h_mm} mm rain / 24 h` : "No record" },
                { k: "Captured by", v: e.captured_by ? `${e.captured_by.name} · ${e.captured_by.phone_masked}` : e.capture_source === "in_app" ? "ImpactProof camera" : e.software === "ImpactProof Field" ? "Field app, offline" : (e.device_info || "File upload") },
                { k: "Status", v: <Verdict status={status} className="!text-[12px]" /> },
              ]} />
            </figcaption>
          </figure>

          {e.duplicate_matches.length > 0 && (
            <section>
              <SectionHeading label="Visually similar evidence" className="!mb-2" />
              <p className="text-sm text-muted mb-4">
                Compared by perceptual hash: 0 bits different means the same picture, up to 10 means a near-copy
                (cropped, resized or re-saved).
              </p>
              <div className="grid grid-cols-2 gap-4">
                <figure>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={e.thumb_url || ""} alt="" className="w-full aspect-[4/3] object-cover outline outline-1 outline-paper/60" />
                  <figcaption className="text-sm mt-2"><b className="font-mono">{e.code}</b> (this one)<br />
                    <span className="text-muted">{e.capture_time ? `Taken ${fmtDate(e.capture_time)}` : "No capture date"}</span></figcaption>
                </figure>
                {e.duplicate_matches.slice(0, 1).map((m) => (
                  <figure key={m.id}>
                    <Link href={`/evidence/${m.id}`}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={m.thumb_url || ""} alt="" className="w-full aspect-[4/3] object-cover hover:opacity-90" />
                    </Link>
                    <figcaption className="text-sm mt-2"><Link href={`/evidence/${m.id}`} className="font-mono font-bold underline underline-offset-2">{m.code}</Link>
                      {m.status && <StatusTag status={m.status} className="ml-2" />}<br />
                      <span className="text-muted">
                        {m.project_id !== e.project_id && m.project_name ? `${m.project_name}, ` : ""}{m.captured_at ? `taken ${fmtDate(m.captured_at)}` : "no capture date"}.{" "}
                        {m.distance} of 64 bits different{m.same_file ? ", identical file" : ""}.
                      </span>
                    </figcaption>
                  </figure>
                ))}
              </div>
              {e.duplicate_matches.length > 1 && (
                <p className="text-sm text-muted mt-3">Also similar:{" "}
                  {e.duplicate_matches.slice(1).map((m, i) => (
                    <span key={m.id}>{i > 0 && ", "}<Link href={`/evidence/${m.id}`} className="underline font-mono">{m.code}</Link></span>
                  ))}
                </p>
              )}
            </section>
          )}

          <section>
            <SectionHeading label="What the photo shows" />
            {ai ? (
              <>
                <ul className="list-disc pl-5 space-y-1.5 text-[15px] leading-relaxed marker:text-faint">
                  {ai.observations.map((o, i) => <li key={i}>{o}</li>)}
                </ul>
                <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 mt-6 text-sm">
                  {d.activity && <><dt className="t-label !text-[10px] pt-[3px]">Main activity</dt><dd>{d.activity}</dd></>}
                  {d.people_count_estimate != null && <><dt className="t-label !text-[10px] pt-[3px]">People</dt><dd>about {d.people_count_estimate} <span className="text-faint">(AI estimate)</span></dd></>}
                  {d.sapling_count_estimate != null && <><dt className="t-label !text-[10px] pt-[3px]">Saplings</dt><dd>about {d.sapling_count_estimate} <span className="text-faint">(AI estimate)</span></dd></>}
                  {(d.visible_text || []).length > 0 && <><dt className="t-label !text-[10px] pt-[3px]">Readable text</dt>
                    <dd className="flex flex-wrap gap-1.5">{d.visible_text.map((t: string, i: number) => <span key={i} className="font-mono text-[13px] bg-raised px-1.5 py-0.5 rounded-sm">{t}</span>)}</dd></>}
                  {(d.comparable_details || []).length > 0 && <><dt className="t-label !text-[10px] pt-[3px]">Fixed landmarks</dt><dd>{d.comparable_details.join(", ")}</dd></>}
                </dl>
                {(d.tags || []).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-5">{d.tags.map((t: string) => <span key={t} className="text-xs bg-raised text-muted rounded-full px-2.5 py-1">{t}</span>)}</div>
                )}
                {e.sdgs.length > 0 && (
                  <div className="mt-6">
                    <div className="text-sm text-muted mb-2">Sustainable Development Goals shown</div>
                    <div className="flex flex-wrap gap-2">{e.sdgs.map((g) => <SdgBadge key={g.number} g={g} size="sm" />)}</div>
                    {e.sdg_reason && <p className="text-sm text-muted mt-2">{e.sdg_reason}</p>}
                  </div>
                )}
                <p className="text-xs text-faint mt-5">Described by {ai.provider === "gemini" ? "Gemini" : ai.provider}. The AI only describes what is visible; it does not decide the verdict.</p>
              </>
            ) : (
              <p className="text-muted">{e.ai_error ? `AI analysis failed: ${e.ai_error}` : "AI analysis has not run for this photo."}</p>
            )}
          </section>

          <section>
            <SectionHeading label="Source" />
            <dl className="grid grid-cols-[max-content_1fr] gap-x-8 gap-y-2.5 text-sm">
              <dt className="t-label !text-[10px] pt-[3px]">Captured</dt><dd>{e.capture_time ? fmtDate(e.capture_time, true) : <Missing />}</dd>
              <dt className="t-label !text-[10px] pt-[3px]">Location</dt><dd>{e.latitude != null ? `${e.latitude.toFixed(5)}, ${e.longitude!.toFixed(5)}` : <Missing />}
                {e.capture_meta?.gps_accuracy_m != null && <span className="text-muted"> (±{Math.round(e.capture_meta.gps_accuracy_m)} m, live GPS)</span>}</dd>
              <dt className="t-label !text-[10px] pt-[3px]">Device</dt><dd>{e.device_info || <Missing />}</dd>
              <dt className="t-label !text-[10px] pt-[3px]">Software</dt><dd>{e.software || <Missing />}</dd>
              <dt className="t-label !text-[10px] pt-[3px]">Size</dt><dd>{e.width ? `${e.width} × ${e.height} px` : <Missing />}{e.file_size ? `, ${fmtSize(e.file_size)}` : ""}</dd>
              {e.weather && !e.weather.error && <><dt className="t-label !text-[10px] pt-[3px]">Weather then</dt>
                <dd>{e.weather.precip_24h_mm} mm rain in the 24 h before{e.weather.cloud_cover_pct != null ? `, ${e.weather.cloud_cover_pct}% cloud` : ""} <span className="text-faint">(Open-Meteo)</span></dd></>}
            </dl>
          </section>

          <section>
            <SectionHeading label="Provenance · chain of custody" className="!mb-2" />
            <p className="text-sm text-muted mb-4">The exact bytes received were fingerprinted before anything else happened.</p>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-8 gap-y-2.5 text-sm">
              <dt className="t-label !text-[10px] pt-[3px]">SHA-256</dt><dd className="font-mono text-[12.5px] break-all">{e.seal.sha256 || <Missing text="Not recorded (added before sealing existed)" />}</dd>
              <dt className="t-label !text-[10px] pt-[3px]">Cloudinary copy</dt>
              <dd>{e.seal.cloudinary_matches === true ? <span className="text-ok">Matches the file received (MD5 {e.seal.md5?.slice(0, 12)}…)</span>
                : e.seal.cloudinary_matches === false ? <span className="text-bad">Does not match the file received</span>
                  : e.cloudinary_public_id ? "Stored, not compared" : <Missing text="Not on Cloudinary" />}</dd>
              {e.cloudinary_public_id && <><dt className="t-label !text-[10px] pt-[3px]">Cloudinary asset</dt>
                <dd className="font-mono text-[12.5px] break-all">{e.cloudinary_public_id}{e.seal.cloudinary_version ? ` (v${e.seal.cloudinary_version})` : ""}</dd></>}
              <dt className="t-label !text-[10px] pt-[3px]">Perceptual hash</dt><dd className="font-mono text-[12.5px]">{e.phash || <Missing />}{e.seal.cloudinary_phash ? `, Cloudinary ${e.seal.cloudinary_phash}` : ""}</dd>
              <dt className="t-label !text-[10px] pt-[3px]">Content credentials</dt><dd>{provenanceText(e)}</dd>
            </dl>
          </section>

          {e.cloudinary_record && <CloudinaryRecord r={e.cloudinary_record} />}

          <section>
            <SectionHeading label="Timeline" />
            <ol className="relative border-l border-line ml-1.5 space-y-5">
              {history.map((h) => (
                <li key={h.id} className="pl-5 relative">
                  <span className={`absolute -left-[4px] top-[7px] w-[7px] h-[7px] rounded-full ${h.action === "review" ? "bg-gold" : h.action === "verdict" ? "bg-teal" : "bg-faint"}`} />
                  <div className="text-sm [overflow-wrap:anywhere]">{h.summary}</div>
                  <div className="t-meta text-[11px] text-faint uppercase mt-0.5">{fmtUtc(h.created_at)} · {h.actor}</div>
                </li>
              ))}
              {history.length === 0 && <li className="pl-5 text-sm text-muted">No recorded events yet.</li>}
            </ol>
          </section>
        </div>

        {/* RIGHT: the verdict */}
        <div className="space-y-10 lg:sticky lg:top-24">
          <div className={`v-${status}`}>
            <p className="t-label mb-5">Verification</p>
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <span className="stamp stamp-press">{integ?.status_label || "Unverifiable"}</span>
              <div className="text-right">
                <div className="t-num text-6xl">{status === "UNVERIFIABLE" ? "–" : integ?.score ?? "–"}</div>
                <div className="t-meta text-[11px] text-faint uppercase mt-2">Trust score · {integ?.available ?? 0} of {integ?.total ?? 0} checks</div>
              </div>
            </div>
            {overridden && (
              <p className="text-sm mt-5 border-l-2 border-gold pl-3">
                The checks said <b>{integ!.engine_status_label}</b>. A reviewer {status === "REJECTED" ? "rejected" : "approved"} it:
                “{e.reviews?.[0]?.reason}” ({e.reviews?.[0]?.reviewer}).
              </p>
            )}
            <div className="mt-6"><CheckLedger signals={signals} /></div>
            <p className="text-xs text-faint mt-4 leading-relaxed">
              A dash means that check had no data. Missing data lowers the number of checks, not the score, and is never treated as proof of anything.
            </p>
          </div>

          <ClassificationBox e={e} onDone={(ev) => { setE(ev); api<AuditEvent[]>(`/api/evidence/${id}/history`).then(setHistory); flash("Gallery placement updated"); }} />

          <ReviewForm evidence={e} onDone={(ev) => { setE(ev); api<AuditEvent[]>(`/api/evidence/${id}/history`).then(setHistory); flash("Decision recorded"); }} />

          {status === "CORROBORATED" && e.cloudinary_public_id && <Campaign id={e.id} code={e.code} />}

          <div className="border-t border-line pt-5">
            <p className="t-label mb-3">Claims using this evidence</p>
            {e.claims?.length ? (
              <ul className="mt-2 space-y-1.5 text-sm">{e.claims.map((c) => <li key={c.id}><Link href={`/claims/${c.id}`} className="underline underline-offset-2">{c.text}</Link></li>)}</ul>
            ) : <p className="text-sm text-muted mt-1">Not linked to any claim yet.</p>}
            <div className="flex flex-wrap gap-3 mt-5">
              <button onClick={recheck} disabled={busy} className={btnGhost}>{busy ? "Running checks…" : "Run checks again"}</button>
              {e.latitude != null && signals.find((s) => s.key === "location")?.status !== "pass" && (
                <Link href={`/project?lat=${e.latitude}&lng=${e.longitude}`} className={btnGhost}>Add a site here</Link>
              )}
            </div>
          </div>

          <div className="border-t border-line pt-5">
            <p className="t-label mb-2">Delete</p>
            <p className="text-sm text-muted mt-1 mb-4">For test uploads or photos added by mistake.</p>
            <DeletePanel ids={[e.id]} label={`Delete ${e.code}`} onDone={() => router.push("/gallery?deleted=1")} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Missing({ text = "Not in file" }: { text?: string }) {
  return <span className="text-faint">{text}</span>;
}

function provenanceText(e: EvidenceFull) {
  const p = e.provenance;
  if (!p) return <Missing text="Not checked" />;
  const tools = p.tools?.length ? ` (${p.tools.join(", ")})` : "";
  switch (p.verdict) {
    case "ai_generated": return <span className="text-bad">Declares AI generation{tools}</span>;
    case "ai_edited": return <span className="text-review">Declares AI editing{tools}</span>;
    case "tampered": return <span className="text-bad">Present but broken: image changed after signing</span>;
    case "camera": return <span className="text-ok">Camera capture{tools}</span>;
    case "credentials_present": return <span>Present, no AI generation recorded{tools}</span>;
    default: return <Missing text="None attached" />;
  }
}

function Campaign({ id, code }: { id: number; code: string }) {
  const [caption, setCaption] = useState("");
  const [blur, setBlur] = useState(true);
  const [items, setItems] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function make() {
    setBusy(true); setErr("");
    try { setItems(await postJSON(`/api/evidence/${id}/campaign`, { caption, blur_faces: blur })); }
    catch (x: any) { setErr(x.message); }
    setBusy(false);
  }
  return (
    <div className="border-t border-line pt-5">
      <p className="t-label mb-2">Campaign images · Cloudinary</p>
      <p className="text-sm text-muted mt-1">Made by Cloudinary from this photo. The original is never changed, and every image names {code}.</p>
      <label className="block text-sm font-medium mt-4 mb-1.5" htmlFor="cap">Caption</label>
      <input id="cap" className={input} maxLength={120} value={caption} onChange={(x) => setCaption(x.target.value)} placeholder="e.g. 60 volunteers cleared the north bank" />
      <label className="flex items-center gap-2 text-sm mt-3"><input type="checkbox" checked={blur} onChange={(x) => setBlur(x.target.checked)} /> Blur faces</label>
      <button onClick={make} disabled={busy} className={`${btn} mt-4`}>{busy ? "Creating…" : "Create campaign images"}</button>
      {err && <p className="text-bad text-sm mt-2">{err}</p>}
      {items.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mt-5 items-start">
          {items.map((d) => (
            <a key={d.key} href={d.url} target="_blank" rel="noreferrer" className="block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={d.url} alt={d.label} className="w-full rounded-sm ring-1 ring-line" />
              <span className="block text-xs text-muted mt-1">{d.label}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function CloudinaryRecord({ r }: { r: NonNullable<EvidenceFull["cloudinary_record"]> }) {
  const labels: Record<string, string> = {
    ip_evidence_id: "Evidence ID", ip_trust_status: "Verdict", ip_trust_score: "Trust score", ip_project: "Project",
    ip_site: "Site", ip_captured_at: "Captured on", ip_sha256: "SHA-256", ip_sdgs: "Goals",
  };
  return (
    <section>
      <SectionHeading label="In Cloudinary" className="!mb-2" />
      <p className="text-sm text-muted mb-4">
        The verdict lives on the asset itself, so the Cloudinary Media Library can be searched and filtered by it.
        {r.structured_metadata === false && " Structured metadata isn't enabled on this account, so tags and context are used."}
      </p>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-8 gap-y-2.5 text-sm">
        {Object.entries(r.metadata).map(([k, v]) => (
          <Fragment key={k}><dt className="t-label !text-[10px] pt-[3px]">{labels[k] || k}</dt>
            <dd className={`[overflow-wrap:anywhere] ${k === "ip_sha256" ? "font-mono text-[12.5px]" : ""}`}>{Array.isArray(v) ? v.join(", ") : String(v)}</dd></Fragment>
        ))}
        <dt className="t-label !text-[10px] pt-[3px]">Tags</dt>
        <dd className="flex flex-wrap gap-1.5">{r.tags.map((t) => <span key={t} className="font-mono text-[12px] bg-raised px-1.5 py-0.5 rounded-sm">{t}</span>)}</dd>
        <dt className="t-label !text-[10px] pt-[3px]">Derived copies</dt>
        <dd className="space-x-4">
          {r.derived.thumbnail && <a className="underline underline-offset-2" href={r.derived.thumbnail} target="_blank" rel="noreferrer">Smart-cropped thumbnail</a>}
          {r.derived.public_copy && <a className="underline underline-offset-2" href={r.derived.public_copy} target="_blank" rel="noreferrer">Face-blurred public copy</a>}
        </dd>
      </dl>
    </section>
  );
}
