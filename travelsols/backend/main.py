from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from scheduler import start_scheduler, stop_scheduler, get_cached_forecasts, get_single_forecast, FORECAST_CACHE, LAST_REFRESH, run_pipeline
from weather_client import get_weather_detail
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(title="TravelRoute Intelligence v2", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "model": "meta-llama/Meta-Llama-3-8B-Instruct",
        "surge_engine": "v2",
        "cache_size": len(FORECAST_CACHE),
        "last_refresh": LAST_REFRESH.isoformat() if LAST_REFRESH else None
    }

@app.get("/api/origins")
def get_origins():
    return [
        {"code": "BOM", "name": "Mumbai"},
        {"code": "DEL", "name": "Delhi"},
        {"code": "BLR", "name": "Bengaluru"},
        {"code": "MAA", "name": "Chennai"},
        {"code": "HYD", "name": "Hyderabad"}
    ]

@app.get("/api/forecasts")
def list_forecasts(origin: str = "BOM", limit: int = 20):
    try:
        results = get_cached_forecasts(origin)
        return results[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/forecast/{origin}/{dest}")
def single_forecast(origin: str, dest: str, day_offset: int = 0):
    try:
        data = get_single_forecast(origin, dest)
        if not data:
            raise HTTPException(status_code=404, detail="Route not found")
        
        from scheduler import recompute_forecast_for_day
        data = recompute_forecast_for_day(data, day_offset)
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/weather/{dest}")
def live_weather(dest: str):
    """
    Live 7-day weather detail for a destination, fetched on-demand.
    Returns daily breakdown with °C temperatures, precipitation, WMO condition,
    wind speed (km/h), precipitation probability, and travel appeal score.
    Results are cached for 30 minutes.
    """
    try:
        detail = get_weather_detail(dest.upper())
        return detail
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/refresh")
def refresh_data(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(run_pipeline)
        return {"status": "refreshing", "eta_seconds": 30}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from travel_advisor import get_travel_advisor_response

from pydantic import BaseModel
from typing import Optional

class AdvisorQuery(BaseModel):
    question: Optional[str] = None

@app.post('/api/advisor/{origin}/{dest}')
async def ask_advisor(origin: str, dest: str, query: Optional[AdvisorQuery] = None):
    from scheduler import FORECAST_CACHE, ALTERNATE_ROUTES
    route_key = f"{origin.upper()}-{dest.upper()}"
    if route_key not in FORECAST_CACHE:
        raise HTTPException(status_code=404, detail='Route not found in cache')
        
    route = dict(FORECAST_CACHE[route_key])
    
    # Load 14-day weather details
    from weather_client import get_weather_detail
    weather_detail = get_weather_detail(dest.upper())
    days = weather_detail.get("days", [])
    
    # Compute surge details for each day
    daily_schedules = []
    base_price = route.get("base_price", 300.0)
    trend_score = route.get("raw_trend_score", 0.0)
    
    from scoring import compute_surge_pricing_v2
    for offset in range(len(days)):
        day_weather = days[offset]
        w_score = day_weather.get("appeal", 0.5)
        day_weathercode = int(day_weather.get("weather_code", 0))
        
        # Get alternate routes weather scores
        alt_dests = ALTERNATE_ROUTES.get(dest.upper(), [])
        alt_weather_scores = {}
        for alt in alt_dests:
            alt_detail = get_weather_detail(alt)
            if "days" in alt_detail and offset < len(alt_detail["days"]):
                alt_weather_scores[alt] = alt_detail["days"][offset].get("appeal", 0.5)
            else:
                alt_weather_scores[alt] = 0.5
                
        pricing = compute_surge_pricing_v2(
            origin=origin.upper(),
            destination=dest.upper(),
            trend_score=trend_score,
            weather_score=w_score,
            weathercode=day_weathercode,
            forecast_day=offset,
            alternate_weather_scores=alt_weather_scores,
        )
        
        daily_schedules.append({
            "day_offset": offset,
            "date": day_weather.get("date"),
            "weather_condition": day_weather.get("condition"),
            "temp_max_c": day_weather.get("temp_max_c"),
            "temp_min_c": day_weather.get("temp_min_c"),
            "weather_appeal": w_score,
            "surge_multiplier": pricing["multiplier"],
            "price_usd": round(base_price * pricing["multiplier"], 2)
        })
        
    route["daily_schedules"] = daily_schedules
    user_q = query.question if query else None
    answer = get_travel_advisor_response(route, user_q)
    return {'answer': answer, 'model': 'Qwen/Qwen3-4B-Instruct-2507'}


from export.tableau_exporter import export_chronos_forecast_to_csv, export_all_routes_to_csv
from fastapi.responses import FileResponse
import os
import tempfile

@app.get('/api/export/forecast/{origin}/{dest}')
async def export_route_forecast(origin: str, dest: str):
    '''Export single route forecast to CSV for Tableau'''
    route_key = f'{origin}-{dest}'
    
    if route_key not in FORECAST_CACHE:
        raise HTTPException(status_code=404, detail=f'Route {route_key} not found')
    
    route_data = FORECAST_CACHE[route_key]
    
    from weather_client import get_weather_detail
    weather_detail = get_weather_detail(dest)
    days = weather_detail.get('days', [])
    
    wk1_scores = [d.get('appeal', 0.5) for d in days[:7]]
    wk2_scores = [d.get('appeal', 0.5) for d in days[7:14]]
    
    wk1_avg = sum(wk1_scores) / len(wk1_scores) if wk1_scores else 0.5
    wk2_avg = sum(wk2_scores) / len(wk2_scores) if wk2_scores else 0.5

    filepath = export_chronos_forecast_to_csv(
        origin=origin,
        destination=dest,
        historical_data={
            '12w': route_data.get('gds_rank_12w', 0) / 50,
            '8w': route_data.get('gds_rank_8w', 0) / 50,
            '2w': route_data.get('gds_rank_2w', 0) / 50,
        },
        forecast_data=route_data.get('weekly_forecast', [0.7, 0.7]),
        weather_scores={
            'today': route_data.get('weather_score', 0.75),
            'wk1': round(wk1_avg, 3),
            'wk2': round(wk2_avg, 3)
        },
        trend_score=route_data.get('trend_score', 0),
        opportunity_score=route_data.get('score', 0),
        surge_multiplier=route_data.get('surge_multiplier', 1.0),
        base_price=route_data.get('base_price', 35000),
        filepath=os.path.join(tempfile.gettempdir(), f'{route_key}_forecast.csv')
    )
    
    return FileResponse(filepath, filename=f'{route_key}_forecast.csv')

@app.get('/api/export/all-routes')
async def export_all_routes():
    '''Export all cached forecasts to CSV for Tableau'''
    filepath = export_all_routes_to_csv(FORECAST_CACHE, filepath=os.path.join(tempfile.gettempdir(), 'all_routes_forecast.csv'))
    return FileResponse(filepath, filename='all_routes_forecast.csv')
