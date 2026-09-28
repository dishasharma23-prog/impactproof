"use client";
import { fmtDate, fmtUtc, STATUS_LABEL } from "@/lib/api";
import { SdgBadge } from "./Sdg";

const PAPER_STATUS: Record<string, string> = {
  CORROBORATED: "#1f7a4f", NEEDS_REVIEW: "#9a6300", SUSPICIOUS: "#b3321e", UNVERIFIABLE: "#5d6560", REJECTED: "#8a2f22",
};
const SUPPORT_PAPER: Record<string, string> = { SUPPORTED: "#1f7a4f", PARTIAL: "#9a6300", CONTESTED: "#b3321e", UNSUPPORTED: "#5d6560" };
const MARK: Record<string, string> = { pass: "✓", warn: "!", fail: "✕", unavailable: "–" };

export default function ReportView({ r, isPublic = false, qrSrc }: { r: any; isPublic?: boolean; qrSrc?: string }) {
  const link = (id: number) => (isPublic ? undefined : `/evidence/${id}`);
  return (
    <article className="paper-scope bg-[#f6f4ee] text-[#1b1d1c] rounded-sm print-plain px-6 py-10 md:px-14 md:py-14 max-w-[900px] mx-auto">
      <header className="flex flex-wrap justify-between gap-8 border-b border-[#d9d5ca] pb-8">
        <div className="max-w-[560px]">
          <p className="t-label !text-[#6b6f6b]">What was claimed</p>
          <p className="t-meta text-[11px] uppercase text-[#6b6f6b] mt-3">{r.project_name}{r.project?.organization ? ` · ${r.project.organization}` : ""}</p>
          <h1 className="t-display !text-[clamp(2rem,4.2vw,3rem)] mt-3">&ldquo;{String(r.claim_text).replace(/\.$/, "")}.&rdquo;</h1>
          <p className="mt-6 t-title !text-[1.7rem]" style={{ color: SUPPORT_PAPER[r.support.state] }}>{r.support.label}</p>
          <p className="text-[15px] text-[#4b504c] mt-1">{isPublic ? (r.support.public_reason ?? r.support.reason) : r.support.reason}</p>
        </div>
        {qrSrc && (
          <div className="text-center shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={qrSrc} alt="QR code linking to the public verification page" className="w-32 h-32 bg-white p-1.5 rounded-sm" />
            <p className="text-xs text-[#6b6f6b] mt-2 max-w-[140px]">Scan to check every photo behind this claim</p>
          </div>
        )}
      </header>

      <dl className="flex flex-wrap gap-x-12 gap-y-4 py-6 text-sm border-b border-[#d9d5ca]">
        <div><dt className="t-label !text-[10px] !text-[#6b6f6b] mb-1">Supporting photos</dt><dd className="t-num text-3xl">{r.supporting.length}</dd></div>
        <div><dt className="t-label !text-[10px] !text-[#6b6f6b] mb-1">Not used</dt><dd className="t-num text-3xl">{r.flagged.length}</dd></div>
        {r.period && <div><dt className="t-label !text-[10px] !text-[#6b6f6b] mb-1">Evidence dates</dt><dd className="t-num text-3xl">{fmtDate(r.period[0])} to {fmtDate(r.period[1])}</dd></div>}
        <div><dt className="t-label !text-[10px] !text-[#6b6f6b] mb-1">Generated</dt><dd className="t-num text-3xl">{fmtUtc(r.generated_at, false)}</dd></div>
      </dl>

      <section className="mt-10">
        <Q q="What evidence supports it" title="Field evidence" />
        {r.supporting.length === 0 && <p className="text-[#6b6f6b] mt-2">No corroborated photo supports this claim yet.</p>}
        <div className="grid sm:grid-cols-2 gap-x-8 gap-y-10 mt-6">
          {r.supporting.map((e: any) => <EvidenceBlock key={e.id} e={e} href={link(e.id)} />)}
        </div>
      </section>

      {r.pairs.length > 0 && (
        <section className="mt-14">
          <Q q="What changed" title="Before and after" />
          {r.pairs.map((p: any) => (
            <div key={p.key} className="mt-6">
              <div className="grid grid-cols-2 gap-3">
                <figure>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={p.before_image} alt="Before" className="w-full aspect-[4/3] object-cover rounded-sm" />
                  <figcaption className="text-xs text-[#6b6f6b] mt-1">Before, EV-{String(p.before).padStart(4, "0")}</figcaption>
                </figure>
                <figure>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={p.after_image} alt="After" className="w-full aspect-[4/3] object-cover rounded-sm" />
                  <figcaption className="text-xs text-[#6b6f6b] mt-1">After, EV-{String(p.after).padStart(4, "0")}, {p.gap_days >= 1 ? `${p.gap_days} days` : `${p.gap_hours} hours`} later</figcaption>
                </figure>
              </div>
              {(p.description?.change_summary || p.signal_changes.length > 0) && (
                <p className="text-[15px] mt-3">{p.description?.change_summary || p.signal_changes.join("; ") + "."}</p>
              )}
            </div>
          ))}
        </section>
      )}

      <section className="mt-14">
        <Q q="Also linked, not counted" title="Evidence not used" />
        <p className="text-sm text-[#6b6f6b] mt-1">Photos linked to this claim that failed or could not pass the checks. They are listed, not hidden.</p>
        {r.flagged.length === 0 ? <p className="mt-3 text-[15px]">None. Every linked photo was corroborated.</p> : (
          <ul className="mt-4 divide-y divide-[#d9d5ca] border-y border-[#d9d5ca]">
            {r.flagged.map((e: any) => (
              <li key={e.id} className="py-3 flex gap-4">
                {e.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={e.image_url} alt="" className="w-20 h-15 object-cover rounded-sm shrink-0 opacity-80" />
                )}
                <div className="text-sm">
                  <span className="font-mono">{e.code}</span>{" "}
                  <b style={{ color: PAPER_STATUS[e.status] }}>{STATUS_LABEL[e.status]}</b>
                  <ul className="mt-1 text-[#4b504c] space-y-0.5">{e.reasons.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {r.coverage?.site_count > 0 && (
        <section className="mt-14">
          <Q q="Where it happened" title="Sites" />
          <p className="text-[15px] mt-1">{r.coverage.summary}</p>
          <ul className="mt-3 text-sm grid sm:grid-cols-2 gap-x-8 gap-y-1">
            {r.coverage.sites.map((s: any) => (
              <li key={s.site_id} className="flex justify-between border-b border-[#e3dfd5] py-1.5">
                <span style={{ color: s.stale ? "#9a6300" : undefined }}>{s.site_name}</span>
                <span className="text-[#6b6f6b]">{s.last_evidence ? `last ${fmtDate(s.last_evidence)}` : "no evidence"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {r.sdgs?.length > 0 && (
        <section className="mt-14">
          <Q q="What impact it supports" title="Sustainable Development Goals" />
          <p className="text-sm text-[#6b6f6b] mt-1">Verified photos supporting each UN goal, as tagged from what is visible in them.</p>
          <div className="flex flex-wrap gap-2 mt-4">{r.sdgs.map((g: any) => <SdgBadge key={g.number} g={g} count={g.photos} />)}</div>
        </section>
      )}

      <section className="mt-14">
        <Q q="How it was verified" title="The method" />
        <p className="text-sm text-[#4b504c] mt-2 leading-relaxed max-w-[75ch]">{r.method}</p>
        {isPublic && <p className="text-xs text-[#6b6f6b] mt-3">Faces are blurred and locations rounded on this public page. Originals are kept unaltered by the organisation.</p>}
      </section>
    </article>
  );
}

function Q({ q, title }: { q: string; title: string }) {
  return (
    <div className="border-t border-[#d9d5ca] pt-4">
      <p className="t-label !text-[#6b6f6b]">{q}</p>
      <h2 className="t-title mt-2">{title}</h2>
    </div>
  );
}

function EvidenceBlock({ e, href }: { e: any; href?: string }) {
  const img = e.image_url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={e.image_url} alt={e.description || e.code} className="w-full aspect-[4/3] object-cover" />
  ) : (
    <div className="w-full aspect-[4/3] rounded-sm bg-[#ebe7dd] grid place-items-center text-center p-4 text-sm text-[#6b6f6b]">
      Photo hidden: faces can only be blurred when the photo is stored on Cloudinary.
    </div>
  );
  const shown = e.checks.filter((c: any) => c.status !== "unavailable");
  return (
    <div className="break-inside-avoid">
      {href ? <a href={href}>{img}</a> : img}
      <div className="flex justify-between items-baseline mt-3">
        <span className="t-meta text-[12px]">FIELD RECORD / {String(e.id).padStart(4, "0")}</span>
        <span className="text-sm" style={{ color: PAPER_STATUS[e.status] }}>{STATUS_LABEL[e.status]}{e.score != null ? `, score ${e.score}` : ""}</span>
      </div>
      <p className="text-sm text-[#4b504c] mt-1">
        {e.capture_source === "in_app" ? "Taken with the ImpactProof camera" : "Uploaded photo"}
        {e.capture_time ? `, ${fmtDate(e.capture_time, true)}` : ""}{e.site_name ? `, ${e.site_name}` : ""}.
      </p>
      {e.description && <p className="text-sm mt-1">{e.description}</p>}
      <ul className="mt-3 space-y-1 text-[13px]">
        {shown.map((c: any) => (
          <li key={c.label} className="flex gap-2">
            <span className="w-4 shrink-0 font-bold" style={{ color: c.status === "pass" ? "#1f7a4f" : c.status === "warn" ? "#9a6300" : "#b3321e" }}>{MARK[c.status]}</span>
            <span><b className="font-medium">{c.label}.</b> <span className="text-[#4b504c]">{c.reason}</span></span>
          </li>
        ))}
      </ul>
      {e.seal?.sha256 && <p className="text-[11px] text-[#8a8e8a] mt-2 font-mono break-all">SHA-256 {e.seal.sha256}</p>}
    </div>
  );
}

