"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { API, api } from "@/lib/api";

const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;
const STATUS: Record<string, [string, string]> = {
  pending: ["Awaiting the organisation's confirmation", "#a36a00"],
  confirmed: ["Payment confirmed by the organisation", "#1f7a4d"],
  rejected: ["The organisation could not match this payment", "#b3261e"],
};

export default function ReceiptPage() {
  const { token } = useParams<{ token: string }>();
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api(`/api/public/receipts/${token}`).then(setR).catch((e) => setError(e.message)); }, [token]);

  return (
    <div className="min-h-screen bg-ink px-4 py-8 md:py-14">
      <div className="max-w-[760px] mx-auto mb-6 flex flex-wrap justify-between items-center gap-3">
        <span className="flex items-baseline gap-4"><span className="text-paper font-serif text-[19px] uppercase">ImpactProof</span><span className="t-label">Donation receipt</span></span>
        {r && <button onClick={() => window.print()} className="text-sm text-muted hover:text-paper print:hidden">Print or save as PDF</button>}
      </div>
      {error ? (
        <div className="max-w-[760px] mx-auto border-y border-line py-16 text-center"><h1 className="font-serif text-3xl">Receipt not found</h1><p className="text-muted mt-2">{error}</p></div>
      ) : !r ? (
        <p className="text-center text-muted py-20 animate-pulse">Loading receipt…</p>
      ) : (
        <article className="paper-scope bg-[#f6f4ee] text-[#1b1d1c] rounded-sm px-6 py-10 md:px-12 md:py-12 max-w-[760px] mx-auto print-plain">
          <div className="flex flex-wrap justify-between gap-8">
            <div>
              <p className="font-mono text-[11px] tracking-[.18em] uppercase text-[#6b6b66]">Thank you, {r.donation.donor_name}</p>
              <p className="font-serif text-6xl mt-3">{inr(r.donation.amount)}</p>
              <p className="mt-3 text-sm font-medium" style={{ color: STATUS[r.donation.status]?.[1] }}>● {STATUS[r.donation.status]?.[0]}</p>
              <p className="font-mono text-[11px] uppercase text-[#6b6b66] mt-2">
                {new Date(r.donation.created_at + "Z").toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                {r.donation.method === "demo" ? " · demo payment" : r.utr_last4 ? ` · UPI ref ••••${r.utr_last4}` : ""}
              </p>
            </div>
            <figure className="text-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`${API}/api/public/receipts/${token}/qr.svg`} alt="QR code for this receipt" className="w-32 h-32" />
              <figcaption className="text-[11px] text-[#6b6b66] mt-1">Scan to check this receipt</figcaption>
            </figure>
          </div>

          <hr className="my-8 border-[#dcd8cc]" />
          <p className="font-mono text-[11px] tracking-[.18em] uppercase text-[#6b6b66]">You funded</p>
          <h1 className="font-serif text-3xl mt-2">&ldquo;{r.claim.text.replace(/\.$/, "")}.&rdquo;</h1>
          <p className="text-sm text-[#55554f] mt-1">{[r.claim.organization, r.claim.project].filter(Boolean).join(" · ")}</p>

          <div className="mt-6 border-l-4 pl-4 py-1" style={{ borderColor: r.proof.state === "SUPPORTED" ? "#1f7a4d" : "#a36a00" }}>
            <p className="font-medium">{r.proof.state === "SUPPORTED" ? "Released on proof" : "Held until proven"}: the claim is {r.proof.label.toLowerCase()}.</p>
            <p className="text-sm text-[#55554f] mt-1">Every photo behind this claim was checked for place, date, reuse, content credentials, metadata, what it shows and the weather that day. You can inspect them yourself.</p>
          </div>
          <Link href={`/verify/${r.claim.verify_token}`} className="inline-block mt-6 rounded-full px-6 py-3 bg-[#1b1d1c] text-[#f6f4ee] text-sm print:hidden">See the verified photos →</Link>
          <p className="text-[11px] text-[#6b6b66] mt-8">ImpactProof records pledges and the organisation&apos;s confirmation. The payment itself goes directly to the organisation by UPI.</p>
        </article>
      )}
    </div>
  );
}
