import logging
import httpx
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from gds_client import get_top_destinations
from weather_client import get_weather_score
from trends_client import get_trend_scores
from scoring import compute_surge_pricing_v2, rank_routes

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
    "ICN": "Seoul", "TPE": "Taipei", "MNL": "Manila", "CGK": "Jakarta",
    "SGN": "Ho Chi Minh City"
}

# Alternate routes for competitive adjustment (primary dest → list of competing dests)
ALTERNATE_ROUTES = {
    "DXB": ["DOH", "AUH"],
    "LHR": ["CDG", "AMS", "FRA"],
    "SIN": ["BKK", "KUL"],
    "BKK": ["SIN", "KUL"],
    "JFK": ["ORD", "LAX", "YYZ"],
    "DOH": ["DXB"],
    "KUL": ["SIN", "BKK"],
    "NRT": ["ICN", "HKG"],
    "CDG": ["LHR", "FRA", "AMS"],
    "SYD": ["MEL", "BNE", "AKL"],
    "FRA": ["LHR", "CDG", "AMS"],
    "AMS": ["LHR", "CDG", "FRA"],
    "SFO": ["LAX", "ORD"],
    "HKG": ["NRT", "ICN"],
    "ICN": ["NRT", "HKG"],
}


def get_base_price(origin: str, dest: str) -> float:
    """Deterministic base price seeded from route pair."""
    seed = sum(ord(c) for c in origin + dest)
    return 300 + (seed % 900)


def run_pipeline():
    global LAST_REFRESH
    logger.info("Starting v2 forecast pipeline refresh...")
    origins = ['BOM', 'DEL', 'BLR', 'MAA', 'HYD']
    processed_count = 0

    for origin in origins:
        gds_data = get_top_destinations(origin)
        snapshots = gds_data.get("snapshots", {})

        # Collect all destinations for this origin
        all_dests = set()
        for snap in snapshots.values():
            all_dests.update(snap.keys())

        # Batch-fetch all weather scores so we can do alternate-route comparisons
        all_weather_scores = get_weather_score(list(all_dests))

        # Batch-fetch all trend scores
        all_trend_scores = get_trend_scores(list(all_dests))

        for dest in all_dests:
            history = {
                "12w": snapshots.get("12w", {}).get(dest, 0.0),
                "8w":  snapshots.get("8w",  {}).get(dest, 0.0),
                "2w":  snapshots.get("2w",  {}).get(dest, 0.0),
            }

            # Trend score
            t_score = all_trend_scores.get(dest, 0.0)
            w_score = all_weather_scores.get(dest, 0.5)

            # Alternate routes for this destination
            alt_dests = ALTERNATE_ROUTES.get(dest, [])

            # ── v2 full pricing pipeline ──────────────────────────────────
            pricing = compute_surge_pricing_v2(
                origin=origin,
                destination=dest,
                trend_score=t_score,
                weather_score=w_score,
                weathercode=0,
                forecast_day=0,   # 0 = today's view
                alternate_weather_scores=all_weather_scores,
            )
            # ─────────────────────────────────────────────────────────────

            dest_name  = CITY_NAMES.get(dest, dest)
            base_price = get_base_price(origin, dest)
            surge_mult = pricing["multiplier"]
            current_price = base_price * surge_mult

            # Human-readable signal explanation
            tier        = pricing["tier"]
            trend_word  = "present" if t_score > 0 else "absent"
            gds_diff  = (history["12w"] - history["2w"])
            gds_dir   = "up" if gds_diff < 0 else "down"
            gds_momentum = abs(int(gds_diff * 100))

            date_str = datetime.now().strftime('%Y-%m-%d')
            signal_explanation = (
                f"[v2] Demand {gds_dir} {gds_momentum}% over 12 weeks. "
                f"Google Trends signal {trend_word}. "
                f"Weather at {dest} on {date_str}: {pricing['weather_label']} "
                f"({round(w_score, 2):.2f}, x{pricing['weather_multiplier']:.2f}). "
                f"Temporal decay factor: {pricing['temporal_decay']:.1f}. "
                f"Alternate-route adj: {pricing['alt_route_delta']:+.4f}. "
                f"Final surge: {surge_mult:.2f}x"
                + (" [CAPPED]" if pricing.get("capped") else "") + "."
            )

            FORECAST_CACHE[f"{origin}-{dest}"] = {
                # Identity
                "origin":           origin,
                "destination":      dest,
                "dest_city_name":   dest_name,

                # Raw parameters for recomputation
                "raw_gds_momentum": history["2w"],
                "raw_trend_score": t_score,
                "raw_weather_score": w_score,

                # Opportunity score
                "score":            pricing["score"],
                "tier":             tier,
                "raw_base":         pricing["raw_base"],

                # Chronos default placeholders
                "trend":            "stable",
                "momentum_pct":     0.0,
                "mean_demand":      0.0,
                "peak_demand":      0.0,
                "weekly_forecast":  [0.7, 0.7],

                # Weather
                "weather_score":    round(w_score, 2),
                "weather_label":    pricing["weather_label"],
                "weather_multiplier": pricing["weather_multiplier"],

                # Trends
                "trend_score":      round(t_score, 2),

                # Surge pricing breakdown
                "base_surge":       pricing["base_surge"],
                "weather_boost":    pricing["weather_boost"],
                "alt_route_delta":  pricing["alt_route_delta"],
                "temporal_decay":   pricing["temporal_decay"],
                "surge_multiplier": round(surge_mult, 3),
                "surge_capped":     pricing.get("capped", False),
                "surge_version":    "v2",

                # GDS rank proxies
                "gds_rank_2w":    int(51 - history["2w"]  * 50) if history["2w"]  > 0 else 50,
                "gds_rank_8w":    int(51 - history["8w"]  * 50) if history["8w"]  > 0 else 50,
                "gds_rank_12w":   int(51 - history["12w"] * 50) if history["12w"] > 0 else 50,

                # Pricing
                "base_price":       round(base_price, 2),
                "current_price":    round(current_price, 2),

                # Explanation
                "signal_explanation": signal_explanation,
            }
            processed_count += 1

    LAST_REFRESH = datetime.now()
    logger.info(f"v2 pipeline complete. Processed {processed_count} routes.")


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


