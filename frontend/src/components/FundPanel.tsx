"use client";
/** "Fund this verified work": donors pay the NGO directly by UPI and get a receipt tied to the proof. */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { API, api, postJSON } from "@/lib/api";

interface Funding {
  raised: number; donors: number; pending: number; released: number; held: number;
  support_state: string; support_label: string; upi: boolean; payee: string | null;
}
const AMOUNTS = [100, 500, 1000, 5000];
const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export default function FundPanel({ token }: { token: string }) {
  const router = useRouter();
  const [f, setF] = useState<Funding | null>(null);
  const [amount, setAmount] = useState(500);
  const [custom, setCustom] = useState("");
  const [step, setStep] = useState<"pick" | "pay">("pick");
  const [name, setName] = useState("");
  const [utr, setUtr] = useState("");
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { api<Funding>(`/api/public/claims/${token}/funding`).then(setF).catch(() => {}); }, [token]);
  const value = custom ? Math.floor(Number(custom)) : amount;
  const valid = Number.isFinite(value) && value >= 1 && value <= 1_000_000;

  async function next() {
    setErr("");
    if (!valid) return setErr("Choose an amount between ₹1 and ₹10,00,000.");
    if (f?.upi) {
      const r = await api<{ link: string }>(`/api/public/claims/${token}/upi-link?amount=${value}`).catch((e) => { setErr(e.message); return null; });
      if (!r) return;
      setLink(r.link);
    }
    setStep("pay");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const r = await postJSON<{ receipt_token: string }>(`/api/public/claims/${token}/donations`,
        { donor_name: name, amount: value, utr: f?.upi ? utr : null });
      router.push(`/receipt/${r.receipt_token}`);
    } catch (x: any) { setErr(x.message); setBusy(false); }
  }

  if (!f) return null;
  const proven = f.support_state === "SUPPORTED";

  return (
    <section className="max-w-[900px] mx-auto mt-8 border border-line rounded-sm p-6 md:p-10">
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="max-w-[46ch]">
          <p className="t-label">Pay on proof</p>
          <h2 className="font-serif text-3xl mt-2">Fund this verified work</h2>
          <p className="text-muted mt-3 text-[15px] leading-relaxed">
            Your money goes straight to {f.payee || "the organisation"} and is tied to this claim. It counts as
            delivered only while independent checks support it, and your receipt links to the photos behind it.
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-x-8 gap-y-3 md:text-right">
          <div><dt className="t-label !text-[10px]">Raised</dt><dd className="t-num text-3xl">{inr(f.raised)}</dd></div>
          <div><dt className="t-label !text-[10px]">Donors</dt><dd className="t-num text-3xl">{f.donors}</dd></div>
          <div className="col-span-2"><dt className="t-label !text-[10px]">Status</dt>
            <dd className={`text-sm mt-1 ${proven ? "text-ok" : "text-review"}`}>{proven ? "Released on proof: the claim is supported" : "Held until the claim is supported by verified photos"}</dd></div>
        </dl>
      </div>

      {step === "pick" ? (
        <div className="mt-8">
          <div className="flex flex-wrap gap-2">
            {AMOUNTS.map((a) => (
              <button key={a} type="button" onClick={() => { setAmount(a); setCustom(""); }}
                className={`px-5 py-2.5 rounded-full border text-sm transition-colors ${!custom && amount === a ? "border-paper bg-paper text-ink" : "border-line hover:border-paper/60"}`}>{inr(a)}</button>
            ))}
            <input aria-label="Other amount in rupees" inputMode="numeric" placeholder="Other ₹" value={custom}
              onChange={(e) => setCustom(e.target.value.replace(/[^0-9]/g, ""))}
              className="w-28 px-4 py-2.5 rounded-full border border-line bg-transparent text-sm focus:outline-none focus:border-paper/60" />
          </div>
          <button type="button" onClick={next} disabled={!valid} className="mt-5 inline-flex items-center gap-2 rounded-full px-7 py-3 bg-paper text-ink font-medium disabled:opacity-40">
            Continue with {valid ? inr(value) : "an amount"} →
          </button>
          {!f.upi && <p className="text-xs text-faint mt-3">Demo mode: this organisation hasn&apos;t added a UPI ID yet, so no real money moves.</p>}
          {err && <p className="text-bad text-sm mt-3">{err}</p>}
        </div>
      ) : (
        <form onSubmit={submit} className="mt-8 grid md:grid-cols-[auto_1fr] gap-8 items-start">
          {f.upi ? (
            <div className="text-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`${API}/api/public/claims/${token}/upi.svg?amount=${value}`} alt={`UPI QR code for ${inr(value)}`} className="w-48 h-48 bg-white p-2 rounded" />
              <p className="t-meta text-[11px] text-muted mt-2 uppercase">Scan with any UPI app</p>
              <a href={link} className="md:hidden mt-3 inline-block rounded-full px-5 py-2.5 border border-paper text-sm">Open UPI app</a>
            </div>
          ) : (
            <div className="w-48 h-48 border border-dashed border-line rounded flex items-center justify-center text-center text-sm text-muted p-4">Demo payment: no money moves</div>
          )}
          <div className="space-y-4 max-w-md">
            <p className="text-[15px]">{f.upi ? <>Pay <b>{inr(value)}</b> to {f.payee}, then tell us who you are and your UPI reference number so the organisation can confirm it.</> : <>Record a demo pledge of <b>{inr(value)}</b> to see the receipt a donor gets.</>}</p>
            <div><label className="block t-label !text-paper/80 mb-2" htmlFor="dn">Your name</label>
              <input id="dn" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} className="w-full px-4 py-3 bg-transparent border border-line rounded-sm focus:outline-none focus:border-paper/60" /></div>
            {f.upi && (
              <div><label className="block t-label !text-paper/80 mb-2" htmlFor="du">UPI reference number (UTR)</label>
                <input id="du" required inputMode="numeric" value={utr} onChange={(e) => setUtr(e.target.value)} placeholder="12-digit number in your UPI app" className="w-full px-4 py-3 bg-transparent border border-line rounded-sm focus:outline-none focus:border-paper/60" /></div>
            )}
            {err && <p className="text-bad text-sm">{err}</p>}
            <div className="flex gap-3 items-center">
              <button disabled={busy} className="rounded-full px-7 py-3 bg-paper text-ink font-medium disabled:opacity-50">{busy ? "Saving…" : f.upi ? "I've paid: get my receipt" : "Record demo pledge"}</button>
              <button type="button" onClick={() => setStep("pick")} className="text-sm text-muted hover:text-paper">Back</button>
            </div>
          </div>
        </form>
      )}
    </section>
  );
}
