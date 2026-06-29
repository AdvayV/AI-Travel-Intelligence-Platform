import httpx
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

AIRPORT_COORDS = {
    "DXB": (25.2532, 55.3657), "LHR": (51.4700, -0.4543), "SIN": (1.3644, 103.9915),
    "BKK": (13.6900, 100.7501), "JFK": (40.6413, -73.7781), "DOH": (25.2730, 51.6080),
    "KUL": (2.7456, 101.7099), "NRT": (35.7647, 140.3863), "CDG": (49.0097, 2.5479),
    "SYD": (-33.9399, 151.1753), "FRA": (50.0333, 8.5705), "AMS": (52.3105, 4.7683),
    "ORD": (41.9742, -87.9073), "LAX": (33.9416, -118.4085), "DFW": (32.8998, -97.0403),
    "SFO": (37.6213, -122.3790), "HKG": (22.3080, 113.9185), "ICN": (37.4602, 126.4407),
    "FCO": (41.7999, 12.2462), "ZRH": (47.4582, 8.5555), "VIE": (48.1103, 16.5697),
    "MUC": (48.3537, 11.7861), "CPH": (55.6180, 12.6560), "ARN": (59.6519, 17.9186),
    "IST": (41.2590, 28.7420), "CAI": (30.1219, 31.4056), "NBO": (-1.3192, 36.9278),
    "JNB": (-26.1367, 28.2411), "BOM": (19.0896, 72.8656), "DEL": (28.5562, 77.1000),
    "BLR": (13.1986, 77.7066), "MAA": (12.9941, 80.1709), "HYD": (17.2403, 78.4294),
    "CMB": (7.1803, 79.8833), "DAC": (23.8433, 90.4013), "KTM": (27.6966, 85.3592),
    "PEK": (40.0725, 116.5972), "PVG": (31.1443, 121.8083), "CAN": (23.3924, 113.2988),
    "RGN": (16.9043, 96.1332), "SGN": (10.8188, 106.6520), "HAN": (21.2212, 105.8072),
    "CGK": (-6.1256, 106.6558), "MNL": (14.5090, 121.0194), "KIX": (34.4320, 135.2304),
    "NGO": (34.8584, 136.8054), "CTS": (42.7752, 141.6923), "MEL": (-37.6690, 144.8410),
    "BNE": (-27.3842, 153.1175), "AKL": (-37.0082, 174.7850), "PER": (-31.9385, 115.9672),
    "YYZ": (43.6777, -79.6248), "JED": (21.6796, 39.1565)
}

# WMO weather code → (label, travel appeal multiplier, emoji)
WMO_LOOKUP = {
    range(0, 1):   ("Clear Sky",        1.25, "☀️"),
    range(1, 3):   ("Mostly Clear",     1.20, "🌤"),
    range(3, 4):   ("Overcast",         1.00, "☁️"),
    range(45, 50): ("Fog",              0.80, "🌫"),
    range(51, 56): ("Light Drizzle",    0.75, "🌦"),
    range(56, 68): ("Heavy Drizzle",    0.65, "🌧"),
    range(71, 78): ("Snow",             0.50, "❄️"),
    range(80, 83): ("Rain Showers",     0.70, "🌧"),
    range(85, 87): ("Snow Showers",     0.45, "🌨"),
    range(95, 96): ("Thunderstorm",     0.35, "⛈"),
    range(96, 100):("Heavy Thunderstorm", 0.30, "⛈"),
}

def _wmo_info(code: int) -> tuple[str, float, str]:
    """Return (label, multiplier, emoji) for a WMO weather code."""
    code = int(code or 0)
    for r, info in WMO_LOOKUP.items():
        if code in r:
            return info
    return ("Unknown", 1.0, "🌡")

# Two-tier cache: score-only (light) + full detail (heavy)
_SCORE_CACHE: dict = {}   # code → {score, expires_at}
_DETAIL_CACHE: dict = {}  # code → {full weather dict, expires_at}

_SCORE_TTL  = 3600    # 1 hour for scoring pipeline
_DETAIL_TTL = 1800    # 30 min for the live detail panel


