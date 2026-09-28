"""Create the three planted test cases for your demo from your real photos.

    python -m scripts.make_test_cases photo1.jpg photo2.jpg photo3.jpg

Use three DIFFERENT real photos, so each case shows exactly one problem:
  photo1  upload it normally first; the reused copy is made from it
  photo2  the wrong-location copy is made from it (do not upload photo2 itself)
  photo3  the WhatsApp copy is made from it (do not upload photo3 itself)
With one photo only, all three copies come from it, and every copy is also (correctly) flagged as reuse.

Writes to backend/test_cases/:
  reused_photo.jpg         cropped, recompressed copy with no metadata, like a photo saved from an old
                           report or social post (should be flagged as reuse: Suspicious)
  wrong_location.jpg       same photo with GPS moved about 40 km away (should fail the location check)
  forwarded_on_whatsapp.jpg all metadata removed and resized (should be Unverifiable, NOT Suspicious)

Be open about this in your pitch: these are a controlled test set that shows each check working.
"""
import sys
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

import piexif
from PIL import Image, ImageOps

OUT = Path(__file__).resolve().parent.parent / "test_cases"


def to_dms(value):
    value = abs(value)
    d = int(value); m = int((value - d) * 60); s = (value - d - m / 60) * 3600
    f = Fraction(s).limit_denominator(10000)
    return ((d, 1), (m, 1), (f.numerator, f.denominator))


def load_exif(path):
    try:
        return piexif.load(str(path))
    except Exception:
        return {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}


def set_gps(exif, lat, lng):
    exif["GPS"] = {
        piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S", piexif.GPSIFD.GPSLatitude: to_dms(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lng >= 0 else b"W", piexif.GPSIFD.GPSLongitude: to_dms(lng),
    }


def read_gps(exif):
    g = exif.get("GPS") or {}
    try:
        def conv(v): return v[0][0] / v[0][1] + v[1][0] / v[1][1] / 60 + v[2][0] / v[2][1] / 3600
        lat, lng = conv(g[piexif.GPSIFD.GPSLatitude]), conv(g[piexif.GPSIFD.GPSLongitude])
        if g.get(piexif.GPSIFD.GPSLatitudeRef) == b"S": lat = -lat
        if g.get(piexif.GPSIFD.GPSLongitudeRef) == b"W": lng = -lng
        return lat, lng
    except Exception:
        return None


def save(img, exif, name):
    exif["thumbnail"] = None
    exif.pop("1st", None)
    img.save(OUT / name, "JPEG", quality=88, exif=piexif.dump(exif) if exif is not None else b"")
    print("wrote", OUT / name)


def _open(src):
    with Image.open(src) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def main(src, src_location=None, src_whatsapp=None):
    OUT.mkdir(parents=True, exist_ok=True)
    src_location, src_whatsapp = src_location or src, src_whatsapp or src
    exif = load_exif(src_location)
    im = _open(src)

    # 1. Reused photo: small crop + resize + recompress, metadata gone (as when saved from a web page)
    w, h = im.size
    reused = im.crop((int(w * .03), int(h * .03), int(w * .97), int(h * .97))).resize((int(w * .9), int(h * .9)))
    reused.save(OUT / "reused_photo.jpg", "JPEG", quality=80)
    print("wrote", OUT / "reused_photo.jpg")

    # 2. Wrong location: GPS moved ~40 km north-east
    e2 = load_exif(src_location); e2["0th"][piexif.ImageIFD.Orientation] = 1
    gps = read_gps(e2) or read_gps(load_exif(src)) or (26.9, 75.8)
    set_gps(e2, gps[0] + 0.25, gps[1] + 0.25)
    save(_open(src_location), e2, "wrong_location.jpg")

    # 3. Forwarded on WhatsApp: no metadata, resized to 1600 px
    wa = _open(src_whatsapp); wa.thumbnail((1600, 1600))
    wa.save(OUT / "forwarded_on_whatsapp.jpg", "JPEG", quality=75)
    print("wrote", OUT / "forwarded_on_whatsapp.jpg")
    if not read_gps(exif):
        print("\nNote: your source photo has no GPS, so the wrong-location copy got a placeholder position.")


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 4:
        sys.exit(__doc__)
    main(*[Path(a) for a in sys.argv[1:]])
    if len(sys.argv) < 4:
        print("\nTip: pass three different photos so each test case shows exactly one problem (see the top of this file).")
