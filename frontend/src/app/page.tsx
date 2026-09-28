"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { MotionConfig, motion, useScroll, useTransform } from "framer-motion";
import { X } from "lucide-react";
import EarlyAccessForm from "@/components/EarlyAccessForm";
import {
  CursorPreview, EditorialLabel, RevealText, EditorialRow, EditorialRule, EditorialSection, EditorialTitle, EvidenceChain,
  MagneticButton, Reveal, ScrollProgress, TypeIn, VerificationStamp,
} from "@/components/editorial";

// Swap in your own video (for example a Cloudinary URL with f_auto,q_auto) with NEXT_PUBLIC_HERO_VIDEO.
const HERO_VIDEO = process.env.NEXT_PUBLIC_HERO_VIDEO ||
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_204103_f607742e-09da-4cf5-bb06-4e67b0a531de.mp4";
// Optional: the story video that "Watch the story" plays (e.g. your explainer).
const STORY_VIDEO = process.env.NEXT_PUBLIC_STORY_VIDEO || "";

const LINKS = [
  { href: "#problem", label: "Problem" },
  { href: "#chain", label: "Evidence chain" },
  { href: "#platform", label: "Platform" },
  { href: "#evidence", label: "Live record" },
];
const EASE = "ease-[cubic-bezier(0.76,0,0.24,1)]";

const CHAIN = [
  { k: "Claim", v: "The blocked drain was cleared.", meta: "Stated by Green Steps Foundation" },
  { k: "Field evidence", v: "Six photographs, before and after.", meta: "EV-0241 → EV-0246 · original files kept" },
  { k: "Location", v: "Inside the Library lawn site.", meta: "28.6139° N 77.2090° E · 10 m from centre · 150 m radius" },
  { k: "Timestamp", v: "Within the project period.", meta: "20 SEP 2026 · 14:32:08 UTC · server clock" },
  { k: "Source", v: "A named volunteer's device.", meta: "FIELD_AGENT_024 · offline capture, synced later" },
  { k: "Verification", v: "Nine checks, one verdict.", meta: "Reuse · weather · C2PA · content · metadata → corroborated" },
  { k: "Impact", v: "Counted toward SDG 11.", meta: "14 bags removed · public page with QR code" },
];

const PLATFORM = [
  { n: "01", title: "Collect", text: "Volunteers capture photos and notes in the field app, even with no signal. Everything is searchable on the device and syncs when it can." },
  { n: "02", title: "Verify", text: "Every photo is fingerprinted on arrival and put through nine independent checks. Each verdict comes with a plain reason, and people resolve what the rules can't." },
  { n: "03", title: "Connect", text: "Verdicts are written onto each asset in Cloudinary as structured metadata. Photos link to claims, sites and before-and-after pairs." },
  { n: "04", title: "Report", text: "Every claim gets an impact brief and a QR code. Donors scan it and check the evidence themselves, faces blurred." },
];

