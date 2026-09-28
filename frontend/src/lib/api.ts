// Empty means same origin: requests go through the rewrites in next.config.ts.
export const API = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export type Status = "CORROBORATED" | "NEEDS_REVIEW" | "SUSPICIOUS" | "UNVERIFIABLE" | "REJECTED";
export type SignalStatus = "pass" | "warn" | "fail" | "unavailable";

export const STATUS_LABEL: Record<string, string> = {
  CORROBORATED: "Corroborated",
  NEEDS_REVIEW: "Needs review",
  SUSPICIOUS: "Suspicious",
  UNVERIFIABLE: "Unverifiable",
  REJECTED: "Rejected",
};
export const STATUS_ORDER: Status[] = ["CORROBORATED", "NEEDS_REVIEW", "SUSPICIOUS", "UNVERIFIABLE"];
export const STATUS_HELP: Record<string, string> = {
  CORROBORATED: "Independent checks agree on where and when it was taken.",
  NEEDS_REVIEW: "Mostly consistent, but something needs a person to look.",
  SUSPICIOUS: "A check failed: reused, wrong place or time, or AI-generated.",
  UNVERIFIABLE: "Not enough data in the file to verify it either way.",
  REJECTED: "A reviewer rejected it. It cannot support claims.",
};

export const SUPPORT_COLOR: Record<string, string> = {
  SUPPORTED: "var(--color-ok)", PARTIAL: "var(--color-review)", CONTESTED: "var(--color-bad)", UNSUPPORTED: "var(--color-unknown)",
};

export interface SdgInfo { number: number; name: string; color: string; photos?: number }

export interface Signal {
  key: string;
  label: string;
  status: SignalStatus;
  reason: string;
  weight: number;
  text?: string[];
  match_id?: number;
}

export interface EvidenceLight {
  id: number;
  code: string;
  original_filename: string;
  image_url: string | null;
  thumb_url: string | null;
  cloudinary_url: string | null;
  cloudinary_public_id: string | null;
  capture_time: string | null;
  uploaded_at: string | null;
  latitude: number | null;
  longitude: number | null;
  project_id: number | null;
  site_id: number | null;
  site_name: string | null;
  capture_source: "upload" | "in_app";
  processing_status: string;
  phash: string | null;
  integrity_status: Status;
  status_label: string;
  trust_score: number | null;
  checks_available: number | null;
  checks_total: number | null;
  headline_reasons: string[];
  activity: string | null;
  tags: string[];
  review_status: string | null;
  sdgs: SdgInfo[];
  stage: string;
  stage_label: string;
  stage_source: "ai" | "rules" | "person";
  category: string;
  category_label: string;
  category_source: "ai" | "rules" | "person";
  duplicate_of_evidence_id: number | null;
  captured_by?: { name: string; phone_masked: string; device: string | null } | null;
}

export interface DuplicateMatch {
  id: number;
  code: string;
  distance: number;
  project_id: number | null;
  project_name: string | null;
  captured_at: string | null;
  uploaded_at: string | null;
  earlier: boolean;
  burst: boolean;
  same_file: boolean;
  image_url: string | null;
  thumb_url: string | null;
  status: Status | null;
}

export interface EvidenceFull extends EvidenceLight {
  device_info: string | null;
  software: string | null;
  width: number | null;
  height: number | null;
  mime_type: string | null;
  file_size: number | null;
  capture_meta: Record<string, any>;
  seal: {
    sha256: string | null;
    md5: string | null;
    cloudinary_etag: string | null;
    cloudinary_matches: boolean | null;
    cloudinary_phash: string | null;
    cloudinary_asset_id: string | null;
    cloudinary_version: string | null;
  };
  provenance: { verdict: string; tools: string[]; manifest: any } | null;
  weather: Record<string, any> | null;
  ai_analysis: {
    provider: string;
    observations: string[];
    objects: string[];
    activities: string[];
    details: Record<string, any>;
  } | null;
  ai_error: string | null;
  integrity: {
    status: Status;
    engine_status: Status;
    status_label: string;
    engine_status_label: string;
    score: number | null;
    available: number;
    total: number;
    signals: Record<string, Signal>;
    computed_at: string | null;
  } | null;
  duplicate_matches: DuplicateMatch[];
  project_name: string | null;
  sdg_reason: string | null;
  cloudinary_record: {
    public_id: string; tags: string[]; metadata: Record<string, any>; context: Record<string, string>;
    structured_metadata: boolean | null; derived: { thumbnail: string | null; public_copy: string | null };
  } | null;
  claims: { id: number; text: string }[];
  reviews: { decision: string; reason: string; reviewer: string; engine_status: string; created_at: string }[];
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  organization: string | null;
  start_date: string | null;
  end_date: string | null;
  sdgs: SdgInfo[];
}

export interface Site {
  id: number;
  name: string;
  project_id: number;
  latitude: number | null;
  longitude: number | null;
  radius_m: number;
  description: string | null;
  evidence_count: number;
  corroborated_count: number;
  last_corroborated_at: string | null;
}

export interface Coverage {
  sites: { site_id: number; site_name: string; corroborated: number; last_evidence: string | null; stale: boolean }[];
  stale_count: number;
  site_count: number;
  stale_days: number;
  summary: string;
}

export interface AuditEvent {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  summary: string;
  detail: any;
  actor: string;
  created_at: string;
}

export interface Support {
  state: "SUPPORTED" | "PARTIAL" | "CONTESTED" | "UNSUPPORTED";
  label: string;
  reason: string;
  corroborated: number;
  total: number;
  counts?: Record<string, number>;
  public_reason?: string;
}

export class ApiError extends Error {}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError("Can't reach the backend. Is it running on port 8000?");
  }
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    if (data === null && res.status >= 500) throw new ApiError("Can't reach the backend. Is it running on port 8000?");
    let msg = data?.detail ?? `Request failed (${res.status})`;
    if (Array.isArray(msg)) msg = msg.map((d: any) => String(d.msg || d).replace(/^Value error, /, "")).join(" ");
    throw new ApiError(String(msg));
  }
  return data as T;
}

export function postJSON<T = any>(path: string, body: unknown, method = "POST") {
  return api<T>(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function fmtDate(iso?: string | null, withTime = false) {
  if (!iso) return "Unknown";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

/** Server timestamps like uploaded_at are UTC without a zone marker. */
export function fmtUtc(iso?: string | null, withTime = true) {
  if (!iso) return "Unknown";
  return fmtDate(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z", withTime);
}

export function fmtSize(bytes?: number | null) {
  if (!bytes) return "";
  return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function timeAgo(iso?: string | null) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso.endsWith("Z") ? iso : iso + "Z").getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