# ---------------------------------------------------------------------------
# Hugging Face Agent Travel Advisor
# ---------------------------------------------------------------------------

def find_optimal_day(base_forecast: dict, weather_detail: dict) -> dict:
    """
    Find the day offset (0 to 13) with the best ratio of weather appeal to surge price.
    """
    days = weather_detail.get("days", [])
    if not days:
        return {}
        
    origin = base_forecast["origin"]
    dest = base_forecast["destination"]
    trend_score = base_forecast.get("raw_trend_score", 0.0)
    base_price = base_forecast.get("base_price", 300.0)
    
    best_offset = 0
    best_ratio = -1.0
    best_details = {}
    
    for offset in range(len(days)):
        day_weather = days[offset]
        w_score = day_weather.get("appeal", 0.5)
        day_weathercode = int(day_weather.get("weather_code", 0))
        
        # Get alternate routes weather scores for the same day offset
        alt_dests = ALTERNATE_ROUTES.get(dest, [])
        alt_weather_scores = {}
        for alt in alt_dests:
            from weather_client import get_weather_detail
            alt_detail = get_weather_detail(alt)
            if "days" in alt_detail and offset < len(alt_detail["days"]):
                alt_weather_scores[alt] = alt_detail["days"][offset].get("appeal", 0.5)
            else:
                alt_weather_scores[alt] = 0.5
                
        pricing = compute_surge_pricing_v2(
            origin=origin,
            destination=dest,
            trend_score=trend_score,
            weather_score=w_score,
            weathercode=day_weathercode,
            forecast_day=offset,
            alternate_weather_scores=alt_weather_scores,
        )
        
        surge_mult = pricing["multiplier"]
        # Calculate ratio: weather appeal / surge multiplier
        ratio = w_score / max(0.1, surge_mult)
        
        if ratio > best_ratio:
            best_ratio = ratio
            best_offset = offset
            best_details = {
                "optimal_day_offset": offset,
                "optimal_date": day_weather.get("date"),
                "optimal_weather_appeal": w_score,
                "optimal_price": round(base_price * surge_mult, 2),
                "optimal_surge_multiplier": surge_mult,
                "optimal_weather_emoji": day_weather.get("emoji", "🌤"),
                "optimal_weather_condition": day_weather.get("condition", "Clear")
            }
            
    return best_details


