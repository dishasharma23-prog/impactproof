"use client";
import { useState } from "react";
import { postJSON } from "@/lib/api";

const field = "w-full bg-surface border border-line rounded-xl px-4 py-3 text-paper placeholder:text-faint focus:border-gold focus:outline-none";

export default function EarlyAccessForm() {
  const [f, setF] = useState({ name: "", organisation: "", email: "", role: "", message: "" });
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [err, setErr] = useState("");
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending"); setErr("");
    try { await postJSON("/api/early-access", f); setState("done"); }
    catch (x: any) { setErr(x.message); setState("idle"); }
  }

  if (state === "done") {
    return (
      <div className="border border-line rounded-2xl p-8 bg-surface">
        <p className="font-serif text-3xl">Thank you, {f.name.split(" ")[0]}.</p>
        <p className="text-muted mt-2">We&apos;ll be in touch about piloting ImpactProof with {f.organisation}.</p>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="grid sm:grid-cols-2 gap-4">
      <input className={field} placeholder="Your name" value={f.name} onChange={set("name")} aria-label="Your name" required />
      <input className={field} placeholder="Organisation" value={f.organisation} onChange={set("organisation")} aria-label="Organisation" required />
      <input className={field} type="email" placeholder="Email" value={f.email} onChange={set("email")} aria-label="Email" required />
      <input className={field} placeholder="Role, e.g. programme lead, CSR manager" value={f.role} onChange={set("role")} aria-label="Role" />
      <textarea className={`${field} sm:col-span-2`} rows={3} placeholder="How do you report impact to donors today? (optional)"
        value={f.message} onChange={set("message")} aria-label="How you report impact today" />
      <div className="sm:col-span-2 flex flex-wrap items-center gap-4">
        <button disabled={state === "sending"} className="bg-paper text-ink font-medium px-7 py-3 rounded-full hover:bg-gold transition-colors disabled:opacity-50">
          {state === "sending" ? "Sending…" : "Request early access"}
        </button>
        {err && <span className="text-bad text-sm">{err}</span>}
      </div>
    </form>
  );
}
