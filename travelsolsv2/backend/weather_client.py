import httpx
import logging
import time

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

WEATHER_CACHE = {}

def get_weather_score(dest_codes: list[str]) -> dict:
    scores = {}
    now = time.time()
    
    for code in dest_codes:
        if code in WEATHER_CACHE and now < WEATHER_CACHE[code]["expires_at"]:
            scores[code] = WEATHER_CACHE[code]["score"]
            continue
            
        if code not in AIRPORT_COORDS:
            scores[code] = 0.5
            continue
            
        lat, lon = AIRPORT_COORDS[code]
        # weather_code is the current field name (weathercode was deprecated in Open-Meteo v1)
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
            f"&forecast_days=16"
            f"&timezone=auto"
        )
        
        try:
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            daily = data.get("daily", {})
            # Support both old and new field names gracefully
            weathercodes = daily.get("weather_code", daily.get("weathercode", []))
            temp_maxes = daily.get("temperature_2m_max", [])
            
            points = 0.0
            days = min(16, len(weathercodes))
            if days == 0:
                scores[code] = 0.5
                continue
                
            for i in range(days):
                wc = weathercodes[i] or 0
                tmax = temp_maxes[i]
                
                if wc < 50:
                    points += 1.0
                elif 50 <= wc <= 69:
                    points += 0.3
                # >= 70 (snow/storm) gives 0 points
                
                if tmax is not None:
                    if 18 <= tmax <= 30:
                        points += 0.5
                    elif tmax > 38:
                        points -= 0.5
            
            # Normalise over max possible points for 'days' days (1.5 pts/day)
            max_points = days * 1.5
            final_score = max(0.0, min(1.0, points / max_points))
            scores[code] = final_score
            WEATHER_CACHE[code] = {"score": final_score, "expires_at": now + 3600}
            
        except Exception as e:
            logger.warning(f"Weather API failed for {code}: {e}")
            scores[code] = 0.5
            
    return scores
