"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Empty, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api, fmtUtc } from "@/lib/api";

interface Req { id: number; name: string; organisation: string; email: string; role: string; message: string; created_at: string }

export default function SignupsPage() {
  const [rows, setRows] = useState<Req[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Req[]>("/api/early-access").then(setRows).catch((e) => setError(e.message)); }, []);
  if (error) return <ErrorBox message={error} />;
  if (!rows) return <Loading />;
  const orgs = new Set(rows.map((r) => r.organisation.trim().toLowerCase())).size;
  return (
    <div className="max-w-4xl">
      <PageHeader title="Early access"
        lead={<>{rows.length} request{rows.length === 1 ? "" : "s"} from {orgs} organisation{orgs === 1 ? "" : "s"}. People sign up with the form on the <Link href="/#early-access" className="text-gold underline underline-offset-2">landing page</Link>.</>} />
      {rows.length === 0 ? (
        <Empty title="No requests yet">Share the landing page with NGOs, your NSS unit or CSR contacts.</Empty>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {rows.map((r) => (
            <li key={r.id} className="py-4">
              <div className="flex flex-wrap justify-between gap-3">
                <span><b>{r.organisation}</b> <span className="text-muted">{r.name}{r.role ? `, ${r.role}` : ""}</span></span>
                <span className="text-xs text-faint">{fmtUtc(r.created_at)}</span>
              </div>
              <a href={`mailto:${r.email}`} className="text-sm text-gold underline underline-offset-2">{r.email}</a>
              {r.message && <p className="text-sm text-muted mt-1.5">“{r.message}”</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