export default function LandingPage() {
  const [open, setOpen] = useState(false);
  const [story, setStory] = useState(false);
  const [row, setRow] = useState(0);
  const hero = useRef<HTMLElement>(null);
  const problem = useRef<HTMLDivElement>(null);

  // scroll-linked motion on native scroll (no hijacking)
  const { scrollYProgress: heroP } = useScroll({ target: hero, offset: ["start start", "end start"] });
  const titleY = useTransform(heroP, [0, 1], ["0%", "-22%"]);
  const titleO = useTransform(heroP, [0, 0.7], [1, 0]);
  const videoY = useTransform(heroP, [0, 1], ["0%", "18%"]);
  const videoScale = useTransform(heroP, [0, 1], [1, 1.08]);
  const { scrollYProgress: probP } = useScroll({ target: problem, offset: ["start end", "end start"] });
  const drift1 = useTransform(probP, [0, 0.6], ["-6vw", "0vw"]);
  const drift3 = useTransform(probP, [0, 0.6], ["-10vw", "0vw"]);

  useEffect(() => {
    document.body.style.overflow = open || story ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open, story]);

  const [clock, setClock] = useState("");
  useEffect(() => {
    const t = () => setClock(new Date().toISOString().slice(11, 19));
    t(); const id = setInterval(t, 1000); return () => clearInterval(id);
  }, []);

  return (
    <MotionConfig reducedMotion="user">
      <div className="ed min-h-screen overflow-x-clip">
        <div className="ed-grain" aria-hidden />
        <ScrollProgress total={6} />

        {/* ------------------------------------------------ nav */}
        <nav className="absolute top-0 inset-x-0 z-30 ed-gutter flex items-center justify-between py-6">
          <Link href="/" className="font-[family-name:var(--ed-display)] font-extrabold text-[22px] tracking-[-.03em] uppercase">ImpactProof</Link>
          <div className="hidden md:flex items-center gap-8">
            {LINKS.map((l) => <a key={l.href} href={l.href} className="text-[13px] font-bold uppercase tracking-[.02em] text-[var(--ed-cream)]/85 hover:text-[var(--ed-cream)] ed-link transition-colors">{l.label}</a>)}
          </div>
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="hidden md:inline ed-mono text-[var(--ed-muted)] hover:text-[var(--ed-cream)] ed-link">Sign in</Link>
            <a href="#early-access" className="hidden md:inline-flex ed-mono !text-[11px] border border-[var(--ed-rule-strong)] rounded-full px-5 py-2.5 hover:bg-[var(--ed-cream)] hover:text-[var(--ed-bg)] transition-colors">Request access</a>
            <button onClick={() => setOpen(true)} className="md:hidden relative w-8 h-8 flex flex-col items-end justify-center gap-[6px]" aria-label="Open menu" aria-expanded={open}>
              <span className="block h-[1.5px] w-6 bg-[var(--ed-cream)]" />
              <span className="block h-[1.5px] w-4 bg-[var(--ed-cream)]" />
              <span className="block h-[1.5px] w-6 bg-[var(--ed-cream)]" />
            </button>
          </div>
        </nav>

        {/* mobile menu */}
        <div className={`fixed inset-0 z-50 md:hidden ${open ? "pointer-events-auto" : "pointer-events-none"}`} aria-hidden={!open}>
          <div className={`absolute inset-0 bg-[var(--ed-bg)] transition-opacity duration-700 ${EASE} ${open ? "opacity-100" : "opacity-0"}`} />
          <div className={`relative h-full flex flex-col ed-gutter transition-opacity duration-700 ${EASE} ${open ? "opacity-100" : "opacity-0"}`}>
            <div className="flex items-center justify-between py-6">
              <span className="font-semibold text-[17px] tracking-tight">ImpactProof</span>
              <button onClick={() => setOpen(false)} className="relative w-8 h-8" aria-label="Close menu">
                <span className="absolute left-1 right-1 top-1/2 h-[1.5px] bg-[var(--ed-cream)] rotate-45" />
                <span className="absolute left-1 right-1 top-1/2 h-[1.5px] bg-[var(--ed-cream)] -rotate-45" />
              </button>
            </div>
            <div className="flex-1 flex flex-col justify-center">
              {[...LINKS, { href: "/dashboard", label: "Dashboard" }, { href: "#early-access", label: "Request access" }].map((l, i) => (
                <a key={l.href} href={l.href} onClick={() => setOpen(false)} style={{ transitionDelay: open ? `${150 + i * 70}ms` : "0ms" }}
                  className={`ed-display text-[10vw] border-b border-[var(--ed-rule)] py-3 flex items-baseline gap-4 transition-all duration-700 ${EASE} ${open ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"}`}>
                  <span className="ed-mono text-[var(--ed-accent)]">0{i + 1}</span>{l.label}
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* ------------------------------------------------ 01 hero: full-screen field footage */}
        <section ref={hero} id="top" data-ed-section={1} data-ed-name="ImpactProof" className="relative h-[100svh] min-h-[600px] overflow-hidden">
          <motion.video style={{ y: videoY, scale: videoScale }} className="absolute inset-0 w-full h-full object-cover"
            src={HERO_VIDEO} autoPlay loop muted playsInline preload="auto" aria-hidden />
          {/* keep the cream type legible and melt the footage into the page */}
          <div className="absolute inset-0 bg-[rgb(16_9_4/.28)]" aria-hidden />
          <div className="absolute inset-x-0 top-0 h-48 bg-gradient-to-b from-[rgb(16_9_4/.65)] to-transparent" aria-hidden />
          <div className="absolute inset-x-0 bottom-0 h-[45%] bg-gradient-to-t from-[var(--ed-bg)] via-[rgb(16_9_4/.55)] to-transparent" aria-hidden />

          <motion.div style={{ y: titleY, opacity: titleO }} className="relative z-10 h-full flex flex-col items-center justify-center text-center ed-gutter pt-16">
            <EditorialLabel className="justify-center">Evidence infrastructure for NGOs</EditorialLabel>
            <RevealText as="h1" lines={["IMPACT", "PROOF."]} delay={0.15}
              className="ed-display text-[23vw] lg:text-[12vw] mt-6 drop-shadow-[0_2px_30px_rgba(16,9,4,.35)]" />
            <Reveal delay={0.7}><p className="ed-body mt-6 max-w-[40ch] !text-[clamp(16px,1.4vw,20px)] !text-[var(--ed-cream)]">
              Evidence, provenance and measurable impact — connected, from a village with no signal to the donor&apos;s phone.
            </p></Reveal>
            <Reveal delay={0.85} className="mt-8 flex flex-col sm:flex-row items-center gap-4">
              <MagneticButton href="#problem">Explore the platform <span className="transition-transform group-hover:translate-x-1">→</span></MagneticButton>
              {STORY_VIDEO
                ? <button onClick={() => setStory(true)} className="inline-flex items-center gap-3 rounded-full px-7 py-3.5 ed-mono !text-[12px] !tracking-[.14em] border border-[rgb(244_232_216/.45)] hover:bg-[rgb(244_232_216/.1)] transition-colors">▶ Watch the story</button>
                : <MagneticButton href="/dashboard" variant="line">Open the dashboard</MagneticButton>}
            </Reveal>
          </motion.div>

          {/* field-footage read-outs */}
          <div className="absolute z-10 inset-x-0 bottom-0 ed-gutter pb-6">
            <div className="flex flex-wrap justify-between gap-3 ed-mono !text-[10px] text-[var(--ed-cream)]/85">
              <span className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-[#ff5a3c] animate-pulse" />Field footage · REC · {clock} UTC</span>
              <span className="hidden sm:inline">28.6139° N · 77.2090° E</span>
              <span>Unverified until checked · Scroll ↓</span>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------ 02 the problem */}
        <EditorialSection id="problem" n={2} name="The problem" className="py-[18vh]">
          <div ref={problem}>
            <EditorialLabel n={2}>The problem</EditorialLabel>
            <h2 className="ed-display text-[12vw] md:text-[7.8vw] mt-8">
              <motion.span style={{ x: drift1 }} className="block"><RevealLine>THE PHOTO</RevealLine></motion.span>
              <span className="block md:pl-[18vw]"><RevealLine em delay={0.1}>IS NOT</RevealLine></span>
              <motion.span style={{ x: drift3 }} className="block md:text-right"><RevealLine delay={0.2}>THE PROOF.</RevealLine></motion.span>
            </h2>
            <div className="mt-[10vh] grid md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] gap-x-[6vw] gap-y-12 items-start">
              <Reveal>
                <p className="ed-body max-w-[46ch]">
                  A photograph with no location, no timestamp, no source and no verification is a picture, not evidence.
                  WhatsApp strips it. Screenshots strip it. AI can make one in five seconds. Donors are asked to trust it anyway.
                </p>
              </Reveal>
              <figure>
                <div className="relative aspect-[4/3] overflow-hidden bg-[var(--ed-bg-2)]">
                  <img className="absolute inset-0 w-full h-full object-cover grayscale opacity-60" src="/problem.jpg" alt="" aria-hidden />
                  <span className="absolute top-3 left-3 ed-mono !text-[10px] text-[var(--ed-cream)]">IMG_2041.JPG · forwarded</span>
                </div>
                <dl className="mt-4">
                  {["Location", "Timestamp", "Source", "Verification"].map((k, i) => (
                    <Reveal key={k} delay={0.15 + i * 0.18} y={6} className="grid grid-cols-[8.5rem_1fr] items-center gap-4 py-3">
                      <dt className="ed-mono text-[var(--ed-muted)]">{k}</dt>
                      <dd className="flex items-center gap-3"><span className="flex-1 ed-rule-dashed" /><span className="ed-mono text-[#ef7d63]">Missing</span></dd>
                    </Reveal>
                  ))}
                </dl>
              </figure>
            </div>
          </div>
        </EditorialSection>

        {/* ------------------------------------------------ 03 evidence chain (sticky) */}
        <EditorialSection id="chain" n={3} name="Evidence chain" className="py-[14vh] border-t border-[var(--ed-rule)]">
          <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] gap-x-[6vw] gap-y-12">
            <div className="lg:sticky lg:top-[18vh] self-start">
              <EditorialLabel n={3}>Evidence chain</EditorialLabel>
              <EditorialTitle size="lg" lines={["A claim is", "only as strong", "as its chain."]} em={[1]} className="mt-8" />
              <Reveal delay={0.3}><p className="ed-body max-w-[40ch] mt-8">
                ImpactProof keeps every link: who captured it, where, when, on which device, and what the checks found. Break one and the claim says so.
              </p></Reveal>
            </div>
            <EvidenceChain steps={CHAIN} />
          </div>
        </EditorialSection>

        {/* ------------------------------------------------ 04 platform (tile rows) */}
        <EditorialSection id="platform" n={4} name="Platform" className="py-[14vh] border-t border-[var(--ed-rule)]">
          <div className="flex flex-wrap items-end justify-between gap-6 mb-[8vh]">
            <div>
              <EditorialLabel n={4}>Platform</EditorialLabel>
              <EditorialTitle size="lg" lines={["One record,", "four moves."]} em={[1]} className="mt-8" />
            </div>
            <Reveal><p className="ed-mono text-[var(--ed-muted)] max-w-[30ch] text-right hidden md:block">Hover a row to open its record</p></Reveal>
          </div>
          <div className="grid lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] gap-x-[5vw]">
            <ul className="border-b border-[var(--ed-rule)]">
              {PLATFORM.map((p, i) => (
                <EditorialRow key={p.n} n={p.n} title={p.title} text={p.text} active={row === i} onEnter={() => setRow(i)} preview={<Preview i={i} />} />
              ))}
            </ul>
            <div className="hidden lg:block">
              <div className="sticky top-[22vh]">
                <p className="ed-mono text-[var(--ed-muted)] mb-3">Record · {PLATFORM[row].n} {PLATFORM[row].title}</p>
                <div className="relative">
                  {PLATFORM.map((p, i) => (
                    <div key={p.n} className={i === row ? "relative" : "absolute inset-0"}>
                      <CursorPreview show={i === row}><Preview i={i} /></CursorPreview>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </EditorialSection>

        {/* ------------------------------------------------ 05 live evidence */}
        <EditorialSection id="evidence" n={5} name="Live record" className="py-[14vh] border-t border-[var(--ed-rule)]">
          <EditorialLabel n={5}>Live evidence</EditorialLabel>
          <EditorialTitle size="md" lines={["A provenance record,", "not a thumbnail."]} em={[1]} className="mt-8 max-w-[18ch]" />
          <div className="mt-[8vh] grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] gap-x-[5vw] gap-y-10 items-start">
            <figure>
              <div className="flex justify-between ed-mono text-[var(--ed-muted)] mb-3"><span>Field record / 0248</span><span className="text-[var(--ed-accent)]">● Corroborated</span></div>
              <div className="relative aspect-[4/5] overflow-hidden bg-[var(--ed-bg-2)]">
                <img className="absolute inset-0 w-full h-full object-cover" src="/record.jpg" alt="A field photo recorded by ImpactProof" />
                <span className="absolute inset-4 border border-[rgb(244_232_216/.35)] pointer-events-none" />
                <span className="absolute left-1/2 top-1/2 w-10 h-10 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                  <span className="absolute left-1/2 top-0 bottom-0 w-px bg-[rgb(244_232_216/.6)]" /><span className="absolute top-1/2 left-0 right-0 h-px bg-[rgb(244_232_216/.6)]" />
                </span>
              </div>
            </figure>
            <div>
              <dl>
                {[
                  { k: "Field site", v: "28.6139° N\n77.2090° E" },
                  { k: "Captured", v: "14:32:08 UTC · 20 SEP 2026" },
                  { k: "Source", v: "FIELD_AGENT_024" },
                  { k: "Device", v: "ImpactProof Field · offline capture" },
                  { k: "Fingerprint", v: "SHA-256 9f2c4e1a…b7d03c" },
                  { k: "Cloudinary", v: "impactproof/ev_0248 · ETag matches" },
                ].map((r, i) => (
                  <div key={r.k}>
                    <EditorialRule dashed delay={i * 0.08} />
                    <div className="grid grid-cols-[8.5rem_1fr] gap-4 py-4 items-baseline">
                      <dt className="ed-mono text-[var(--ed-muted)]">{r.k}</dt>
                      <dd className="font-[family-name:var(--ed-mono)] text-[clamp(15px,1.5vw,20px)] whitespace-pre-line">
                        <TypeIn text={r.v} delay={0.2 + i * 0.25} />
                      </dd>
                    </div>
                  </div>
                ))}
                <EditorialRule dashed />
                <div className="grid grid-cols-[8.5rem_1fr] gap-4 py-6 items-center">
                  <dt className="ed-mono text-[var(--ed-muted)]">Status</dt>
                  <dd><VerificationStamp label="Verified" /></dd>
                </div>
              </dl>
              <Reveal><p className="ed-body max-w-[44ch] mt-4">
                Nine checks passed or were marked as having no data: location, date, reuse, content credentials, camera metadata,
                visual content, visible text, weather and capture method. Unknown is never treated as fake.
              </p></Reveal>
            </div>
          </div>
        </EditorialSection>

        {/* ------------------------------------------------ 06 final call */}
        <EditorialSection id="start" n={6} name="Start" className="pt-[16vh] pb-[10vh] border-t border-[var(--ed-rule)]">
          <EditorialLabel n={6}>Start</EditorialLabel>
          <EditorialTitle size="xl" lines={["MAKE", "THE EVIDENCE", "TRACEABLE."]} em={[1]} className="mt-8" />
          <div className="mt-12 flex flex-wrap items-center gap-4">
            <MagneticButton href="/dashboard">Start with ImpactProof <span className="transition-transform group-hover:translate-x-1">→</span></MagneticButton>
            <MagneticButton href="#early-access" variant="line">Request access</MagneticButton>
          </div>

          <div id="early-access" className="mt-[16vh] grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)] gap-x-[6vw] gap-y-10 items-start">
            <div>
              <EditorialRule />
              <p className="ed-label mt-4">For NGOs and CSR teams</p>
              <h3 className="ed-display text-[8vw] md:text-[2.9vw] mt-4">Pilot it with <span className="ed-em">your</span> next drive.</h3>
              <p className="ed-body mt-5 max-w-[40ch]">Stop assembling donor reports from scattered photos. Tell us how you report impact today.</p>
            </div>
            <EarlyAccessForm />
          </div>

          <footer className="mt-[14vh]">
            <EditorialRule />
            <div className="flex flex-wrap justify-between gap-4 pt-4 ed-mono text-[var(--ed-faint)]">
              <span>ImpactProof · {new Date().getFullYear()}</span>
              <span>Evidence you can trace. Impact you can trust.</span>
              <Link href="/dashboard" className="ed-link hover:text-[var(--ed-cream)]">Open the dashboard</Link>
            </div>
          </footer>
        </EditorialSection>

        {story && STORY_VIDEO && (
          <div className="fixed inset-0 z-[70] bg-[rgb(16_9_4/.96)] flex items-center justify-center p-4" role="dialog" aria-label="The story">
            <button onClick={() => setStory(false)} className="absolute top-5 right-5 text-[var(--ed-cream)]" aria-label="Close"><X size={28} /></button>
            <video src={STORY_VIDEO} controls autoPlay className="max-h-[85vh] max-w-full" />
          </div>
        )}
      </div>
    </MotionConfig>
  );
}

/** One masked line (used where a line also drifts with scroll). */
function RevealLine({ children, delay = 0, em = false }: { children: React.ReactNode; delay?: number; em?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const o = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); o.disconnect(); } }, { threshold: 0.4 });
    o.observe(el); return () => o.disconnect();
  }, []);
  return (
    <span ref={ref} className="block overflow-hidden pb-[0.06em] -mb-[0.06em]">
      <motion.span className={`block ${em ? "ed-em" : ""}`} initial={{ y: "108%" }} animate={{ y: seen ? "0%" : "108%" }}
        transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1], delay }}>{children}</motion.span>
    </span>
  );
}

