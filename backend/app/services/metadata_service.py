"""Reads camera metadata (EXIF) from JPEG, PNG and WEBP files."""
from datetime import datetime
from typing import Any, Dict

from PIL import Image

GPS_IFD = 0x8825
EXIF_IFD = 0x8769


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    return str(value).replace("\x00", "").strip()


def _to_degrees(value):
    try:
        d, m, s = value
        return float(d) + float(m) / 60 + float(s) / 3600
    except Exception:
        return None


class MetadataService:
    @staticmethod
    def extract_metadata(file_path: str) -> Dict[str, Any]:
        meta = {"capture_time": None, "latitude": None, "longitude": None, "device_info": None,
                "software": None, "width": None, "height": None}
        try:
            with Image.open(file_path) as im:
                meta["width"], meta["height"] = im.size
                exif = im.getexif()
                if not exif:
                    return meta
                make, model = _clean(exif.get(271)), _clean(exif.get(272))
                device = model if make and model.lower().startswith(make.lower()) else " ".join(x for x in (make, model) if x)
                meta["device_info"] = device or None
                meta["software"] = _clean(exif.get(305)) or None

                exif_ifd = exif.get_ifd(EXIF_IFD)
                raw = exif_ifd.get(36867) or exif_ifd.get(36868) or exif.get(306)
                if raw:
                    try:
                        meta["capture_time"] = datetime.strptime(_clean(raw)[:19], "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass

                gps = exif.get_ifd(GPS_IFD)
                if gps and 2 in gps and 4 in gps:
                    lat, lng = _to_degrees(gps[2]), _to_degrees(gps[4])
                    if lat is not None and lng is not None and not (lat == 0 and lng == 0):
                        if _clean(gps.get(1, "N")).upper().startswith("S"):
                            lat = -lat
                        if _clean(gps.get(3, "E")).upper().startswith("W"):
                            lng = -lng
                        meta["latitude"], meta["longitude"] = round(lat, 6), round(lng, 6)
        except Exception as e:
            print(f"Metadata extraction error: {e}")
        return meta
