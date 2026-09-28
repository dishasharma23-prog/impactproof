"""Gemini vision analysis. The model observes; it never decides the verdict."""
import json
import re
from typing import Any, Dict, List

from pydantic import BaseModel

from app.core.config import settings

# Phrases that turn an observation into an interpretation. Observations containing them are dropped.
INFERENCE_PHRASES = ("indicat", "suggest", "likely", "probably", "aimed at", "points to", "highlight",
                     "demonstrat", "signif", "part of a", "effort", "initiative", "impact", "improv",
                     "commitment", "dedicat", "underscore", "showcas", "reflect", "symboli", "evidence of",
                     "developing community", "rural or developing")


class EvidenceAnalysis(BaseModel):
    observations: List[str]
    objects: List[str]
    activities: List[str]
    raw_response: Dict[str, Any]


EVIDENCE_PROMPT = """You examine field photos for an evidence-verification platform used by NGOs and
sustainability teams. Your answers are shown to auditors, so accuracy matters more than completeness.

Project: {name}
What the project does: {description}

RULES
- Describe only what is directly visible. Never state purposes, causes, outcomes, or what something
  "indicates", "suggests" or "is likely part of". No words like indicates, suggests, likely, efforts,
  initiative, impact, highlights.
- Counts are rough estimates. Use null when you cannot count reasonably.
- Copy any readable text exactly (signs, labels, painted text, dates, banners, watermarks).

Return one JSON object with exactly these keys:
{{
  "observations": ["3 to 7 short factual sentences about what is visible"],
  "objects": ["up to 10 visible objects"],
  "activities": ["visible activities, e.g. 'person filling a metal pot at a tap'"],
  "activity": "the main visible activity in a few words",
  "description": "one or two plain factual sentences",
  "people_count_estimate": integer or null,
  "sapling_count_estimate": integer or null,
  "waste_visible": true/false,
  "water_visible": true/false,
  "vegetation_visible": true/false,
  "construction_visible": true/false,
  "damage_visible": true/false,
  "ground_wet": true/false (puddles, wet soil or wet surfaces from rain),
  "rain_falling": true/false,
  "visible_text": ["exact text strings readable in the photo"],
  "visible_organizations": ["organisation or brand names readable in the photo"],
  "is_collage_or_composite": true/false (several photos combined, split panels, borders between images),
  "collage_reason": "short reason or empty",
  "looks_like_screen_or_stock": true/false (screenshot, photo of a screen, stock watermark, illustration),
  "screen_or_stock_reason": "short reason or empty",
  "appears_ai_generated": true/false (tell-tale signs: malformed hands or text, impossible geometry,
      unnaturally perfect lighting and textures, repeated faces),
  "ai_generated_reason": "short reason or empty",
  "relevant_to_project": true/false (does the photo show on-the-ground work of the kind described?),
  "relevance_reason": "one short factual sentence",
  "comparable_details": ["up to 5 fixed landmarks useful to match a future photo of the same spot"],
  "tags": ["5 to 10 short lowercase search tags"],
  "sdgs": [up to 3 numbers (1-17) of the UN Sustainable Development Goals this photo visibly relates to,
           e.g. 6 for water points, 11 or 12 for waste cleanup, 13 for climate action, 15 for tree planting;
           empty list if none],
  "sdg_reason": "one short factual sentence linking what is visible to those goals",
  "stage": "before" | "during" | "after" | "other"  (relative to the project's work: "before" shows the problem
           untouched, e.g. litter or a bare plot; "during" shows people doing the work; "after" shows the result,
           e.g. a cleared area or planted saplings; "other" if unclear),
  "category": one of "waste", "planting", "water", "construction", "education", "health", "community", "site", "other"
}}"""

PAIR_PROMPT = """You compare two field photos for an evidence-verification platform.
The FIRST image is the earlier "before" photo, the SECOND is the later "after" photo.
Project: {name}. {description}

Describe only visible differences. Do not claim causes or outcomes you cannot see.
Return JSON with exactly these keys:
{{
  "same_site_likely": true/false,
  "same_site_reason": "one sentence naming the landmarks that match or differ",
  "change_summary": "two or three plain sentences describing the visible change",
  "changes": ["up to 5 specific visible changes"],
  "confidence": "low" | "medium" | "high"
}}"""


class VisionError(Exception):
    pass


def _clean_observations(items) -> list[str]:
    out = []
    for s in items or []:
        s = str(s).strip()
        if s and not any(p in s.lower() for p in INFERENCE_PHRASES):
            out.append(s)
    return out


def _years(texts) -> list[int]:
    ys = set()
    for t in texts or []:
        for m in re.finditer(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)", str(t)):
            ys.add(int(m.group(1)))
    return sorted(ys)


class VisionService:
    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            from google import genai
            from google.genai import types
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY,
                                       http_options=types.HttpOptions(timeout=60_000))

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def ask_json(self, prompt: str, images: list[tuple[bytes, str]]) -> dict:
        if not self.client:
            raise VisionError("GEMINI_API_KEY is not configured.")
        from google.genai import types
        parts = [types.Part.from_bytes(data=b, mime_type=m) for b, m in images] + [prompt]
        try:
            resp = self.client.models.generate_content(
                model=settings.GEMINI_MODEL, contents=parts,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
            text = resp.text or ""
        except Exception as e:
            raise VisionError(f"Gemini request failed: {str(e)[:300]}")
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            raise VisionError("Gemini did not return valid JSON.")

    def analyze_evidence(self, image_path: str, mime_type: str, project=None) -> dict:
        """Returns {"status", "provider", "data": EvidenceAnalysis | None, "error"}."""
        if not self.client:
            return {"status": "FAILED", "provider": "none", "data": None, "error": "GEMINI_API_KEY is not configured."}
        try:
            with open(image_path, "rb") as f:
                data = f.read()
            prompt = EVIDENCE_PROMPT.format(name=getattr(project, "name", "") or "Field project",
                                            description=getattr(project, "description", "") or "Not described")
            raw = self.ask_json(prompt, [(data, mime_type or "image/jpeg")])
        except (VisionError, OSError) as e:
            return {"status": "FAILED", "provider": "gemini", "data": None, "error": str(e)}
        raw["observations"] = _clean_observations(raw.get("observations"))
        raw["visible_years"] = _years((raw.get("visible_text") or []) + [raw.get("description", "")])
        analysis = EvidenceAnalysis(
            observations=raw["observations"],
            objects=[str(x) for x in raw.get("objects") or []],
            activities=[str(x) for x in raw.get("activities") or []],
            raw_response=raw,
        )
        return {"status": "COMPLETED", "provider": "gemini", "data": analysis, "error": None}

    def describe_pair(self, before: tuple[bytes, str], after: tuple[bytes, str], project=None) -> dict:
        prompt = PAIR_PROMPT.format(name=getattr(project, "name", "") or "Field project",
                                    description=getattr(project, "description", "") or "")
        return self.ask_json(prompt, [before, after])


vision_service = VisionService()
