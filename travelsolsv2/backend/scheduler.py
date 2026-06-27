import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from travel_client import get_top_destinations
from chronos_engine import forecast_route_demand
from weather_client import get_weather_score
from trends_client import get_trend_scores
from scoring import compute_opportunity_score, rank_routes

logger = logging.getLogger(__name__)

FORECAST_CACHE = {}
LAST_REFRESH = None
_scheduler = None

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

def get_base_price(origin, dest):
    seed = sum(ord(c) for c in origin + dest)
    return 300 + (seed % 900)

def run_pipeline():
    global LAST_REFRESH
    logger.info("Starting forecast pipeline refresh...")
    origins = ['BOM', 'DEL', 'BLR', 'MAA', 'HYD']
    processed_count = 0
    
    for origin in origins:
        try:
            travel_data = get_top_destinations(origin)
            snapshots = travel_data.get("snapshots", {})
            
            all_dests = set()
            for snap in snapshots.values():
                all_dests.update(snap.keys())
                
            for dest in all_dests:
                history = {
                    "12w": snapshots.get("12w", {}).get(dest, 0.0),
                    "8w": snapshots.get("8w", {}).get(dest, 0.0),
                    "2w": snapshots.get("2w", {}).get(dest, 0.0)
                }
                
                chronos_result = forecast_route_demand(history)
                weather_scores = get_weather_score([dest])
                trend_scores = get_trend_scores([dest])
                
                w_score = weather_scores.get(dest, 0.5)
                t_score = trend_scores.get(dest, 0.0)
                
                score_data = compute_opportunity_score(
                    travel_momentum=history["2w"],
                    trend_score=t_score,
                    weather_score=w_score,
                    chronos_momentum_pct=chronos_result["momentum_pct"]
                )
                
                dest_name = CITY_NAMES.get(dest, dest)
                
                base_price = get_base_price(origin, dest)
                surge_multiplier = 1.0
                if score_data["score"] >= 40:
                    surge_multiplier = 1.0 + ((score_data["score"] - 40) / 75.0)
                current_price = base_price * surge_multiplier
                
                FORECAST_CACHE[f"{origin}-{dest}"] = {
                    "origin": origin,
                    "destination": dest,
                    "dest_city_name": dest_name,
                    "score": score_data["score"],
                    "tier": score_data["tier"],
                    "trend": chronos_result["trend"],
                    "momentum_pct": round(chronos_result["momentum_pct"], 1),
                    "mean_demand": round(chronos_result["mean_demand"], 3),
                    "peak_demand": round(chronos_result["peak_demand"], 3),
                    "weekly_forecast": [round(x, 3) for x in chronos_result["weekly_forecast"]],
                    "weather_score": round(w_score, 2),
                    "trend_score": round(t_score, 2),
                    "travel_rank_2w": int(51 - history["2w"]*50) if history["2w"] > 0 else 50,
                    "travel_rank_8w": int(51 - history["8w"]*50) if history["8w"] > 0 else 50,
                    "travel_rank_12w": int(51 - history["12w"]*50) if history["12w"] > 0 else 50,
                    "base_price": round(base_price, 2),
                    "surge_multiplier": round(surge_multiplier, 2),
                    "current_price": round(current_price, 2)
                }
                processed_count += 1
        except Exception as e:
            logger.error(f"Error processing forecasting pipeline for origin {origin}: {e}")
            
    LAST_REFRESH = datetime.now()
    logger.info(f"Pipeline refresh complete. Processed {processed_count} routes.")

def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(run_pipeline, 'interval', minutes=30)
    _scheduler.start()
    # Run immediately on startup
    _scheduler.add_job(run_pipeline)

def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown()

def get_cached_forecasts(origin=None):
    results = list(FORECAST_CACHE.values())
    if origin:
        results = [r for r in results if r["origin"] == origin]
    return rank_routes(results)

def get_single_forecast(origin, dest):
    return FORECAST_CACHE.get(f"{origin}-{dest}")
