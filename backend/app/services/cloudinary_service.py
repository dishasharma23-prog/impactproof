"""Cloudinary: the evidence vault.

Originals are uploaded untouched and never transformed in place. Everything else (thumbnails,
face-blurred public copies, campaign images) is a derived URL that names its source.
"""
import cloudinary
import cloudinary.uploader
from cloudinary import CloudinaryImage

from app.core.config import cloudinary_enabled, settings


class CloudinaryService:
    @staticmethod
    def enabled() -> bool:
        return cloudinary_enabled()

    @staticmethod
    def upload_image(file_path: str, evidence_key: str = None, project_id=None) -> dict:
        if not cloudinary_enabled():
            raise Exception("Media storage is not configured.")
        options = dict(image_metadata=True, phash=True, resource_type="image",
                       tags=["impactproof"] + ([f"project_{project_id}"] if project_id else []))
        if evidence_key:
            options.update(public_id=evidence_key, folder=f"{settings.CLOUDINARY_FOLDER}/project_{project_id or 'none'}",
                           overwrite=False, unique_filename=False)
        return cloudinary.uploader.upload(file_path, **options)

    @staticmethod
    def trust_payload(evidence, integrity) -> dict | None:
        """Everything ImpactProof writes onto the Cloudinary asset. Built in the request, sent in the background."""
        if not evidence.cloudinary_public_id:
            return None
        from app.services import classify, sdg
        raw = (evidence.ai_analysis.raw_response or {}) if evidence.ai_analysis else {}
        stage, category = classify.stage_of(evidence), classify.category_of(evidence)
        status = (integrity.status or "UNVERIFIABLE").lower()
        goals = sdg.evidence_sdgs(evidence, evidence.project)
        ctx = {"evidence_id": f"EV-{evidence.id:04d}", "trust_status": integrity.status or "",
               "trust_score": str(integrity.score if integrity.score is not None else ""),
               "project_id": str(evidence.project_id or ""), "activity": (raw.get("activity") or "")[:200]}
        tags = ["impactproof", f"project_{evidence.project_id}", f"trust_{status}", f"stage_{stage}",
                f"category_{category}"] + [f"sdg_{n}" for n in goals] + \
               [str(t).replace(" ", "_").lower()[:40] for t in (raw.get("tags") or [])[:8]]
        metadata = {
            "ip_evidence_id": f"EV-{evidence.id:04d}",
            "ip_trust_status": status,
            "ip_project": (evidence.project.name if evidence.project else "")[:250],
            "ip_site": (evidence.site.name if evidence.site else "")[:250],
            "ip_sha256": evidence.sha256 or "",
            "ip_stage": stage,
            "ip_category": category,
        }
        if integrity.score is not None:
            metadata["ip_trust_score"] = int(integrity.score)
        if evidence.capture_time:
            metadata["ip_captured_at"] = evidence.capture_time.date().isoformat()
        if goals:
            metadata["ip_sdgs"] = [f"sdg_{n}" for n in goals]
        metadata = {k: v for k, v in metadata.items() if v not in ("", None)}
        return {"public_id": evidence.cloudinary_public_id, "context": ctx, "tags": tags, "metadata": metadata}

    _fields_ready = False
    metadata_available = None   # None = not tried yet

    @classmethod
    def ensure_metadata_fields(cls) -> bool:
        """Creates ImpactProof's structured metadata fields in the Cloudinary account once."""
        if cls._fields_ready:
            return True
        if not cloudinary_enabled():
            return False
        import cloudinary.api
        from app.services import classify
        from app.services.sdg import SDGS
        wanted = [
            {"type": "string", "external_id": "ip_evidence_id", "label": "ImpactProof evidence ID"},
            {"type": "enum", "external_id": "ip_trust_status", "label": "ImpactProof verdict",
             "datasource": {"values": [{"external_id": k, "value": v} for k, v in (
                 ("corroborated", "Corroborated"), ("needs_review", "Needs review"), ("suspicious", "Suspicious"),
                 ("unverifiable", "Unverifiable"), ("rejected", "Rejected"))]}},
            {"type": "integer", "external_id": "ip_trust_score", "label": "ImpactProof trust score"},
            {"type": "string", "external_id": "ip_project", "label": "ImpactProof project"},
            {"type": "string", "external_id": "ip_site", "label": "ImpactProof site"},
            {"type": "date", "external_id": "ip_captured_at", "label": "Captured on"},
            {"type": "string", "external_id": "ip_sha256", "label": "SHA-256 on receipt"},
            {"type": "enum", "external_id": "ip_stage", "label": "Work stage",
             "datasource": {"values": [{"external_id": k, "value": v} for k, v in classify.STAGES.items()]}},
            {"type": "enum", "external_id": "ip_category", "label": "Activity category",
             "datasource": {"values": [{"external_id": k, "value": v} for k, v in classify.CATEGORIES.items()]}},
            {"type": "set", "external_id": "ip_sdgs", "label": "Sustainable Development Goals",
             "datasource": {"values": [{"external_id": f"sdg_{n}", "value": f"SDG {n}: {name}"}
                                       for n, (name, _c) in SDGS.items()]}},
        ]
        try:
            existing = {f["external_id"] for f in cloudinary.api.list_metadata_fields().get("metadata_fields", [])}
            for field in wanted:
                if field["external_id"] not in existing:
                    cloudinary.api.add_metadata_field(field)
            cls._fields_ready = True
            cls.metadata_available = True
        except Exception as e:
            print(f"Cloudinary structured metadata unavailable, using tags and context only: {e}")
            cls.metadata_available = False
        return cls._fields_ready

    @classmethod
    def push_trust(cls, payload: dict) -> None:
        """Replaces the asset's tags, sets context, and fills the structured metadata fields."""
        if not cloudinary_enabled():
            return
        import cloudinary.api
        try:
            cloudinary.api.update(payload["public_id"], tags=payload["tags"],
                                  context="|".join(f"{k}={str(v).replace('|', '/').replace('=', '-')}"
                                                   for k, v in payload["context"].items()))
        except Exception as e:
            print(f"Cloudinary write-back failed for {payload['public_id']}: {e}")
        if payload.get("metadata") and cls.ensure_metadata_fields():
            try:
                cloudinary.uploader.update_metadata(payload["metadata"], [payload["public_id"]])
            except Exception as e:
                print(f"Cloudinary metadata update failed for {payload['public_id']}: {e}")

    @staticmethod
    def widget_signature(params_to_sign: dict) -> str:
        from cloudinary.utils import api_sign_request
        cfg = cloudinary.config()
        return api_sign_request(params_to_sign, cfg.api_secret)

    @staticmethod
    def fetch_resource(public_id: str) -> dict:
        import cloudinary.api
        return cloudinary.api.resource(public_id, phash=True, image_metadata=True)

    @staticmethod
    def thumb_url(evidence, width=640, height=480) -> str | None:
        if not evidence.cloudinary_public_id or not cloudinary_enabled():
            return evidence.cloudinary_url
        return CloudinaryImage(evidence.cloudinary_public_id).build_url(
            transformation=[{"width": width, "height": height, "crop": "fill", "gravity": "auto"},
                            {"quality": "auto", "fetch_format": "auto"}], secure=True)

    @staticmethod
    def public_url(evidence, width=1400) -> str | None:
        """Copy for public pages: faces blurred, resized. The original stays private."""
        if not evidence.cloudinary_public_id or not cloudinary_enabled():
            return evidence.cloudinary_url
        return CloudinaryImage(evidence.cloudinary_public_id).build_url(
            transformation=[{"effect": "blur_faces:900"}, {"width": width, "crop": "limit"},
                            {"quality": "auto", "fetch_format": "auto"}], secure=True)

    FORMATS = [
        {"key": "square", "label": "Instagram post", "width": 1080, "height": 1080},
        {"key": "story", "label": "Story or reel cover", "width": 1080, "height": 1920},
        {"key": "banner", "label": "Web and LinkedIn banner", "width": 1200, "height": 628},
    ]

    @staticmethod
    def _safe_text(text: str) -> str:
        return "".join(ch for ch in (text or "") if ch not in "%/\\#?,").strip()[:140]

    @staticmethod
    def campaign_derivatives(evidence, caption: str, blur_faces: bool, verify_url: str | None = None) -> list:
        if not evidence.cloudinary_public_id:
            return []
        caption = CloudinaryService._safe_text(caption)
        stamp = CloudinaryService._safe_text(f"Verified evidence EV-{evidence.id:04d} with ImpactProof")
        out = []
        for f in CloudinaryService.FORMATS:
            w, h = f["width"], f["height"]
            chain = [{"width": w, "height": h, "crop": "fill", "gravity": "auto"}]
            if blur_faces:
                chain.append({"effect": "blur_faces:900"})
            if caption:
                chain.append({"overlay": {"font_family": "Arial", "font_size": int(w / 19), "font_weight": "bold",
                                          "text": caption},
                              "color": "#FFFFFF", "background": "#0B1512", "width": int(w * 0.84), "crop": "fit",
                              "gravity": "south_west", "x": int(w * 0.06), "y": int(h * 0.11)})
            chain.append({"overlay": {"font_family": "Arial", "font_size": int(w / 44), "text": stamp},
                          "color": "#D4AF37", "background": "#0B1512",
                          "gravity": "south_west", "x": int(w * 0.06), "y": int(h * 0.045)})
            chain.append({"quality": "auto", "fetch_format": "auto"})
            url = CloudinaryImage(evidence.cloudinary_public_id).build_url(transformation=chain, secure=True)
            out.append({**f, "url": url, "source_evidence_id": evidence.id,
                        "source_public_id": evidence.cloudinary_public_id, "original_url": evidence.cloudinary_url,
                        "blur_faces": blur_faces, "verify_url": verify_url})
        return out