/** Each platform row's visual moment: a real piece of the product, set as a record. */
function Preview({ i }: { i: number }) {
  const frame = "border border-[var(--ed-rule-strong)] bg-[var(--ed-bg-2)] p-6 md:p-7";
  const line = "grid grid-cols-[1.4rem_1fr_auto] gap-3 py-2.5 border-b border-dashed border-[var(--ed-rule)] items-baseline";
  if (i === 0) return (
    <div className={frame}>
      <div className="flex flex-wrap gap-x-5 gap-y-1 ed-mono !text-[10px] text-[var(--ed-muted)] pb-4 border-b border-[var(--ed-rule)]">
        <span>NET <b className="font-normal text-[#ef7d63]">OFFLINE</b></span><span>GPS <b className="font-normal text-[var(--ed-cream)]">±8 M</b></span>
        <span>SYNC <b className="font-normal text-[var(--ed-cream)]">3 PENDING</b></span><span>BATT <b className="font-normal text-[var(--ed-cream)]">82%</b></span>
      </div>
      <p className="ed-display !font-bold text-[1.9rem] !leading-[1.05] mt-6">“where was the blocked drain?”</p>
      <p className="ed-mono text-[var(--ed-accent)] mt-4">4 results · 3 ms · searched on this device</p>
      <p className="ed-mono !text-[10px] text-[var(--ed-faint)] mt-2">Qdrant Edge · on-device memory · no network</p>
    </div>
  );
  if (i === 1) return (
    <div className={frame}>
      {[["✓", "Location", "10 m inside site"], ["✓", "Capture date", "in project period"], ["✓", "Weather", "0 mm · dry ground"],
      ["✓", "Reuse", "no earlier copy"], ["–", "Content credentials", "none attached"], ["✓", "Visual content", "cleanup visible"]].map(([m, k, v]) => (
        <div key={k} className={line}>
          <span className={`ed-mono ${m === "✓" ? "text-[var(--ed-accent)]" : "text-[var(--ed-faint)]"}`}>{m}</span>
          <span className="text-[15px]">{k}</span><span className="ed-mono !text-[10px] text-[var(--ed-muted)]">{v}</span>
        </div>
      ))}
      <div className="flex items-end justify-between mt-6"><span className="ed-mono text-[var(--ed-accent)]">Corroborated</span><span className="ed-display text-6xl">92</span></div>
    </div>
  );
  if (i === 2) return (
    <div className={frame}>
      <p className="ed-mono !text-[10px] text-[var(--ed-muted)]">Cloudinary · structured metadata</p>
      {[["public_id", "impactproof/project_1/ev_0248"], ["ip_trust_status", "corroborated"], ["ip_trust_score", "92"], ["ip_stage", "after"],
      ["ip_sdgs", "sdg_11"], ["tags", "trust_corroborated · stage_after"]].map(([k, v]) => (
        <div key={k} className="grid grid-cols-[9.5rem_1fr] gap-3 py-2.5 border-b border-dashed border-[var(--ed-rule)]">
          <span className="ed-mono !normal-case !tracking-normal text-[var(--ed-muted)] !text-[12px]">{k}</span>
          <span className="font-[family-name:var(--ed-mono)] text-[13px] truncate">{v}</span>
        </div>
      ))}
      <p className="ed-mono !text-[10px] text-[var(--ed-faint)] mt-4">Linked to claim 0001 · before/after pair · Library lawn</p>
    </div>
  );
  return (
    <div className={`${frame} grid grid-cols-[auto_1fr] gap-6 items-center`}>
      <svg viewBox="0 0 21 21" className="w-32 h-32 bg-[var(--ed-cream)] p-1.5" shapeRendering="crispEdges" aria-hidden>
        {QR.map(([x, y]) => <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill="#100904" />)}
      </svg>
      <div>
        <p className="ed-display text-3xl !leading-[1]">Scan to verify.</p>
        <p className="ed-mono !text-[10px] text-[var(--ed-muted)] mt-3">Impact brief · claim 0001</p>
        <p className="ed-mono !text-[10px] text-[var(--ed-accent)] mt-1">6 corroborated · 0 hidden</p>
      </div>
    </div>
  );
}

// A decorative QR-like pattern (finder squares + a fixed pseudo-random fill).
const QR: [number, number][] = (() => {
  const cells: [number, number][] = [];
  const finder = (ox: number, oy: number) => {
    for (let y = 0; y < 7; y++) for (let x = 0; x < 7; x++) {
      const edge = x === 0 || y === 0 || x === 6 || y === 6, core = x >= 2 && x <= 4 && y >= 2 && y <= 4;
      if (edge || core) cells.push([ox + x, oy + y]);
    }
  };
  finder(0, 0); finder(14, 0); finder(0, 14);
  let s = 7;
  for (let y = 0; y < 21; y++) for (let x = 0; x < 21; x++) {
    const inFinder = (x < 8 && y < 8) || (x > 12 && y < 8) || (x < 8 && y > 12);
    s = (s * 9301 + 49297) % 233280;
    if (!inFinder && s / 233280 > 0.52) cells.push([x, y]);
  }
  return cells;
})();
