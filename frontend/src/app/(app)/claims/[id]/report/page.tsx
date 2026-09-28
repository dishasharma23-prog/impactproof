"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import ReportView from "@/components/ReportView";
import { btn, btnGhost, ErrorBox, Loading } from "@/components/ui";
import { API, api } from "@/lib/api";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => { api(`/api/claims/${id}/report`).then(setR).catch((e) => setError(e.message)); }, [id]);

  if (error) return <ErrorBox message={error} />;
  if (!r) return <Loading label="Assembling the impact brief…" />;
  const publicPath = `/verify/${r.verify_url.split("/verify/")[1]}`;

  return (
    <div>
      <div className="no-print flex flex-wrap justify-between items-end gap-4 mb-8 max-w-[900px] mx-auto">
        <div>
          <Link href={`/claims/${id}`} className="text-sm text-muted hover:text-paper">Back to the claim</Link>
          <h1 className="font-serif text-3xl mt-1">Impact brief</h1>
          <p className="text-sm text-muted mt-1">Only corroborated photos support the claim. The QR code opens a public page where anyone can check them.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button className={btnGhost} onClick={() => { navigator.clipboard?.writeText(r.verify_url); setCopied(true); setTimeout(() => setCopied(false), 2000); }}>
            {copied ? "Link copied" : "Copy public link"}
          </button>
          <Link href={publicPath} className={btnGhost} target="_blank">Open public page</Link>
          <button className={btn} onClick={() => window.print()}>Print or save as PDF</button>
        </div>
      </div>
      <ReportView r={r} qrSrc={`${API}/api/claims/${id}/qr.svg`} />
    </div>
  );
}
