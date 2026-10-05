"""Explainable heuristic ranking/pricing; no search API, no market-fare claims."""
import math

def clamp(value,lo=0,hi=1):
    return min(hi,max(lo,float(value)))

def day_metrics(demand, weather_appeal):
    demand = clamp(demand)
    # Demand already has its bounded weather adjustment; do not multiply twice.
    comfort = .5 if weather_appeal is None else clamp(weather_appeal)
    score = round(100*(.8*demand+.2*comfort),1)
    tier = "HOT" if score>=65 else "RISING" if score>=40 else "WATCH"
    surge = round(clamp(.75+1.25*demand,.75,2.5),3)
    return {"score":score,"tier":tier,"surge_multiplier":surge}

def compute_opportunity_score(travel_momentum, trend_score=0, weather_score=None, chronos_momentum_pct=0):
    """Legacy signature retained; search and percentage-change bonuses removed."""
    return day_metrics(travel_momentum,weather_score)

def get_base_price(origin,dest):
    return float(300 + sum(ord(c) for c in origin+dest)%900)

def rank_routes(routes_list):
    ordered=sorted((dict(r) for r in routes_list),key=lambda r:(-r.get("score",0),r["destination"]))
    return [{**r,"rank":i+1} for i,r in enumerate(ordered)]
