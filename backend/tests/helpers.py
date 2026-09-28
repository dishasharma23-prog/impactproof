import io
import json
import random
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import piexif
from PIL import Image, ImageDraw

FIX = Path(__file__).parent / "fixtures"


def to_dms(value):
    value = abs(value)
    d = int(value); m = int((value - d) * 60); s = (value - d - m / 60) * 3600
    f = Fraction(s).limit_denominator(10000)
    return ((d, 1), (m, 1), (f.numerator, f.denominator))


def photo(seed, lat=None, lng=None, when: datetime | None = None, crop=0, software=None, fmt="JPEG"):
    rnd = random.Random(seed)
    im = Image.new("RGB", (800, 600), (rnd.randint(0, 255),) * 3)
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y = rnd.randint(0, 780), rnd.randint(0, 580)
        d.rectangle([x, y, x + rnd.randint(20, 200), y + rnd.randint(20, 200)],
                    fill=(rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    if crop:
        im = im.crop((crop, crop, 800 - crop, 600 - crop)).resize((760, 570))
    exif = {"0th": {piexif.ImageIFD.Make: b"Google", piexif.ImageIFD.Model: b"Pixel 8"}, "Exif": {}, "GPS": {}}
    if software:
        exif["0th"][piexif.ImageIFD.Software] = software.encode()
    if when:
        exif["Exif"][piexif.ExifIFD.DateTimeOriginal] = when.strftime("%Y:%m:%d %H:%M:%S").encode()
    if lat is not None:
        exif["GPS"] = {1: b"N", 2: to_dms(lat), 3: b"E", 4: to_dms(lng)}
    buf = io.BytesIO()
    if fmt == "JPEG":
        im.save(buf, "JPEG", quality=90, exif=piexif.dump(exif))
    else:
        im.save(buf, fmt)
    return buf.getvalue()


def ai_generated_photo(seed=99) -> bytes:
    """A JPEG carrying C2PA content credentials that declare AI generation (signed with a test cert)."""
    import c2pa
    src = io.BytesIO(photo(seed, fmt="JPEG"))
    info = c2pa.C2paSignerInfo(b"es256", (FIX / "chain.pem").read_bytes(), (FIX / "leaf.p8").read_bytes(), None)
    signer = c2pa.Signer.from_info(info)
    manifest = {"claim_generator_info": [{"name": "Test image generator", "version": "1.0"}], "title": "gen.jpg",
                "format": "image/jpeg", "assertions": [{"label": "c2pa.actions", "data": {"actions": [
                    {"action": "c2pa.created",
                     "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
                     "softwareAgent": {"name": "Test Diffusion"}}]}}]}
    out = io.BytesIO()
    c2pa.Builder(json.dumps(manifest)).sign(signer, "image/jpeg", src, out)
    return out.getvalue()


def ai_result(**overrides):
    raw = {"observations": ["Two people pick up plastic bottles."], "objects": ["bottles"], "activities": ["litter pickup"],
           "activity": "volunteers collecting litter", "description": "Two people pick up litter.",
           "people_count_estimate": 2, "sapling_count_estimate": None, "waste_visible": True, "water_visible": False,
           "vegetation_visible": True, "construction_visible": False, "damage_visible": False, "ground_wet": False,
           "rain_falling": False, "visible_text": [], "visible_organizations": [], "is_collage_or_composite": False,
           "collage_reason": "", "looks_like_screen_or_stock": False, "screen_or_stock_reason": "",
           "appears_ai_generated": False, "ai_generated_reason": "", "relevant_to_project": True,
           "relevance_reason": "Shows litter collection.", "comparable_details": [], "tags": ["cleanup"], "visible_years": []}
    raw.update(overrides)
    return raw
