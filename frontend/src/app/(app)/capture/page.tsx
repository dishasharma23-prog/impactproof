"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { btn, btnGhost, Loading, PageHeader, StatusTag } from "@/components/ui";
import { API, api, EvidenceLight, Site } from "@/lib/api";
import { useProject } from "@/lib/project";

interface Fix { lat: number; lng: number; accuracy: number }

export default function CapturePage() {
  const { project } = useProject();
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState<string>("");
  const [reference, setReference] = useState<EvidenceLight & { overlay_url?: string } | null>(null);
  const [ghost, setGhost] = useState(40);
  const [running, setRunning] = useState(false);
  const [fix, setFix] = useState<Fix | null>(null);
  const [geoError, setGeoError] = useState("");
  const [camError, setCamError] = useState("");
  const [busy, setBusy] = useState(false);
  const [shots, setShots] = useState<EvidenceLight[]>([]);
  const [secure, setSecure] = useState(true);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const watch = useRef<number | null>(null);
  const token = useRef<string>("");

  useEffect(() => { setSecure(window.isSecureContext); }, []);
  useEffect(() => {
    if (project) api<any>(`/api/projects/${project.id}`).then((p) => setSites(p.sites)).catch(() => {});
  }, [project]);
  useEffect(() => {
    setReference(null);
    if (siteId) api<any>(`/api/sites/${siteId}/reference`).then((r) => setReference(r.reference)).catch(() => {});
  }, [siteId]);
  useEffect(() => () => stop(), []);

  async function newToken() {
    const q = new URLSearchParams();
    if (project) q.set("project_id", String(project.id));
    if (siteId) q.set("site_id", siteId);
    const t = await api<{ token: string }>(`/api/capture/token?${q}`);
    token.current = t.token;
  }

  async function start() {
    setCamError("");
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1440 } }, audio: false,
      });
      stream.current = s;
      if (video.current) { video.current.srcObject = s; await video.current.play(); }
      setRunning(true);
    } catch (e: any) {
      setCamError(e?.name === "NotAllowedError" ? "Camera permission was refused. Allow it in the browser's site settings." : `Camera unavailable: ${e?.message || e}`);
      return;
    }
    if ("geolocation" in navigator) {
      watch.current = navigator.geolocation.watchPosition(
        (p) => { setFix({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }); setGeoError(""); },
        (e) => setGeoError(e.code === 1 ? "Location permission was refused, so photos won't have a verified location." : "Waiting for a GPS fix…"),
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
    } else setGeoError("This browser has no location support.");
    newToken().catch(() => {});
  }

  function stop() {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (watch.current != null) navigator.geolocation.clearWatch(watch.current);
    setRunning(false);
  }

  async function shoot() {
    const v = video.current;
    if (!v || !v.videoWidth || !project) return;
    setBusy(true);
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d")!.drawImage(v, 0, 0);
    const blob: Blob = await new Promise((r) => canvas.toBlob((b) => r(b!), "image/jpeg", 0.92));
    try {
      if (!token.current) await newToken();
      const fd = new FormData();
      fd.append("file", blob, `capture-${Date.now()}.jpg`);
      fd.append("project_id", String(project.id));
      if (siteId) fd.append("site_id", siteId);
      fd.append("capture_token", token.current);
      fd.append("client_time", new Date().toISOString());
      fd.append("tz_offset_min", String(new Date().getTimezoneOffset()));
      if (fix) {
        fd.append("gps_lat", String(fix.lat));
        fd.append("gps_lng", String(fix.lng));
        fd.append("gps_accuracy", String(fix.accuracy));
      }
      const res = await fetch(`${API}/api/evidence/upload`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      setShots((s) => [data.evidence, ...s]);
    } catch (e: any) {
      setCamError(e.message);
    }
    token.current = "";
    newToken().catch(() => {});
    setBusy(false);
  }

  if (!project) return <Loading />;

  return (
    <div>
      <PageHeader title="Camera"
        lead="Photos taken here are verified at the moment of capture: live GPS and the server's clock are recorded with the image, so they can't be backdated or moved. Pick a site to line up your shot with the last photo taken there." />

      {!secure && (
        <div className="border-l-4 border-review bg-review/10 px-4 py-3 mb-6 text-sm">
          Browsers only allow the camera on <b>https</b> pages or on <b>localhost</b>. To use your phone, open the app through a secure tunnel (see the README), not your computer&apos;s network address.
        </div>
      )}

      <div className="grid lg:grid-cols-[minmax(0,1fr)_320px] gap-8 items-start">
        <div>
          <div className="relative bg-black rounded-md overflow-hidden aspect-[4/3] ring-1 ring-line">
            <video ref={video} playsInline muted className="absolute inset-0 w-full h-full object-cover" />
            {running && reference?.overlay_url && ghost > 0 && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={reference.overlay_url} alt="" className="absolute inset-0 w-full h-full object-cover pointer-events-none" style={{ opacity: ghost / 100 }} />
            )}
            {!running && (
              <div className="absolute inset-0 grid place-items-center text-center p-6">
                <div>
                  <p className="font-serif text-3xl text-white">Camera is off</p>
                  <button onClick={start} className={`${btn} mt-4`}>Start camera</button>
                  {camError && <p className="text-bad text-sm mt-3 max-w-sm">{camError}</p>}
                </div>
              </div>
            )}
            {running && (
              <div className="absolute top-3 left-3 right-3 flex justify-between gap-3 text-xs">
                <span className={`px-2 py-1 rounded-sm bg-ink/80 ${fix && fix.accuracy <= 50 ? "text-ok" : "text-review"}`}>
                  {fix ? `GPS ±${Math.round(fix.accuracy)} m` : geoError || "Finding location…"}
                </span>
                {reference && <span className="px-2 py-1 rounded-sm bg-ink/80">Ghost: {reference.code}</span>}
              </div>
            )}
          </div>
          {running && (
            <div className="flex flex-wrap items-center gap-4 mt-4">
              <button onClick={shoot} disabled={busy} className={`${btn} px-8 py-3 text-base`}>{busy ? "Verifying…" : "Take photo"}</button>
              <button onClick={stop} className={btnGhost}>Stop camera</button>
              {camError && <span className="text-bad text-sm">{camError}</span>}
            </div>
          )}
        </div>

        <aside className="space-y-6">
          <label className="block text-sm">
            <span className="block font-medium mb-1.5">Site</span>
            <select value={siteId} onChange={(e) => setSiteId(e.target.value)} className="w-full border border-line rounded-md px-3 py-2">
              <option value="">No site (use GPS only)</option>
              {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          {siteId && (
            <div className="text-sm">
              {reference ? (
                <>
                  <p className="text-muted">Line up with <Link href={`/evidence/${reference.id}`} className="underline font-mono">{reference.code}</Link>, the latest photo here, so before and after match exactly.</p>
                  <label className="block mt-3">
                    <span className="block font-medium mb-1">Ghost opacity {ghost}%</span>
                    <input type="range" min={0} max={80} value={ghost} onChange={(e) => setGhost(Number(e.target.value))} className="w-full accent-[var(--color-gold)]" />
                  </label>
                </>
              ) : <p className="text-muted">No earlier photo at this site yet. This one will become the reference for the next visit.</p>}
            </div>
          )}
          {shots.length > 0 && (
            <div>
              <h2 className="font-semibold mb-2">This session</h2>
              <ul className="space-y-3">
                {shots.map((s) => (
                  <li key={s.id}>
                    <Link href={`/evidence/${s.id}`} className="flex gap-3 items-center">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={s.thumb_url || ""} alt="" className="w-16 h-12 object-cover rounded-sm" />
                      <span><span className="font-mono text-sm block">{s.code}</span><StatusTag status={s.integrity_status} /></span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-faint leading-relaxed">
            Each photo carries a single-use token that expires 15 minutes after the camera opens. Someone determined could still bypass this page, which is why hardware-signed capture in a native app is on the roadmap.
          </p>
        </aside>
      </div>
    </div>
  );
}
