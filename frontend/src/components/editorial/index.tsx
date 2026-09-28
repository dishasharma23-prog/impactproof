"use client";
/**
 * Editorial components (phase 1: landing page).
 *
 * Techniques adapted from the Lusion reference (CC0), rebuilt without WebGL:
 *  - masked line reveals: each line sits in an overflow-hidden box and slides up from below (index.css animated-h1)
 *  - native scrolling with scroll-linked interpolation, never scroll-jacking (paging.js / homeScene.onScroll)
 *  - a slim progress scrollbar (paging.js updateScrollbar)
 *  - project tiles: a centre-out mask opens on enter, the image drifts with the cursor (ProjectTile.js)
 * All motion is transform/opacity only and follows the user's reduced-motion setting (see <MotionConfig> on the page).
 */
import { motion, useInView, useMotionValue, useScroll, useSpring, useTransform } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const EASE = [0.22, 1, 0.36, 1] as const;

/* ------------------------------------------------------------------ text */

/** Lines that slide up out of a mask, staggered. `replay` re-runs it each time it re-enters, like the reference. */
export function RevealText({ lines, as = "div", className = "", lineClassName = "", delay = 0, stagger = 0.09, replay = false, em = []}: {
  lines: React.ReactNode[]; as?: "h1" | "h2" | "h3" | "p" | "div"; className?: string; lineClassName?: string;
  delay?: number; stagger?: number; replay?: boolean; em?: number[];
}) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: !replay, amount: 0.35 });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Tag = as as any;
  return (
    <Tag ref={ref} className={className}>
      {lines.map((line, i) => (
        <span key={i} className="block overflow-hidden pb-[0.06em] -mb-[0.06em]">
          <motion.span className={`block ${em.includes(i) ? "ed-em" : ""} ${lineClassName}`}
            initial={{ y: "108%" }} animate={{ y: inView ? "0%" : "108%" }}
            transition={{ duration: 1.1, ease: EASE, delay: inView ? delay + i * stagger : 0 }}>
            {line}
          </motion.span>
        </span>
      ))}
    </Tag>
  );
}

/** Fades and lifts in; used for eyebrows and body copy so they arrive after the headline. */
export function Reveal({ children, delay = 0, y = 18, className = "", as = "div" }: {
  children: React.ReactNode; delay?: number; y?: number; className?: string; as?: "div" | "p" | "span" | "li";
}) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.3 });
  const M = motion[as] as typeof motion.div;
  return (
    <M ref={ref as React.Ref<HTMLDivElement>} className={className} initial={{ opacity: 0, y }}
      animate={inView ? { opacity: 1, y: 0 } : undefined} transition={{ duration: 0.9, ease: EASE, delay }}>
      {children}
    </M>
  );
}

/** "02 / THE PROBLEM": section number and name in mono. */
export function EditorialLabel({ n, children, className = "" }: { n?: string | number; children: React.ReactNode; className?: string }) {
  return (
    <Reveal className={`ed-label flex items-center gap-3 ${className}`} y={8}>
      {n != null && <SectionNumber n={n} />}
      {n != null && <span className="w-6 h-px bg-[var(--ed-rule-strong)]" />}
      <span>{children}</span>
    </Reveal>
  );
}

export function SectionNumber({ n }: { n: string | number }) {
  return <span className="text-[var(--ed-accent)]">{String(n).padStart(2, "0")}</span>;
}

/** Oversized display title built from lines; lines listed in `em` are highlighted in the accent colour. */
export function EditorialTitle({ lines, size = "xl", em, className = "", delay = 0, as = "h2" }: {
  lines: React.ReactNode[]; size?: "xxl" | "xl" | "lg" | "md"; em?: number[]; className?: string; delay?: number; as?: "h1" | "h2" | "h3";
}) {
  const s = {
    xxl: "text-[23vw] lg:text-[12.8vw]",
    xl: "text-[12.5vw] md:text-[11vw]",
    lg: "text-[11vw] lg:text-[6vw]",
    md: "text-[8.6vw] md:text-[4.4vw]",
  }[size];
  return <RevealText as={as} lines={lines} em={em} delay={delay} className={`ed-display ${s} ${className}`} />;
}

/** A 1px rule that draws itself across when it scrolls into view. */
export function EditorialRule({ dashed = false, className = "", delay = 0 }: { dashed?: boolean; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 1 });
  return (
    <motion.div ref={ref} className={`${dashed ? "ed-rule-dashed" : "ed-rule"} origin-left ${className}`}
      initial={{ scaleX: 0 }} animate={inView ? { scaleX: 1 } : undefined} transition={{ duration: 1.4, ease: EASE, delay }} />
  );
}

