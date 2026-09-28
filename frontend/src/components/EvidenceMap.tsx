"use client";
import { useEffect, useRef } from "react";
import type { EvidenceLight } from "@/lib/api";

const COLORS: Record<string, string> = {
  CORROBORATED: "#36d6b0", NEEDS_REVIEW: "#e8a84e", SUSPICIOUS: "#ef7d63", UNVERIFIABLE: "#a99e91", REJECTED: "#d4644e",
};

export interface MapSite { id: number | string; name: string; latitude: number | null; longitude: number | null; radius_m: number; stale?: boolean }

function esc(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}

export default function EvidenceMap({ sites = [], points = [], height = 380, onPick, draft }: {
  sites?: MapSite[]; points?: EvidenceLight[]; height?: number;
  onPick?: (lat: number, lng: number) => void; draft?: { lat: number; lng: number; radius: number } | null;
}) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);
  const fitKey = useRef("");
  const pickRef = useRef(onPick);
  useEffect(() => { pickRef.current = onPick; }, [onPick]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !el.current) return;
      if (!mapRef.current) {
        mapRef.current = L.map(el.current, { scrollWheelZoom: false, attributionControl: true }).setView([20.6, 78.9], 4);
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(mapRef.current);
        mapRef.current.on("click", (ev: any) => pickRef.current?.(ev.latlng.lat, ev.latlng.lng));
      }
      const map = mapRef.current;
      layerRef.current?.remove();
      const layer = L.layerGroup().addTo(map);
      layerRef.current = layer;
      const bounds: [number, number][] = [];
      sites.forEach((s) => {
        if (s.latitude == null || s.longitude == null) return;
        const c = L.circle([s.latitude, s.longitude], {
          radius: s.radius_m, color: s.stale ? "#e8a84e" : "#36d6b0", weight: 1.5, dashArray: "5 6", fillOpacity: 0.05,
        }).addTo(layer);
        c.bindTooltip(esc(s.name) + (s.stale ? " (no recent evidence)" : ""), { direction: "top" });
        const b = c.getBounds();
        bounds.push([b.getNorth(), b.getEast()], [b.getSouth(), b.getWest()]);
      });
      points.forEach((p) => {
        if (p.latitude == null || p.longitude == null) return;
        L.circleMarker([p.latitude, p.longitude], {
          radius: 7, color: "#100904", weight: 2, fillColor: COLORS[p.integrity_status] || "#888", fillOpacity: 1,
        }).addTo(layer).bindPopup(
          `<a href="/evidence/${p.id}"><img src="${esc(p.thumb_url || "")}" alt="" style="width:190px;border-radius:3px;margin-bottom:6px"/></a>` +
          `<b>${esc(p.code)}</b> ${esc(p.status_label)}<br/><a href="/evidence/${p.id}">Open evidence</a>`);
        bounds.push([p.latitude, p.longitude]);
      });
      if (draft) {
        L.circle([draft.lat, draft.lng], { radius: draft.radius, color: "#2a7f86", weight: 2, fillOpacity: 0.12 }).addTo(layer);
      }
      const key = sites.map((s) => `${s.id}:${s.latitude}:${s.radius_m}`).join("|") + "#" + points.map((p) => p.id).join(",");
      if (key !== fitKey.current) {
        fitKey.current = key;
        if (bounds.length === 1) map.setView(bounds[0], 16);
        else if (bounds.length > 1) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 17 });
      }
    })();
    return () => { cancelled = true; };
  }, [sites, points, draft]);

  useEffect(() => () => { mapRef.current?.remove(); mapRef.current = null; }, []);

  return <div ref={el} style={{ height }} className="w-full rounded-md ring-1 ring-line overflow-hidden z-0" />;
}
