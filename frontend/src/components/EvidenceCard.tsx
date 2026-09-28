import Link from "next/link";
import { EvidenceLight } from "@/lib/api";
import { StatusTag } from "./ui";

export default function EvidenceCard({ e }: { e: EvidenceLight }) {
  return (
    <Link href={`/evidence/${e.id}`} className="group block">
      <div className="aspect-[4/3] overflow-hidden rounded-lg bg-raised ring-1 ring-line group-hover:ring-2 group-hover:ring-paper/70 transition relative">
        {e.thumb_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={e.thumb_url} alt={e.activity || e.original_filename} loading="lazy" className="w-full h-full object-cover" />
        )}
        {e.capture_source === "in_app" && (
          <span className="absolute top-2 left-2 bg-ink/85 text-[11px] px-1.5 py-0.5 rounded-sm text-paper">Live capture</span>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 mt-2">
        <span className="font-mono text-[13px] text-paper">{e.code}</span>
        <StatusTag status={e.integrity_status} />
      </div>
      <div className="text-[13px] text-muted truncate">{e.activity || e.original_filename}</div>
    </Link>
  );
}