/** A full-width section registered with the progress indicator. */
export function EditorialSection({ id, n, name, children, className = "" }: {
  id: string; n: number; name: string; children: React.ReactNode; className?: string;
}) {
  return (
    <section id={id} data-ed-section={n} data-ed-name={name} className={`relative ed-gutter ${className}`}>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ rows (project-tile interaction) */

/** A numbered editorial row. On hover: the row shifts, its rule sweeps, the preview wipes open and follows the cursor. */
export function EditorialRow({ n, title, text, preview, active, onEnter }: {
  n: string; title: string; text: string; preview: React.ReactNode; active: boolean; onEnter: () => void;
}) {
  return (
    <li onMouseEnter={onEnter} onFocus={onEnter} tabIndex={0}
      className="group relative border-t border-[var(--ed-rule)] focus:outline-none">
      <span className={`absolute left-0 top-[-1px] h-px bg-[var(--ed-cream)] transition-[width] duration-700 ease-[var(--ed-ease)] ${active ? "w-full" : "w-0"}`} />
      <div className={`grid grid-cols-[3.2rem_1fr] md:grid-cols-[5.5rem_1fr] gap-x-4 gap-y-3 py-8 md:py-10 transition-transform duration-700 ease-[var(--ed-ease)] ${active ? "md:translate-x-5" : ""}`}>
        <span className={`ed-mono pt-3 transition-colors ${active ? "text-[var(--ed-accent)]" : "text-[var(--ed-muted)]"}`}>{n} —</span>
        <h3 className={`ed-display text-[10vw] md:text-[4vw] transition-colors duration-500 ${active ? "text-[var(--ed-cream)]" : "text-[rgb(244_232_216/.42)]"}`}>{title}</h3>
        <p className={`col-start-2 ed-body max-w-[46ch] transition-opacity duration-500 ${active ? "opacity-100" : "md:opacity-60"}`}>{text}</p>
      </div>
      {/* phones and keyboards: the visual moment opens inline under the active row */}
      <motion.div className="md:hidden overflow-hidden" initial={false} animate={{ height: active ? "auto" : 0, opacity: active ? 1 : 0 }}
        transition={{ duration: 0.7, ease: EASE }}>
        <div className="pb-8 pl-[3.2rem]">{preview}</div>
      </motion.div>
    </li>
  );
}

/** Desktop preview that wipes open from the centre (the tile's mask) and drifts with the cursor. */
export function CursorPreview({ children, show }: { children: React.ReactNode; show: boolean }) {
  const x = useMotionValue(0), y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 120, damping: 20, mass: 0.6 });
  const sy = useSpring(y, { stiffness: 120, damping: 20, mass: 0.6 });
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const move = (e: MouseEvent) => {
      const box = ref.current?.parentElement?.getBoundingClientRect();
      if (!box) return;
      x.set(((e.clientX - box.left) / box.width - 0.5) * 36);
      y.set(((e.clientY - box.top) / box.height - 0.5) * 28);
    };
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, [x, y]);
  return (
    <motion.div ref={ref} style={{ x: sx, y: sy }} className="pointer-events-none"
      initial={false} animate={{ clipPath: show ? "inset(0% 0% 0% 0%)" : "inset(0% 50% 0% 50%)", opacity: show ? 1 : 0 }}
      transition={{ duration: 0.8, ease: EASE }}>
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ evidence */

/** The chain from claim to impact. Each step lights as it crosses the middle of the screen. */
export function EvidenceChain({ steps }: { steps: { k: string; v: string; meta: string }[] }) {
  const [active, setActive] = useState(0);
  return (
    <ol className="relative">
      <span aria-hidden className="absolute left-[7px] top-3 bottom-3 w-px bg-[var(--ed-rule)]" />
      <ChainProgress count={steps.length} active={active} />
      {steps.map((s, i) => <ChainStep key={s.k} i={i} step={s} active={i <= active} current={i === active} onActive={setActive} />)}
    </ol>
  );
}

function ChainProgress({ count, active }: { count: number; active: number }) {
  return (
    <motion.span aria-hidden className="absolute left-[7px] top-3 w-px bg-[var(--ed-accent)] origin-top"
      style={{ height: "calc(100% - 1.5rem)" }} animate={{ scaleY: count > 1 ? active / (count - 1) : 1 }}
      transition={{ duration: 0.8, ease: EASE }} />
  );
}

function ChainStep({ i, step, active, current, onActive }: {
  i: number; step: { k: string; v: string; meta: string }; active: boolean; current: boolean; onActive: (i: number) => void;
}) {
  const ref = useRef<HTMLLIElement>(null);
  const inView = useInView(ref, { margin: "-48% 0px -48% 0px" });
  useEffect(() => { if (inView) onActive(i); }, [inView, i, onActive]);
  return (
    <li ref={ref} className="relative pl-12 py-7 md:py-9">
      <span className={`absolute left-0 top-[2.35rem] md:top-[2.85rem] w-[15px] h-[15px] rounded-full border transition-all duration-500 ${active ? "bg-[var(--ed-accent)] border-[var(--ed-accent)]" : "bg-[var(--ed-bg)] border-[var(--ed-rule-strong)]"} ${current ? "shadow-[0_0_0_6px_rgb(54_214_176/.14)]" : ""}`} />
      <p className={`ed-mono transition-colors duration-500 ${active ? "text-[var(--ed-accent)]" : "text-[var(--ed-faint)]"}`}>{String(i + 1).padStart(2, "0")} · {step.k}</p>
      <p className={`ed-display !font-bold text-[6.4vw] md:text-[2.3vw] !leading-[1.02] mt-2 transition-colors duration-500 ${active ? "text-[var(--ed-cream)]" : "text-[rgb(244_232_216/.25)]"}`}>{step.v}</p>
      <p className={`ed-mono mt-3 transition-opacity duration-500 ${current ? "opacity-100 text-[var(--ed-muted)]" : "opacity-0"}`}>{step.meta}</p>
    </li>
  );
}

/** A rubber-stamp verdict that presses on when it comes into view. */
export function VerificationStamp({ label = "Verified", className = "" }: { label?: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.8 });
  return (
    <motion.div ref={ref} className={`inline-block ${className}`}
      initial={{ opacity: 0, scale: 1.8, rotate: -12 }} animate={inView ? { opacity: 1, scale: 1, rotate: -4 } : undefined}
      transition={{ type: "spring", stiffness: 260, damping: 16, delay: 0.25 }}>
      <span className="block border-2 border-[var(--ed-accent)] text-[var(--ed-accent)] px-4 py-1.5 ed-mono !text-[13px] !tracking-[.28em] shadow-[inset_0_0_0_3px_var(--ed-bg),inset_0_0_0_4px_rgb(54_214_176/.5)]">
        {label}
      </span>
    </motion.div>
  );
}

