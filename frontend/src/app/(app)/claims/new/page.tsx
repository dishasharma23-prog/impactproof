"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { btn } from "@/components/ui";
import { postJSON } from "@/lib/api";
import { useProject } from "@/lib/project";

export default function NewClaimPage() {
  const { project } = useProject();
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t) return setError("Write the claim first.");
    setBusy(true);
    try {
      const c = await postJSON<{ id: number }>("/api/claims", { text: t, project_id: project?.id });
      router.push(`/claims/${c.id}`);
    } catch (err: any) { setError(err.message); setBusy(false); }
  }

  return (
    <div className="max-w-3xl">
      <Link href="/claims" className="text-sm text-muted hover:text-paper">Claims</Link>
      <h1 className="font-serif text-4xl mt-1 mb-2">New claim</h1>
      <p className="text-muted mb-8">State one specific, checkable thing. Numbers, places and dates make a claim easier to support.</p>
      <form onSubmit={submit}>
        <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} disabled={busy} maxLength={2000}
          placeholder="e.g. 60 volunteers cleared litter from the north bank of the river between 1 and 20 September."
          className="w-full bg-transparent border-b border-line text-2xl font-serif py-3 focus:outline-none focus:border-gold resize-none placeholder:text-faint" />
        <div className="flex justify-between text-sm mt-2"><span className="text-bad">{error}</span><span className="text-faint">{text.length} / 2000</span></div>
        <button className={`${btn} mt-6`} disabled={busy}>{busy ? "Creating…" : "Create claim"}</button>
      </form>
    </div>
  );
}
