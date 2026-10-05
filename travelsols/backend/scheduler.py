"""Atomic, single-flight refresh with shared weather and batched CPU forecasts."""
import logging
import threading
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from gds_client import get_top_destinations
from weather_client import get_weather_detail
from trends_client import get_trend_scores, get_trend_metadata
from chronos_engine import forecast_batch
from scoring import compute_surge_pricing_v2, rank_routes, get_base_price

logger = logging.getLogger(__name__)
FORECAST_CACHE = {}
LAST_REFRESH = None
REFRESH_STATUS = {'running': False, 'error': None}
_refresh_lock = threading.Lock()
_scheduler = None
ORIGINS = ['BOM', 'DEL', 'BLR', 'MAA', 'HYD']

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

def daily_schedule(route, weather=None):
    weather = weather or get_weather_detail(route['destination'])
    days = weather.get('days', [])
    alternates = {dest: get_weather_detail(dest) for dest in ALTERNATE_ROUTES.get(route['destination'], [])}
    schedules = []
    for offset in range(14):
        day = days[offset] if offset < len(days) else {}
        available = bool(day)
        alt_scores = {dest: info['days'][offset]['appeal'] for dest, info in alternates.items() if offset < len(info['days'])}
        weekly = route['weekly_forecast']
        demand = weekly[min(offset // 7, len(weekly)-1)]
        pricing = compute_surge_pricing_v2(
            route['origin'], route['destination'], route['raw_trend_score'],
            day.get('appeal', .5), weathercode=day.get('wmo_code'),
            forecast_day=offset, alternate_weather_scores=alt_scores, demand_score=demand,
            trend_source=route['trend_source'], weather_available=available,
        )
        schedules.append({**pricing, 'day_offset': offset,
            'date': day.get('date', (datetime.now().date()+timedelta(days=offset)).isoformat()),
            'weather_condition': day.get('condition', 'Unavailable'), 'weather_appeal': day.get('appeal'),
            'temp_max_c': day.get('temp_max_c'), 'temp_min_c': day.get('temp_min_c'),
            'surge_multiplier': pricing['multiplier'],
            'price_usd': round(route['base_price'] * pricing['multiplier'], 2),
            'weather_available': available, 'selected_weather': day or None})
    return schedules

def _optimal(schedules):
    # Compare comfort and cost without recommending severe/unavailable weather.
    candidates = [s for s in schedules if s['weather_available'] and s['weather_appeal'] >= .5]
    if not candidates: return {}
    best = max(candidates, key=lambda s: (s['weather_appeal']/s['surge_multiplier'], -s['day_offset']))
    return {'optimal_day_offset': best['day_offset'], 'optimal_date': best['date'],
            'optimal_price': best['price_usd'], 'optimal_weather_appeal': best['weather_appeal'],
            'optimal_weather_condition': best['weather_condition'],
            'optimal_surge_multiplier': best['surge_multiplier']}

def recompute_forecast_for_day(route, day_offset):
    if not 0 <= day_offset <= 13: raise ValueError('Day offset must be between 0 and 13')
    schedules = daily_schedule(route)
    selected = schedules[day_offset]
    return {**route, **selected, **_optimal(schedules), 'daily_schedules': schedules,
            'selected_day_offset': day_offset, 'selected_date': selected['date'],
            'current_price': selected['price_usd'], 'weather_score': selected['weather_appeal'],
            'signal_explanation': selected['surge_reasoning']}

def find_optimal_day(route, weather_detail):
    return _optimal(daily_schedule(route, weather_detail))

def run_pipeline():
    global FORECAST_CACHE, LAST_REFRESH
    if not _refresh_lock.acquire(blocking=False): return False
    REFRESH_STATUS.update(running=True, error=None)
    try:
        inputs = []
        for origin in ORIGINS:
            snapshots = get_top_destinations(origin)['snapshots']
            dests = sorted(set().union(*(s.keys() for s in snapshots.values())))
            for dest in dests:
                history = {window: snapshots.get(window, {}).get(dest) for window in ['12w', '8w', '2w']}
                inputs.append((origin, dest, history))
        destinations = sorted({dest for _, dest, _ in inputs} | {alt for alts in ALTERNATE_ROUTES.values() for alt in alts})
        with ThreadPoolExecutor(max_workers=6) as executor:
            weather = dict(zip(destinations, executor.map(get_weather_detail, destinations)))
        trends = get_trend_scores(destinations)
        predictions = forecast_batch([history for _, _, history in inputs])
        updated_at = datetime.now(timezone.utc).isoformat()
        new_cache = {}
        for (origin, dest, history), prediction in zip(inputs, predictions):
            observed = [v for v in history.values() if v is not None]
            route = {'origin': origin, 'destination': dest, 'dest_city_name': CITY_NAMES.get(dest, dest),
                     'history': history, **prediction, 'base_price': get_base_price(origin, dest),
                     'raw_gds_momentum': observed[-1] if observed else None,
                     'raw_trend_score': trends.get(dest, .5), 'trend_score': trends.get(dest, .5),
                     'trend_source': get_trend_metadata(dest)['source'], 'gds_source': 'simulated',
                     'weather_source': weather[dest]['source'], 'price_source': 'illustrative',
                     'currency': 'USD', 'updated_at': updated_at, 'surge_version': 'v3'}
            for window, value in history.items():
                route['gds_rank_'+window] = round(51-value*50) if value is not None else None
            selected = daily_schedule(route, weather[dest])[0]
            route.update(selected, current_price=selected['price_usd'], weather_score=selected['weather_appeal'],
                         raw_weather_score=selected['weather_appeal'], surge_capped=selected['capped'],
                         signal_explanation=selected['surge_reasoning'])
            new_cache[f'{origin}-{dest}'] = route
        # Atomic replacement: readers never see a partially refreshed universe.
        FORECAST_CACHE = new_cache
        LAST_REFRESH = datetime.now(timezone.utc)
        logger.info('Refresh complete: %s routes', len(new_cache))
        return True
    except Exception as exc:
        REFRESH_STATUS['error'] = type(exc).__name__
        logger.exception('Forecast refresh failed; previous cache retained')
        return False
    finally:
        REFRESH_STATUS['running'] = False
        _refresh_lock.release()

def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(run_pipeline, 'interval', minutes=30, max_instances=1, coalesce=True)
    _scheduler.start()
    _scheduler.add_job(run_pipeline)

def stop_scheduler():
    if _scheduler: _scheduler.shutdown(wait=False)

def get_cached_forecasts(origin=None):
    results = list(FORECAST_CACHE.values())
    return rank_routes([r for r in results if origin is None or r['origin'] == origin.upper()])

def get_single_forecast(origin, dest):
    return FORECAST_CACHE.get(f'{origin.upper()}-{dest.upper()}')