/** Text that types itself in once, like a record being written. */
export function TypeIn({ text, delay = 0, speed = 28, className = "" }: { text: string; delay?: number; speed?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 1 });
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!inView) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setN(text.length); return; }
    let i = 0; let t: ReturnType<typeof setTimeout>;
    const step = () => { i += 1; setN(i); if (i < text.length) t = setTimeout(step, speed); };
    t = setTimeout(step, delay * 1000);
    return () => clearTimeout(t);
  }, [inView, text, delay, speed]);
  return (
    <span ref={ref} className={className} aria-label={text}>
      <span aria-hidden>{text.slice(0, n)}</span>
      <span aria-hidden className="invisible">{text.slice(n)}</span>
    </span>
  );
}

/* ------------------------------------------------------------------ chrome */

/** Slim fixed scrollbar with the current section number (the reference's #scrollbar, plus a section read-out). */
export function ScrollProgress({ total }: { total: number }) {
  const { scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, { stiffness: 140, damping: 26 });
  const top = useTransform(progress, (v) => `${v * 100}%`);
  const [current, setCurrent] = useState<{ n: number; name: string }>({ n: 1, name: "" });
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>("[data-ed-section]"));
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) setCurrent({ n: Number(e.target.getAttribute("data-ed-section")), name: e.target.getAttribute("data-ed-name") || "" });
      });
    }, { rootMargin: "-50% 0px -50% 0px" });
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);
  return (
    <div aria-hidden className="fixed right-4 md:right-6 top-1/2 -translate-y-1/2 z-40 hidden sm:flex flex-col items-end gap-3 mix-blend-difference">
      <span className="ed-mono !text-[10px] text-[var(--ed-cream)] [writing-mode:vertical-rl] rotate-180 tracking-[.2em]">
        {String(current.n).padStart(2, "0")} / {String(total).padStart(2, "0")} · {current.name}
      </span>
      <div className="relative w-px h-28 bg-[rgb(244_232_216/.2)]">
        <motion.span className="absolute left-[-1px] w-[3px] h-5 bg-[var(--ed-cream)] -translate-y-1/2" style={{ top }} />
      </div>
    </div>
  );
}

/** A button that leans slightly towards the cursor. */
export function MagneticButton({ href, children, variant = "solid", className = "" }: {
  href: string; children: React.ReactNode; variant?: "solid" | "line"; className?: string;
}) {
  const x = useMotionValue(0), y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 18 }), sy = useSpring(y, { stiffness: 220, damping: 18 });
  function move(e: React.MouseEvent<HTMLAnchorElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - r.left - r.width / 2) * 0.18);
    y.set((e.clientY - r.top - r.height / 2) * 0.3);
  }
  const look = variant === "solid"
    ? "bg-[var(--ed-cream)] text-[var(--ed-bg)] hover:bg-[var(--ed-accent)]"
    : "border border-[var(--ed-rule-strong)] text-[var(--ed-cream)] hover:border-[var(--ed-cream)]";
  return (
    <motion.a href={href} onMouseMove={move} onMouseLeave={() => { x.set(0); y.set(0); }} style={{ x: sx, y: sy }}
      className={`group inline-flex items-center gap-3 rounded-full px-7 py-3.5 ed-mono !text-[12px] !tracking-[.14em] transition-colors duration-300 ${look} ${className}`}>
      {children}
    </motion.a>
  );
}
