"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import ThemeToggle from "@/components/ThemeToggle";
import { useProject } from "@/lib/project";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/gallery", label: "Gallery" },
  { href: "/upload", label: "Add evidence" },
  { href: "/capture", label: "Camera" },
  { href: "/compare", label: "Before and after" },
  { href: "/review", label: "Review" },
  { href: "/claims", label: "Claims" },
  { href: "/project", label: "Project" },
  { href: "/volunteers", label: "Volunteers" },
  { href: "/signups", label: "Early access" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { projects, project, setProjectId, error } = useProject();
  const [health, setHealth] = useState<any>(null);
  const [reviewCount, setReviewCount] = useState<number | null>(null);

  useEffect(() => {
    api("/api/health").then(setHealth).catch(() => setHealth(null));
  }, []);
  useEffect(() => {
    if (!project) return;
    api<any[]>(`/api/review/queue?project_id=${project.id}`).then((q) => setReviewCount(q.length)).catch(() => {});
  }, [project, path]);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="no-print border-b border-line bg-ink/90 backdrop-blur-md sticky top-0 z-[1000]">
        <div className="max-w-7xl mx-auto px-5 md:px-10 flex flex-wrap lg:flex-nowrap items-center gap-x-8 gap-y-1 py-4">
          <Link href="/" className="text-paper font-serif text-[19px] uppercase shrink-0">ImpactProof</Link>
          {projects.length > 0 && (
            <label className="shrink-0 relative">
              <span className="sr-only">Project</span>
              <select value={project?.id ?? ""} onChange={(e) => setProjectId(Number(e.target.value))}
                className="appearance-none bg-transparent border-l border-line pl-4 pr-5 py-0.5 text-sm text-muted hover:text-paper max-w-[150px] sm:max-w-[230px] truncate cursor-pointer focus:outline-none">
                {projects.map((p) => <option key={p.id} value={p.id} className="bg-surface text-paper">{p.name}</option>)}
              </select>
              <span className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 text-faint text-[10px]">▾</span>
            </label>
          )}
          <ThemeToggle className="ml-auto lg:order-last !w-8 !h-8 !border-transparent !bg-transparent" />
          <nav className="flex gap-5 overflow-x-auto scroll-thin order-3 lg:order-none w-full lg:w-auto min-w-0 -mb-px">
            {NAV.map((n) => {
              const active = path === n.href || (n.href !== "/dashboard" && path.startsWith(n.href)) ||
                (n.href === "/dashboard" && path.startsWith("/evidence"));
              return (
                <Link key={n.href} href={n.href} aria-current={active ? "page" : undefined}
                  className={`py-2 text-sm whitespace-nowrap transition-colors border-b ${active ? "text-paper border-paper" : "text-paper/60 font-light border-transparent hover:text-paper"}`}>
                  {n.label}
                  {n.href === "/review" && reviewCount ? <span className="ml-1.5 t-meta text-[11px] text-review">{reviewCount}</span> : null}
                </Link>
              );
            })}
          </nav>
          <div className="hidden 2xl:flex gap-4 t-meta text-[11px] text-faint uppercase lg:order-last">
            {health ? (
              <>
                <Conn on={health.cloudinary === "configured"} label="Cloudinary" />
                <Conn on={health.gemini === "configured"} label="Gemini" />
                <Conn on={health.qdrant === "ok"} label="Qdrant" />
              </>
            ) : <span className="text-bad">Backend offline</span>}
          </div>
        </div>
      </header>
      {error && (
        <div className="max-w-7xl mx-auto w-full px-5 md:px-10 pt-6">
          <div className="border-l-2 border-bad pl-4 py-2 text-sm">{error}</div>
        </div>
      )}
      <main key={path} className="flex-1 max-w-7xl w-full mx-auto px-5 md:px-10 py-12 page-in">{children}</main>
    </div>
  );
}

function Conn({ on, label }: { on: boolean; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${on ? "bg-ok" : "bg-faint"}`} />
      {label}
    </span>
  );
}
