"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import ReportView from "@/components/ReportView";
import { api } from "@/lib/api";

export default function VerifyPage() {
  const { token } = useParams<{ token: string }>();
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api(`/api/public/claims/${token}`).then(setR).catch((e) => setError(e.message)); }, [token]);

  return (
    <div className="min-h-screen bg-ink px-4 py-8 md:py-14">
      <div className="max-w-[900px] mx-auto mb-6 flex flex-wrap justify-between items-center gap-3">
        <span className="flex items-baseline gap-4"><span className="text-paper font-serif text-[19px] uppercase">ImpactProof</span><span className="t-label">Public verification</span></span>
        <span className="text-sm text-muted font-light">Independent checks on every photo behind this claim</span>
      </div>
      {error ? (
        <div className="max-w-[900px] mx-auto border-y border-line py-16 text-center">
          <h1 className="font-serif text-3xl">Link not valid</h1>
          <p className="text-muted mt-2">{error}</p>
        </div>
      ) : !r ? (
        <p className="text-center text-muted py-20 animate-pulse">Loading verification…</p>
      ) : (
        <ReportView r={r} isPublic />
      )}
    </div>
  );
}
