import Link from "next/link";

export default function NotFound() {
  return (
    <main className="min-h-screen bg-ink text-paper flex items-center justify-center px-6">
      <div className="max-w-md text-center">
        <p className="t-label">404 · No record</p>
        <h1 className="font-serif text-5xl mt-4">Nothing to verify here.</h1>
        <p className="text-muted mt-4">This page doesn&apos;t exist, or the link was mistyped. Every real record in ImpactProof can be traced from the dashboard.</p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/" className="rounded-full px-6 py-3 bg-paper text-ink text-sm font-medium">Home</Link>
          <Link href="/dashboard" className="rounded-full px-6 py-3 border border-line text-sm">Dashboard</Link>
        </div>
      </div>
    </main>
  );
}
