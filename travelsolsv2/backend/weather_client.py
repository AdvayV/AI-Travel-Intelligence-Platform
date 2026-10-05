"""One shared weather feed, with TLS verification, single-flight and disk cache."""
import json
import logging
import math
import os
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from tls_config import enable_system_trust_store
enable_system_trust_store()
import httpx

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
AIRPORT_COORDS.update({"HND":(35.5494,139.7798),"TPE":(25.0777,121.2328),"AUH":(24.4330,54.6511)})
CACHE_DIR = Path(__file__).parent/".cache"/"weather"
_DETAIL_CACHE = {}
_DETAIL_TTL = 1800
_FAILURE_TTL = 300
_STALE_TTL = 21600
_locks = {code:threading.Lock() for code in AIRPORT_COORDS}
STATUS = {"status":"not_checked","last_error":None,"provider":"Open-Meteo"}

WMO = {
    0:("Clear sky",1),1:("Mainly clear",.95),2:("Partly cloudy",.9),3:("Overcast",.75),
    45:("Fog",.45),48:("Rime fog",.4),51:("Light drizzle",.65),53:("Drizzle",.55),55:("Heavy drizzle",.4),
    56:("Freezing drizzle",.3),57:("Heavy freezing drizzle",.2),
    61:("Light rain",.6),63:("Rain",.45),65:("Heavy rain",.25),66:("Freezing rain",.25),67:("Heavy freezing rain",.15),
    71:("Light snow",.5),73:("Snow",.35),75:("Heavy snow",.2),77:("Snow grains",.4),
    80:("Light rain showers",.55),81:("Rain showers",.4),82:("Heavy rain showers",.2),
    85:("Snow showers",.3),86:("Heavy snow showers",.15),95:("Thunderstorm",.15),
    96:("Thunderstorm with hail",.1),99:("Severe thunderstorm with hail",.05),
}

def _number(value):
    try:
        number=float(value)
        return number if math.isfinite(number) else None
    except (ValueError,TypeError): return None

def _value(daily,key,index):
    values=daily.get(key,[])
    return _number(values[index]) if index<len(values) else None

def normalize_daily(daily):
    days=[]
    for i,day_date in enumerate(daily.get("time",[])[:14]):
        try: datetime.strptime(day_date,"%Y-%m-%d")
        except (ValueError,TypeError): continue
        code=_value(daily,"weather_code",i)
        code=int(code) if code is not None else None
        high=_value(daily,"temperature_2m_max",i)
        low=_value(daily,"temperature_2m_min",i)
        rain=_value(daily,"precipitation_sum",i)
        probability=_value(daily,"precipitation_probability_max",i)
        wind=_value(daily,"wind_speed_10m_max",i)
        if wind is None: wind=_value(daily,"windspeed_10m_max",i)
        condition,condition_score=WMO.get(code,("Unknown",None))
        # Missing WMO is missing weather, not clear sky; optional values stay null.
        appeal=None
        if condition_score is not None:
            comfort=.5 if high is None else max(0,1-max(18-high,high-30,0)/20)
            appeal=.8*condition_score+.2*comfort
            if wind is not None: appeal-=min(.15,max(0,wind-25)/200)
            if rain is not None: appeal-=min(.1,max(0,rain)/200)
            appeal=round(max(0,min(1,appeal)),3)
        days.append({"date":day_date,"wmo_code":code,"weather_code":code,"condition":condition,
            "temp_max_c":high,"temp_min_c":low,"precipitation_mm":rain,
            "precip_prob_pct":probability,"wind_kmh":wind,"appeal":appeal,
            "emoji":"☀️" if code in (0,1,2) else "🌧" if code in (61,63,65,80,81,82) else "☁️"})
    return days