def _fetch_raw(lat: float, lon: float, days: int = 7) -> dict | None:
    """Fetch raw Open-Meteo daily data. Returns the 'daily' dict or None on failure."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        f"weather_code,precipitation_probability_max,windspeed_10m_max"
        f"&forecast_days={days}"
        f"&timezone=auto"
        f"&wind_speed_unit=kmh"
    )
    try:
        resp = httpx.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        return data.get("daily", {})
    except Exception as e:
        logger.warning(f"Open-Meteo fetch failed: {e}")
        return None


def get_weather_score(dest_codes: list[str]) -> dict[str, float]:
    """
    Lightweight scoring call used by the pipeline.
    Returns {code: float 0-1} for each destination.
    Uses 7-day window for speed.
    """
    scores: dict[str, float] = {}
    now = time.time()

    for code in dest_codes:
        # Cache hit
        if code in _SCORE_CACHE and now < _SCORE_CACHE[code]["expires_at"]:
            scores[code] = _SCORE_CACHE[code]["score"]
            continue

        if code not in AIRPORT_COORDS:
            scores[code] = 0.5
            continue

        lat, lon = AIRPORT_COORDS[code]
        daily = _fetch_raw(lat, lon, days=7)

        if not daily:
            scores[code] = 0.5
            continue

        wmo_codes = daily.get("weather_code", [])
        temp_maxes = daily.get("temperature_2m_max", [])
        days_count = min(7, len(wmo_codes))

        if days_count == 0:
            scores[code] = 0.5
            continue

        points = 0.0
        for i in range(days_count):
            wc = int(wmo_codes[i] or 0)
            tmax = temp_maxes[i]
            _, mult, _ = _wmo_info(wc)
            points += mult  # 0.30–1.25 per day

            # Temperature bonus: ideal travel temp 18–30°C
            if tmax is not None:
                if 18 <= tmax <= 30:
                    points += 0.25
                elif tmax > 38 or tmax < 5:
                    points -= 0.30

        max_possible = days_count * (1.25 + 0.25)  # max points per day
        score = max(0.0, min(1.0, points / max_possible))
        scores[code] = round(score, 3)
        _SCORE_CACHE[code] = {"score": score, "expires_at": now + _SCORE_TTL}

    return scores


def get_weather_detail(dest_code: str) -> dict:
    """
    Full weather detail for the forecast panel — temperatures in °C,
    7-day daily breakdown, current conditions, travel appeal score.
    Called on-demand when a route card is clicked.
    """
    now = time.time()

    # Detailed cache hit
    if dest_code in _DETAIL_CACHE and now < _DETAIL_CACHE[dest_code]["expires_at"]:
        return _DETAIL_CACHE[dest_code]["data"]

    if dest_code not in AIRPORT_COORDS:
        return _make_unknown_detail(dest_code)

    lat, lon = AIRPORT_COORDS[dest_code]
    daily = _fetch_raw(lat, lon, days=14)

    if not daily:
        return _make_unknown_detail(dest_code)

    dates       = daily.get("time", [])
    wmo_codes   = daily.get("weather_code", [])
    temp_maxes  = daily.get("temperature_2m_max", [])
    temp_mins   = daily.get("temperature_2m_min", [])
    precip      = daily.get("precipitation_sum", [])
    precip_prob = daily.get("precipitation_probability_max", [])
    wind        = daily.get("windspeed_10m_max", [])

    days_data = []
    total_appeal = 0.0

    for i in range(min(14, len(dates))):
        wc    = int(wmo_codes[i] or 0) if i < len(wmo_codes) else 0
        tmax  = round(temp_maxes[i], 1) if i < len(temp_maxes) and temp_maxes[i] is not None else None
        tmin  = round(temp_mins[i],  1) if i < len(temp_mins)  and temp_mins[i]  is not None else None
        prep  = round(precip[i],     1) if i < len(precip)     and precip[i]     is not None else 0.0
        prob  = int(precip_prob[i]     ) if i < len(precip_prob) and precip_prob[i] is not None else 0
        wind_ = round(wind[i],       1) if i < len(wind)        and wind[i]       is not None else None

        label, appeal_mult, emoji = _wmo_info(wc)

        # Temp comfort bonus
        temp_bonus = 0.0
        if tmax is not None:
            if 18 <= tmax <= 30:
                temp_bonus = 0.20
            elif tmax > 38 or tmax < 5:
                temp_bonus = -0.25

        day_appeal = min(1.0, max(0.0, appeal_mult + temp_bonus))
        total_appeal += day_appeal

        days_data.append({
            "date":           dates[i] if i < len(dates) else "",
            "wmo_code":       wc,
            "condition":      label,
            "emoji":          emoji,
            "temp_max_c":     tmax,
            "temp_min_c":     tmin,
            "precipitation_mm": prep,
            "precip_prob_pct":  prob,
            "wind_kmh":       wind_,
            "appeal":         round(day_appeal, 2),
        })

    # Overall 7-day appeal score 0–1
    n = len(days_data)
    overall_appeal = round(total_appeal / n, 3) if n > 0 else 0.5

    # Today's condition label
    today = days_data[0] if days_data else {}
    _, _, today_emoji = _wmo_info(today.get("wmo_code", 0))

    # Travel comfort summary
    avg_max = sum(d["temp_max_c"] for d in days_data if d["temp_max_c"] is not None) / max(1, n)
    if overall_appeal >= 0.85:
        comfort_label = "Excellent for travel ✈️"
    elif overall_appeal >= 0.70:
        comfort_label = "Good conditions 👍"
    elif overall_appeal >= 0.50:
        comfort_label = "Mixed — pack layers 🧥"
    elif overall_appeal >= 0.30:
        comfort_label = "Poor — demand suppressed 🌧"
    else:
        comfort_label = "Severe — avoid if possible ⚠️"

    result = {
        "dest_code":        dest_code,
        "overall_appeal":   overall_appeal,
        "comfort_label":    comfort_label,
        "today_emoji":      today_emoji,
        "avg_temp_max_c":   round(avg_max, 1),
        "today_temp_max_c": today.get("temp_max_c"),
        "today_temp_min_c": today.get("temp_min_c"),
        "today_condition":  today.get("condition", "Unknown"),
        "today_precip_mm":  today.get("precipitation_mm", 0),
        "today_wind_kmh":   today.get("wind_kmh"),
        "days":             days_data,
        "fetched_at":       datetime.now(timezone.utc).isoformat(),
        "source":           "Open-Meteo (live)",
    }

    _DETAIL_CACHE[dest_code] = {"data": result, "expires_at": now + _DETAIL_TTL}
    return result


def _make_unknown_detail(code: str) -> dict:
    return {
        "dest_code":       code,
        "overall_appeal":  0.5,
        "comfort_label":   "Weather data unavailable",
        "today_emoji":     "❓",
        "avg_temp_max_c":  None,
        "today_temp_max_c": None,
        "today_temp_min_c": None,
        "today_condition": "Unknown",
        "today_precip_mm": None,
        "today_wind_kmh":  None,
        "days":            [],
        "fetched_at":      datetime.now(timezone.utc).isoformat(),
        "source":          "unavailable",
    }
