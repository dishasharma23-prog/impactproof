"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { btn, Empty, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api, fmtDate, Support, SUPPORT_COLOR } from "@/lib/api";
import { useProject } from "@/lib/project";

interface ClaimRow { id: number; text: string; created_at: string; evidence_count: number; support: Support }

export default function ClaimsPage() {
  const { project } = useProject();
  const [claims, setClaims] = useState<ClaimRow[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (project) api<ClaimRow[]>(`/api/claims?project_id=${project.id}`).then(setClaims).catch((e) => setError(e.message));
  }, [project]);

  if (error) return <ErrorBox message={error} />;
  if (!claims) return <Loading />;
  return (
    <div className="max-w-4xl">
      <PageHeader title="Claims" lead="A claim is a statement you will make to donors. It is only as strong as the corroborated evidence linked to it.">
        <Link href="/claims/new" className={btn}>New claim</Link>
      </PageHeader>
      {claims.length === 0 ? (
        <Empty title="No claims yet" action={{ href: "/claims/new", label: "Write a claim" }}>
          For example: “Volunteers cleared 400 kg of waste from the riverbank in September.”
        </Empty>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {claims.map((c) => (
            <li key={c.id}>
              <Link href={`/claims/${c.id}`} className="group block py-6">
                <h2 className="font-serif text-2xl leading-snug group-hover:text-gold transition-colors">{c.text}</h2>
                <div className="flex flex-wrap items-center gap-x-6 gap-y-1 mt-3 text-sm">
                  <span className="font-semibold" style={{ color: SUPPORT_COLOR[c.support.state] }}>{c.support.label}</span>
                  <span className="text-muted">{c.support.corroborated} of {c.evidence_count} linked photos corroborated</span>
                  <span className="text-faint">{fmtDate(c.created_at)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