def _fetch_raw(lat,lon,days=14):
    if os.getenv("WEATHER_NETWORK_ENABLED","true").lower()=="false": return None
    try:
        with httpx.Client(timeout=12) as client:
            response=client.get("https://api.open-meteo.com/v1/forecast",params={
                "latitude":lat,"longitude":lon,
                "daily":"temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code,precipitation_probability_max,wind_speed_10m_max",
                "forecast_days":days,"timezone":"auto","wind_speed_unit":"kmh"})
            response.raise_for_status()
            daily=response.json().get("daily")
            if not isinstance(daily,dict): raise ValueError("Missing daily weather")
            STATUS.update(status="live",last_error=None)
            return daily
    except Exception as exc:
        status=getattr(getattr(exc,"response",None),"status_code",None)
        error=f"HTTP_{status}" if status else type(exc).__name__
        STATUS.update(status="unavailable",last_error=error)
        logger.warning("Weather feed unavailable (%s); cached/neutral fallback",error)
        return None

def _unknown(code):
    return {"dest_code":code,"overall_appeal":None,"comfort_label":"Weather unavailable",
        "today_condition":"Unknown","today_emoji":"?","today_temp_max_c":None,"today_temp_min_c":None,
        "avg_temp_max_c":None,"today_precip_mm":None,"today_wind_kmh":None,
        "days":[],"source":"unavailable","fetched_at":None,"stale":False}

def _read_disk(code,now):
    try:
        entry=json.loads((CACHE_DIR/(code+".json")).read_text(encoding="utf-8"))
        age=now-entry["timestamp"]
        if 0<=age<=_STALE_TTL and entry["data"]["dest_code"]==code:
            return entry["data"],age
    except (OSError,ValueError,TypeError,KeyError): pass
    return None,None

def _write_disk(code,data,now):
    try:
        CACHE_DIR.mkdir(parents=True,exist_ok=True)
        target=CACHE_DIR/(code+".json")
        temporary=CACHE_DIR/(code+".tmp")
        temporary.write_text(json.dumps({"timestamp":now,"data":data}),encoding="utf-8")
        temporary.replace(target)
    except OSError:
        logger.debug("Weather disk cache unavailable; in-memory cache retained")

def get_weather_detail(dest_code):
    code=dest_code.upper()
    if code not in AIRPORT_COORDS: return _unknown(code)
    with _locks[code]:
        now=time.time()
        cached=_DETAIL_CACHE.get(code)
        if cached and now<cached["expires_at"]: return cached["data"]
        disk,age=_read_disk(code,now)
        if disk and age<_DETAIL_TTL:
            _DETAIL_CACHE[code]={"data":disk,"expires_at":now+_DETAIL_TTL-age}
            return disk
        raw=_fetch_raw(*AIRPORT_COORDS[code])
        days=normalize_daily(raw) if raw else []
        usable=[d for d in days if d["appeal"] is not None]
        if usable:
            appeal=round(sum(d["appeal"] for d in usable)/len(usable),3)
            temperatures=[d["temp_max_c"] for d in days if d["temp_max_c"] is not None]
            today=days[0]
            result={"dest_code":code,"overall_appeal":appeal,
                "comfort_label":"Good travel comfort" if appeal>=.7 else "Mixed travel comfort" if appeal>=.5 else "Poor travel comfort",
                "today_emoji":today["emoji"],"today_condition":today["condition"],
                "avg_temp_max_c":round(sum(temperatures)/len(temperatures),1) if temperatures else None,
                "today_temp_max_c":today["temp_max_c"],"today_temp_min_c":today["temp_min_c"],
                "today_precip_mm":today["precipitation_mm"],"today_wind_kmh":today["wind_kmh"],
                "days":days,"source":"Open-Meteo (live)","stale":False,
                "fetched_at":datetime.now(timezone.utc).isoformat()}
            _write_disk(code,result,now)
            ttl=_DETAIL_TTL
        elif disk:
            # Keep old dates intact; missing future dates are never invented.
            result={**disk,"source":"Open-Meteo (stale)","stale":True}
            ttl=_FAILURE_TTL
        else:
            result=_unknown(code)
            ttl=_FAILURE_TTL
        _DETAIL_CACHE[code]={"data":result,"expires_at":now+ttl}
        return result

def get_weather_score(dest_codes):
    return {code:get_weather_detail(code)["overall_appeal"] for code in dest_codes}
