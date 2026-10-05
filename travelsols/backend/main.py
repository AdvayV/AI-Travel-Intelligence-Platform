from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name('.env'))
import network_config  # noqa: F401
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
import scheduler
import chronos_engine
import trends_client
import travel_advisor
from weather_client import get_weather_detail
from export.tableau_exporter import route_rows, encode_csv

@asynccontextmanager
async def lifespan(app):
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()

app = FastAPI(title='TravelSols v1 · Route Intelligence', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[
    'http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:3000'],
    allow_methods=['*'], allow_headers=['*'])

@app.get('/api/health')
def health_check():
    routes = list(scheduler.FORECAST_CACHE.values())
    live_weather = sum('live' in r['weather_source'] for r in routes)
    live_trends = sum(r['trend_source'] == 'live' for r in routes)
    return {
        'status': 'ok' if routes else 'warming_up', 'cache_size': len(routes),
        'last_refresh': scheduler.LAST_REFRESH.isoformat() if scheduler.LAST_REFRESH else None,
        'refresh': dict(scheduler.REFRESH_STATUS), 'surge_engine': 'v3',
        'integrations': {
            'weather': {'status': 'live' if live_weather == len(routes) and routes else 'partial' if live_weather else 'unavailable',
                        'provider': 'Open-Meteo', 'live_routes': live_weather, 'total_routes': len(routes)},
            'trends': {**trends_client.STATUS, 'status': 'live' if routes and live_trends == len(routes) else 'partial' if live_trends else 'fallback' if routes else 'not_checked',
                       'live_routes': live_trends, 'total_routes': len(routes)},
            'chronos': dict(chronos_engine.STATUS),
            'advisor': dict(travel_advisor.STATUS),
            'gds': {'status': 'simulated', 'note': 'Hardcoded sample snapshots; no live GDS integration.'},
            'pricing': {'status': 'illustrative', 'currency': 'USD', 'note': 'Simulated base fares; not bookable airline quotes.'},
            'neo4j': {'status': 'not_used', 'note': 'TravelSols v1 does not use Neo4j; that integration belongs to v2.'},
        }}

@app.get('/api/origins')
def get_origins():
    return [{'code': code, 'name': scheduler.CITY_NAMES[code]} for code in scheduler.ORIGINS]

def route_or_404(origin, dest):
    route = scheduler.get_single_forecast(origin, dest)
    if not route: raise HTTPException(404, 'Route not found. The first refresh may still be running.')
    return route

@app.get('/api/forecasts')
def list_forecasts(origin: str = 'BOM', limit: int = Query(25, ge=1, le=100)):
    if origin.upper() not in scheduler.ORIGINS: raise HTTPException(422, 'Unsupported origin')
    return scheduler.get_cached_forecasts(origin)[:limit]

@app.get('/api/forecast/{origin}/{dest}')
def single_forecast(origin: str, dest: str, day_offset: int = Query(0, ge=0, le=13)):
    return scheduler.recompute_forecast_for_day(route_or_404(origin, dest), day_offset)

@app.get('/api/weather/{dest}')
def live_weather(dest: str):
    return get_weather_detail(dest.upper())

@app.post('/api/refresh', status_code=202)
def refresh_data(background_tasks: BackgroundTasks):
    if scheduler.REFRESH_STATUS['running']: return {'status': 'already_refreshing'}
    background_tasks.add_task(scheduler.run_pipeline)
    return {'status': 'refreshing'}

class AdvisorQuery(BaseModel):
    question: Optional[str] = Field(None, max_length=2000)
    day_offset: int = Field(0, ge=0, le=13)

@app.post('/api/advisor/{origin}/{dest}')
def ask_advisor(origin: str, dest: str, query: Optional[AdvisorQuery] = None):
    route = scheduler.recompute_forecast_for_day(route_or_404(origin, dest), query.day_offset if query else 0)
    return travel_advisor.get_travel_advisor_result(route, query.question if query else None)

def csv_download(rows, filename):
    return Response(encode_csv(rows), media_type='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})

@app.get('/api/export/forecast/{origin}/{dest}')
def export_route_forecast(origin: str, dest: str):
    route = scheduler.recompute_forecast_for_day(route_or_404(origin, dest), 0)
    return csv_download(route_rows(route), f"{route['origin']}-{route['destination']}_forecast.csv")

@app.get('/api/export/all-routes')
def export_all_routes():
    rows = [row for route in scheduler.get_cached_forecasts() for row in route_rows(route)]
    return csv_download(rows, 'all_routes_forecast.csv')
