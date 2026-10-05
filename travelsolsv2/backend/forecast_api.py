"""Forecast-only API: independent of graph, vector DB and hosted inference."""
import csv
import io
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response
import scheduler
import chronos_engine
from weather_client import get_weather_detail, STATUS as WEATHER_STATUS

router = APIRouter(prefix="/api", tags=["Local forecasting"])


@router.get("/forecast/status")
def forecast_status():
    routes = list(scheduler.cache_snapshot().values())
    sources = [r["weather_source"] for r in routes]
    return {
        "status": "ready" if routes else "warming_up",
        "cache_size": len(routes), "refresh": scheduler.refresh_status(),
        "last_refresh": scheduler.LAST_REFRESH.isoformat() if scheduler.LAST_REFRESH else None,
        "chronos": dict(chronos_engine.STATUS),
        "weather": {**WEATHER_STATUS, "live_routes": sources.count("Open-Meteo (live)"),
                    "stale_routes": sources.count("Open-Meteo (stale)"), "total_routes": len(routes)},
        "search_interest": "disabled", "hosted_inference": "not_used",
        "history_source": "simulated_rank_snapshots", "price_source": "illustrative",
        "confidence": "low", "network_feed": "Open-Meteo weather only",
    }


@router.get("/forecasts")
def list_forecasts(origin: str = "BOM", limit: int = Query(25, ge=1, le=100)):
    if origin.upper() not in scheduler.ORIGINS:
        raise HTTPException(422, "Unsupported departure airport")
    return scheduler.get_cached_forecasts(origin)[:limit]


def route_or_404(origin, dest):
    route = scheduler.get_single_forecast(origin, dest)
    if not route:
        raise HTTPException(404, "Route not found. The initial refresh may still be running.")
    return route


@router.get("/forecast/{origin}/{dest}")
def single_forecast(origin: str, dest: str, day_offset: int = Query(0, ge=0, le=27)):
    return scheduler.recompute_forecast_for_day(route_or_404(origin, dest), day_offset)


@router.get("/weather/{dest}")
def weather_detail(dest: str):
    return get_weather_detail(dest)


@router.post("/refresh", status_code=202)
def refresh_data(background_tasks: BackgroundTasks):
    if scheduler.refresh_status()["running"]:
        return {"status": "already_refreshing"}
    background_tasks.add_task(scheduler.run_pipeline)
    return {"status": "refreshing"}


@router.get("/forecast/{origin}/{dest}/export")
def export_forecast(origin: str, dest: str):
    route = route_or_404(origin, dest)
    output = io.StringIO(newline="")
    rows = [{"origin": route["origin"], "destination": route["destination"],
             "currency": "USD", "history_source": route["history_source"],
             "price_source": route["price_source"], "method": route["forecast_method"],
             "confidence": route["confidence_label"], "model_weight": route["model_weight"],
             "updated_at": route["updated_at"],
             **{key: day[key] for key in ["date", "day_offset", "raw_demand", "demand", "lower", "upper",
                 "weather_factor", "weather_appeal", "weather_source", "score", "surge_multiplier", "price_usd"]}}
            for day in route["daily_forecast"]]
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return Response(output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{route["origin"]}-{route["destination"]}_forecast.csv"'})
