"""Historical weather at the time and place a photo was taken (Open-Meteo, free, no key)."""
from datetime import datetime, timedelta

import httpx

from app.core.config import settings


def lookup(lat: float, lng: float, when: datetime) -> dict | None:
    """Precipitation around the capture time. Times are local to the location, like camera EXIF times."""
    if not settings.WEATHER_ENABLED or lat is None or lng is None or when is None:
        return None
    if when > datetime.now() + timedelta(days=1):
        return None
    start = (when - timedelta(days=1)).date().isoformat()
    end = when.date().isoformat()
    recent = (datetime.now() - when).days < 60
    url = "https://api.open-meteo.com/v1/forecast" if recent else "https://archive-api.open-meteo.com/v1/archive"
    params = {"latitude": round(lat, 4), "longitude": round(lng, 4), "start_date": start, "end_date": end,
              "hourly": "precipitation,cloud_cover", "timezone": "auto"}
    try:
        r = httpx.get(url, params=params, timeout=6)
        r.raise_for_status()
        hourly = r.json().get("hourly", {})
    except Exception as e:
        return {"error": f"Weather service unavailable: {str(e)[:120]}"}

    times = [datetime.fromisoformat(t) for t in hourly.get("time", [])]
    precip = hourly.get("precipitation", []) or []
    cloud = hourly.get("cloud_cover", []) or []
    if not times or not precip:
        return {"error": "No weather data for this place and time."}
    hour = when.replace(minute=0, second=0, microsecond=0)

    def total(hours_before):
        lo = hour - timedelta(hours=hours_before)
        return round(sum((p or 0) for t, p in zip(times, precip) if lo < t <= hour), 1)

    at_hour = next(((p or 0) for t, p in zip(times, precip) if t == hour), None)
    cloud_at = next((c for t, c in zip(times, cloud) if t == hour), None)
    return {"precip_24h_mm": total(24), "precip_3h_mm": total(3), "precip_at_hour_mm": at_hour,
            "cloud_cover_pct": cloud_at, "source": "Open-Meteo", "fetched_at": datetime.utcnow().isoformat()}
