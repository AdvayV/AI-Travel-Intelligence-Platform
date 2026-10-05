"""Atomic local forecasting refresh. Weather is the only network data feed."""
import logging
import threading
import time
from copy import deepcopy
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from travel_client import get_top_destinations
from chronos_engine import forecast_batch,apply_weather,MODEL_ID
from weather_client import get_weather_detail
from scoring import get_base_price,rank_routes

logger=logging.getLogger(__name__)
FORECAST_CACHE={}
LAST_REFRESH=None
REFRESH_STATUS={"running":False,"error":None,"duration_seconds":None}
_cache_lock=threading.Lock()
_refresh_lock=threading.Lock()
_scheduler=None
ORIGINS=["BOM","DEL","BLR","MAA","HYD"]
CITY_NAMES = {
    "DXB": "Dubai", "LHR": "London", "SIN": "Singapore", "BKK": "Bangkok",
    "JFK": "New York", "DOH": "Doha", "KUL": "Kuala Lumpur", "NRT": "Tokyo",
    "CDG": "Paris", "SYD": "Sydney", "FRA": "Frankfurt", "AMS": "Amsterdam",
    "BOM": "Mumbai", "DEL": "Delhi", "BLR": "Bengaluru", "MAA": "Chennai",
    "HYD": "Hyderabad", "YYZ": "Toronto", "SFO": "San Francisco", "CMB": "Colombo",
    "ORD": "Chicago", "JED": "Jeddah", "MEL": "Melbourne", "BNE": "Brisbane",
    "PER": "Perth", "AKL": "Auckland", "HKG": "Hong Kong", "HND": "Tokyo Haneda",
    "ICN": "Seoul", "TPE": "Taipei", "MNL": "Manila", "CGK": "Jakarta", "SGN": "Ho Chi Minh City"
}

def refresh_status():
    return dict(REFRESH_STATUS)

def cache_snapshot():
    with _cache_lock: return deepcopy(FORECAST_CACHE)

def recompute_forecast_for_day(route,day_offset=0):
    # Also used by the deterministic booking agent; beyond the 28-day horizon
    # is rejected, not silently clamped to an unrelated date.
    if not 0<=day_offset<28: raise ValueError("Day offset must be between 0 and 27")
    daily=route["daily_forecast"][day_offset]
    return {**deepcopy(route),"score":daily["score"],"tier":daily["tier"],
        "surge_multiplier":daily["surge_multiplier"],
        "current_price":daily["price_usd"],"weather_score":daily["weather_appeal"],
        "selected_date":daily["date"],"selected_day_offset":day_offset,
        "selected_weather":daily["weather"],"weather_source":daily["weather_source"],
        "selected_demand":daily["demand"],"selected_weather_factor":daily["weather_factor"],
        "signal_explanation":(
            f"Local {route['forecast_method'].replace('_',' ')}; {route['observation_count']} simulated rank snapshots. "
            f"Day {day_offset}: modeled rank index {daily['demand']:.2f}; "
            f"weather factor {daily['weather_factor']:.3f}x ({daily['weather_source']}). "
            "No search/HF inference API used. Low confidence; illustrative USD prices, not airline quotes.")}

def run_pipeline():
    global LAST_REFRESH
    if not _refresh_lock.acquire(blocking=False): return False
    started=time.monotonic()
    REFRESH_STATUS.update(running=True,error=None)
    try:
        inputs=[]
        for origin in ORIGINS:
            snapshots=get_top_destinations(origin)["snapshots"]
            destinations=sorted(set().union(*(values.keys() for values in snapshots.values())))
            for dest in destinations:
                history={window:snapshots.get(window,{}).get(dest) for window in ["12w","8w","2w"]}
                inputs.append((origin,dest,history))
        predictions=forecast_batch([history for _,_,history in inputs])
        destinations=sorted({dest for _,dest,_ in inputs})
        # Fetch once per unique destination, never once per origin/route.
        with ThreadPoolExecutor(max_workers=2) as pool:
            weather=dict(zip(destinations,pool.map(get_weather_detail,destinations)))
        updated_at=datetime.now(timezone.utc).isoformat()
        pending={}
        for (origin,dest,history),prediction in zip(inputs,predictions):
            result=apply_weather(prediction,weather[dest])
            base=get_base_price(origin,dest)
            for day in result["daily_forecast"]:
                day["price_usd"]=round(base*day["surge_multiplier"],2)
            route={"origin":origin,"destination":dest,"dest_city_name":CITY_NAMES.get(dest,dest),
                "history":history,**result,"base_price":base,"currency":"USD",
                "history_source":"simulated_rank_snapshots","price_source":"illustrative",
                "forecast_model":MODEL_ID if not result["fallback"] else None,
                "weather_source":weather[dest]["source"],"updated_at":updated_at,
                "trend_score":None,"trend_source":"disabled","forecast_version":"local-weather-bolt-v1"}
            for window,value in history.items():
                route["travel_rank_"+window]=round(51-value*50) if value is not None else None
            today=result["daily_forecast"][0]
            route.update(score=today["score"],tier=today["tier"],surge_multiplier=today["surge_multiplier"],
                         current_price=today["price_usd"],weather_score=today["weather_appeal"])
            candidates=[d for d in result["daily_forecast"] if d["weather_available"] and
                        d["weather_source"]=="Open-Meteo (live)" and d["weather_appeal"]>=.5]
            if candidates:
                best=max(candidates,key=lambda d:(d["weather_appeal"]/d["surge_multiplier"],-d["day_offset"]))
                route["optimal_day"]={k:best[k] for k in ["day_offset","date","price_usd","weather_appeal"]}
            else: route["optimal_day"]=None
            pending[f"{origin}-{dest}"]=route
        if not pending: raise ValueError("Empty forecast universe")
        # Retain dictionary identity for existing consumers imported by value.
        with _cache_lock:
            FORECAST_CACHE.clear()
            FORECAST_CACHE.update(pending)
            LAST_REFRESH=datetime.now(timezone.utc)
        logger.info("Refreshed %s routes without search or hosted inference APIs",len(pending))
        return True
    except Exception as exc:
        REFRESH_STATUS["error"]=type(exc).__name__
        logger.exception("Refresh failed; previous complete forecasts retained")
        return False
    finally:
        REFRESH_STATUS.update(running=False,duration_seconds=round(time.monotonic()-started,2))
        _refresh_lock.release()

def start_scheduler():
    global _scheduler
    _scheduler=BackgroundScheduler()
    _scheduler.add_job(run_pipeline,"interval",minutes=30,max_instances=1,coalesce=True)
    _scheduler.start()
    _scheduler.add_job(run_pipeline)

def stop_scheduler():
    if _scheduler: _scheduler.shutdown(wait=False)

def get_cached_forecasts(origin=None):
    values=list(cache_snapshot().values())
    return rank_routes([r for r in values if origin is None or r["origin"]==origin.upper()])

def get_single_forecast(origin,dest):
    with _cache_lock: return deepcopy(FORECAST_CACHE.get(f"{origin.upper()}-{dest.upper()}"))
