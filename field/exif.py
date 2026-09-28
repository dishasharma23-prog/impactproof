"""Writes capture time, GPS and device into photos taken on the field device, so ImpactProof HQ can
check them once they sync (browser camera frames carry no metadata of their own)."""
import io
from datetime import datetime
from fractions import Fraction

import piexif
from PIL import Image


def _dms(value):
    value = abs(value)
    d = int(value); m = int((value - d) * 60); s = (value - d - m / 60) * 3600
    f = Fraction(s).limit_denominator(10000)
    return ((d, 1), (m, 1), (f.numerator, f.denominator))


def stamp(data: bytes, when_local: datetime, lat=None, lng=None, device="ImpactProof Field") -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        exif = {"0th": {piexif.ImageIFD.Make: b"ImpactProof", piexif.ImageIFD.Model: device.encode()[:60],
                        piexif.ImageIFD.Software: b"ImpactProof Field"},
                "Exif": {piexif.ExifIFD.DateTimeOriginal: when_local.strftime("%Y:%m:%d %H:%M:%S").encode()},
                "GPS": {}}
        if lat is not None and lng is not None:
            exif["GPS"] = {1: b"N" if lat >= 0 else b"S", 2: _dms(lat), 3: b"E" if lng >= 0 else b"W", 4: _dms(lng)}
        out = io.BytesIO()
        im.save(out, "JPEG", quality=90, exif=piexif.dump(exif))
        return out.getvalue()