def recompute_forecast_for_day(base_forecast: dict, day_offset: int) -> dict:
    """
    Recompute opportunity score and pricing for a specific day offset (0 to 13).
    """
    origin = base_forecast["origin"]
    dest = base_forecast["destination"]
    
    # 1. Retrieve raw signals
    gds_momentum = base_forecast.get("raw_gds_momentum", 0.5)
    trend_score = base_forecast.get("raw_trend_score", 0.0)
    
    # 2. Get weather for primary destination on that specific day
    from weather_client import get_weather_detail
    weather_detail = get_weather_detail(dest)
    w_score = base_forecast.get("raw_weather_score", 0.5)
    day_weather = None
    day_weathercode = 0
    if "days" in weather_detail and day_offset < len(weather_detail["days"]):
        day_weather = weather_detail["days"][day_offset]
        w_score = day_weather.get("appeal", w_score)
        day_weathercode = int(day_weather.get("weather_code", 0))
        
    # 3. Get alternate routes weather scores for the same day offset
    alt_dests = ALTERNATE_ROUTES.get(dest, [])
    alt_weather_scores = {}
    for alt in alt_dests:
        alt_detail = get_weather_detail(alt)
        if "days" in alt_detail and day_offset < len(alt_detail["days"]):
            alt_weather_scores[alt] = alt_detail["days"][day_offset].get("appeal", 0.5)
        else:
            alt_weather_scores[alt] = 0.5
            
    # 4. Recompute surge pricing
    pricing = compute_surge_pricing_v2(
        origin=origin,
        destination=dest,
        trend_score=trend_score,
        weather_score=w_score,
        weathercode=day_weathercode,
        forecast_day=day_offset,
        alternate_weather_scores=alt_weather_scores,
    )
    
    # 5. Build signal explanation
    tier = pricing["tier"]
    trend_word = "present" if trend_score > 0 else "absent"
    
    # GDS ranks
    gds_rank_2w = base_forecast.get("gds_rank_2w", 50)
    gds_rank_12w = base_forecast.get("gds_rank_12w", 50)
    gds_diff = (51 - gds_rank_12w) / 50 - (51 - gds_rank_2w) / 50
    gds_dir = "up" if gds_diff < 0 else "down"
    gds_momentum = abs(int(gds_diff * 100))
    
    date_str = day_weather['date'] if (day_weather and 'date' in day_weather) else datetime.now().strftime('%Y-%m-%d')
    signal_explanation = (
        f"[v2] Demand {gds_dir} {gds_momentum}% over 12 weeks. "
        f"Google Trends signal {trend_word}. "
        f"Weather at {dest} on {date_str}: {pricing['weather_label']} "
        f"({round(w_score, 2):.2f}, x{pricing['weather_multiplier']:.2f}). "
        f"Temporal decay factor: {pricing['temporal_decay']:.1f}. "
        f"Alternate-route adj: {pricing['alt_route_delta']:+.4f}. "
        f"Final surge: {pricing['multiplier']:.2f}x"
        + (" [CAPPED]" if pricing.get("capped") else "") + "."
    )
    
    # 6. Return updated dictionary (copying base and overwriting dynamic values)
    updated = dict(base_forecast)
    updated.update({
        "score": pricing["score"],
        "tier": tier,
        "raw_base": pricing["raw_base"],
        "weather_score": round(w_score, 2),
        "weather_label": pricing["weather_label"],
        "weather_multiplier": pricing["weather_multiplier"],
        "base_surge": pricing["base_surge"],
        "weather_boost": pricing["weather_boost"],
        "alt_route_delta": pricing["alt_route_delta"],
        "temporal_decay": pricing["temporal_decay"],
        "surge_multiplier": round(pricing["multiplier"], 3),
        "surge_capped": pricing.get("capped", False),
        "current_price": round(base_forecast["base_price"] * pricing["multiplier"], 2),
        "signal_explanation": signal_explanation,
        "selected_day_offset": day_offset,
    })
    
    # Calculate optimal day
    optimal_info = find_optimal_day(base_forecast, weather_detail)
    updated.update(optimal_info)

    if day_weather:
        updated["selected_date"] = day_weather.get("date")
        updated["selected_weather"] = day_weather
        
    return updated
