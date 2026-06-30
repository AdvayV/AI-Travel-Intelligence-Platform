"""
TravelRoute Intelligence v2 — Surge Pricing Engine
===================================================
Replaces the legacy linear additive scoring with a multiplicative,
weather-driven, temporally-decayed model.

Tiers (by final opportunity score 0–100):
  PLATINUM : score >= 80
  HOT      : score >= 65
  RISING   : score >= 45
  WATCH    : score >= 25
  COLD     : score <  25

Hard cap: surge multiplier never exceeds 2.50x (250 % of base price).
"""

import math
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Weather WMO code → travel-appeal multiplier
#    Source: Open-Meteo WMO Weather Interpretation Codes
# ---------------------------------------------------------------------------

# Maps WMO weather_code ranges to a (label, multiplier) tuple.
# Multiplier > 1 means good weather boosts demand;
# multiplier < 1 means bad weather suppresses it.
WEATHER_CODE_MULTIPLIERS: list[tuple[range, str, float]] = [
    (range(0, 3),   "Clear/Sunny",          1.25),  # 0=Clear, 1=Mainly clear, 2=Partly cloudy
    (range(3, 4),   "Overcast",             1.05),  # 3=Overcast
    (range(45, 50), "Fog",                  0.85),  # 45, 48
    (range(51, 68), "Drizzle/Rain",         0.70),  # 51-67 drizzle & rain
    (range(68, 78), "Freezing/Snow",        0.50),  # 68-77 freezing rain & snow
    (range(80, 83), "Rain Showers",         0.75),  # 80-82
    (range(85, 87), "Snow Showers",         0.45),  # 85-86
    (range(95, 100),"Thunderstorm",         0.35),  # 95-99
]

def weather_multiplier_from_wmo(wmo_code: int) -> float:
    """Return a weather appeal multiplier [0.35, 1.25] for a WMO weather code."""
    for code_range, _label, mult in WEATHER_CODE_MULTIPLIERS:
        if wmo_code in code_range:
            return mult
    # Unknown codes default to neutral
    return 1.0


def weather_multiplier_from_score(weather_score: float) -> float:
    """
    Convert a normalised 0-1 weather appeal score (from weather_client.py) into
    a multiplicative demand factor.

    Mapping:
      0.00 – 0.30  → 0.70 (severe / suppressed demand)
      0.30 – 0.55  → 0.85 (below average)
      0.55 – 0.75  → 1.00 (neutral)
      0.75 – 0.90  → 1.15 (good)
      0.90 – 1.00  → 1.30 (excellent / peak travel weather)
    """
    if weather_score >= 0.90:
        return 1.30
    elif weather_score >= 0.75:
        return 1.15
    elif weather_score >= 0.55:
        return 1.00
    elif weather_score >= 0.30:
        return 0.85
    else:
        return 0.70


# ---------------------------------------------------------------------------
# 2. Temporal decay — confidence decreases for farther forecast windows
# ---------------------------------------------------------------------------

def compute_temporal_decay(forecast_day: int) -> float:
    if forecast_day <= 7:
        return 1.00
    else:
        return 0.85


# ---------------------------------------------------------------------------
# 3. Alternate-route competitive adjustment
# ---------------------------------------------------------------------------

def get_alternate_route_adjustment(
    origin: str,
    primary_dest: str,
    alternate_dests: list[str],
    weather_scores: dict[str, float]
) -> float:
    """
    Compare the primary destination's weather score against alternates
    to produce a competitive multiplier.

    If primary dest has notably better weather than alternatives:
      → travellers are less price-sensitive → boost (+0.05 to +0.15)
    If primary dest has similar or worse weather than alternatives:
      → suppresses demand → cut (0.00 to -0.10)

    Returns an additive delta to apply to the surge multiplier.
    """
    if not alternate_dests or primary_dest not in weather_scores:
        return 0.0

    primary_score = weather_scores.get(primary_dest, 0.5)
    alt_scores = [weather_scores.get(d, 0.5) for d in alternate_dests if d != primary_dest]

    if not alt_scores:
        return 0.0

    avg_alt_score = sum(alt_scores) / len(alt_scores)
    delta = primary_score - avg_alt_score   # positive = primary is better

    if delta >= 0.25:
        return 0.15   # primary much better → strong demand pull
    elif delta >= 0.10:
        return 0.08
    elif delta >= 0.00:
        return 0.03
    elif delta >= -0.15:
        return -0.05  # primary slightly worse → mild suppression
    else:
        return -0.10  # primary much worse → travellers prefer alternates


def get_base_price(origin: str, dest: str) -> float:
    """Deterministic base price seeded from route pair."""
    seed = sum(ord(c) for c in origin + dest)
    return 300 + (seed % 900)


# ---------------------------------------------------------------------------
# 4. Core v2 opportunity score & demand score (Chronos removed)
# ---------------------------------------------------------------------------

def compute_demand_score(trend_score: float) -> float:
    '''
    Demand score from Google Trends only (Chronos forecast removed).
    '''
    return round(min(max(trend_score, 0.0), 1.0), 4)


def compute_opportunity_score_v2(
    trend_score: float,
    weather_score: float,
    forecast_day: int = 0,
) -> dict:
    """
    Compute a v2 opportunity score [0–100] using the new weighting.
    """
    demand_score = compute_demand_score(trend_score)
    opportunity_score = round(
        (demand_score * 0.55 + (1 - weather_score) * 0.45) * 100, 1
    )

    if opportunity_score >= 80:
        tier = "PLATINUM"
    elif opportunity_score >= 65:
        tier = "HOT"
    elif opportunity_score >= 45:
        tier = "RISING"
    elif opportunity_score >= 25:
        tier = "WATCH"
    else:
        tier = "COLD"

    # Weather multiplier
    w_mult = weather_multiplier_from_score(weather_score)
    decay = compute_temporal_decay(forecast_day)

    return {
        "score":            opportunity_score,
        "tier":             tier,
        "weather_multiplier": round(w_mult, 3),
        "temporal_decay":   round(decay, 2),
        "raw_base":         round(demand_score * 100, 1),
    }


# ---------------------------------------------------------------------------
# 5. Surge multiplier computation
# ---------------------------------------------------------------------------

_SURGE_CAP = 2.50   # Hard ceiling: 250 % of base fare


def compute_surge_multiplier_v2(
    opportunity_score: float,
    weather_score: float,
    weather_multiplier: float,
    alternate_route_delta: float = 0.0,
) -> dict:
    """
    Compute the final surge multiplier from the v2 opportunity score.
    """
    if opportunity_score < 25:
        base_surge = 0.75 + (opportunity_score / 25.0) * 0.15
    elif opportunity_score < 45:
        base_surge = 0.90 + ((opportunity_score - 25) / 20.0) * 0.10
    elif opportunity_score < 65:
        base_surge = 1.00 + ((opportunity_score - 45) / 20.0) * 0.40
    elif opportunity_score < 80:
        base_surge = 1.40 + ((opportunity_score - 65) / 15.0) * 0.45
    else:
        base_surge = 1.85 + ((opportunity_score - 80) / 20.0) * 0.65

    weather_boost = max(0.0, weather_multiplier - 1.0) * 0.30
    surged = base_surge + weather_boost
    surged += alternate_route_delta

    capped = surged > _SURGE_CAP
    final_multiplier = min(surged, _SURGE_CAP)
    final_multiplier = max(final_multiplier, 0.75)

    return {
        "multiplier":         round(final_multiplier, 4),
        "capped":             capped,
        "weather_boost":      round(weather_boost, 4),
        "base_surge":         round(base_surge, 4),
        "alt_route_delta":    round(alternate_route_delta, 4),
        "raw_surge":          round(surged, 4),
    }


# ---------------------------------------------------------------------------
# 6. Full pipeline convenience function
# ---------------------------------------------------------------------------

def compute_surge_pricing_v2(
    origin: str,
    destination: str,
    trend_score: float,
    weather_score: float,
    weathercode: int = 0,
    forecast_day: int = 7,
    alternate_weather_scores: Optional[Dict[str, float]] = None,
) -> dict:
    """
    One-call full pipeline: score → multiplier → price signals.
    """
    alternate_weather_scores = alternate_weather_scores or {}

    # 1. Demand score
    demand_score = compute_demand_score(trend_score)

    # 2. Opportunity score
    opportunity_score = round(
        (demand_score * 0.55 + (1 - weather_score) * 0.45) * 100, 1
    )

    # 3. Tier classification
    if opportunity_score >= 80:
        tier = "PLATINUM"
    elif opportunity_score >= 65:
        tier = "HOT"
    elif opportunity_score >= 45:
        tier = "RISING"
    elif opportunity_score >= 25:
        tier = "WATCH"
    else:
        tier = "COLD"

    # 4. Base surge from opportunity score
    if opportunity_score < 25:
        base_surge = 0.75 + (opportunity_score / 25.0) * 0.15
    elif opportunity_score < 45:
        base_surge = 0.90 + ((opportunity_score - 25) / 20.0) * 0.10
    elif opportunity_score < 65:
        base_surge = 1.00 + ((opportunity_score - 45) / 20.0) * 0.40
    elif opportunity_score < 80:
        base_surge = 1.40 + ((opportunity_score - 65) / 15.0) * 0.45
    else:
        base_surge = 1.85 + ((opportunity_score - 80) / 20.0) * 0.65

    # 5. Weather surge & condition label
    if weathercode != 0:
        weather_condition = "Unknown"
        weather_surge = 1.0
        for code_range, label, mult in WEATHER_CODE_MULTIPLIERS:
            if weathercode in code_range:
                weather_condition = label
                weather_surge = mult
                break
    else:
        weather_surge = weather_multiplier_from_score(weather_score)
        weather_condition = _weather_label(weather_score)

    # 6. Demand x Weather interaction
    interaction = round(1.0 + (demand_score * weather_score * 0.1), 2)

    # 7. Temporal decay
    temporal_decay = compute_temporal_decay(forecast_day)

    # 8. Alternate/competitive route adjustment
    alt_dests = [d for d in alternate_weather_scores.keys() if d != destination]
    if alt_dests:
        alt_delta = get_alternate_route_adjustment(
            origin=origin,
            primary_dest=destination,
            alternate_dests=alt_dests,
            weather_scores=alternate_weather_scores,
        )
    else:
        alt_delta = 0.0

    competitive_adj = round(1.0 + alt_delta, 2)
    if alt_delta == 0.0:
        competitive_reason = "neutral (1.00x)"
    elif alt_delta > 0.0:
        competitive_reason = f"favorable weather vs alternates (+{alt_delta:.2f}x)"
    else:
        competitive_reason = f"unfavorable weather vs alternates ({alt_delta:.2f}x)"

    # 9. Final surge multiplier calculation
    final_surge = base_surge * weather_surge * interaction * temporal_decay * competitive_adj
    final_surge_multiplier = round(min(max(final_surge, 0.75), 2.50), 2)
    capped = final_surge > 2.50

    # 10. Pricing in INR
    base_price_inr = int(get_base_price(origin, destination))
    surge_price_inr = int(base_price_inr * final_surge_multiplier)

    # 11. Reasoning parts
    reasoning_parts = [
        f'Demand score {demand_score:.2f} (Google Trends 100%)',
        f'Weather: {weather_condition} (score {weather_score:.2f}, {weather_surge:.2f}x surge) — highest priority factor',
        f'Demand x Weather interaction: {interaction:.2f}x',
        f'Temporal decay day-{forecast_day}: {temporal_decay:.2f}x',
        f'Competitive routing: {competitive_reason}',
        f'Final: {base_surge:.2f} x {weather_surge:.2f} x {interaction:.2f} x {temporal_decay:.2f} x {competitive_adj:.2f} = {final_surge:.2f}x',
    ]
    surge_reasoning = " | ".join(reasoning_parts)

    weather_label = _weather_label(weather_score)

    return {
        "score":                    opportunity_score,
        "opportunity_score":        opportunity_score,
        "tier":                     tier,
        "base_surge":               round(base_surge, 4),
        "weather_boost":            round(weather_surge, 4),
        "alt_route_delta":          round(alt_delta, 4),
        "temporal_decay":           round(temporal_decay, 2),
        "multiplier":               final_surge_multiplier,
        "final_surge_multiplier":   final_surge_multiplier,
        "capped":                   capped,
        "base_price_inr":           base_price_inr,
        "surge_price_inr":          surge_price_inr,
        "surge_reasoning":          surge_reasoning,
        "weather_label":            weather_label,
        "weather_multiplier":       round(weather_surge, 3),
        "raw_base":                 round(demand_score * 100, 1),
    }


def _weather_label(score: float) -> str:
    if score >= 0.90:
        return "Excellent ☀️"
    elif score >= 0.75:
        return "Good 🌤"
    elif score >= 0.55:
        return "Fair 🌥"
    elif score >= 0.30:
        return "Poor 🌧"
    else:
        return "Severe ⛈"


def compute_opportunity_score(trend_score: float, weather_score: float) -> dict:
    result = compute_surge_pricing_v2(
        origin='BOM', destination='DXB',
        trend_score=trend_score,
        weather_score=weather_score,
    )
    return {
        'score': result['opportunity_score'],
        'tier': result['tier'],
        'surge_multiplier': result['final_surge_multiplier'],
        'base_price': result['base_price_inr'],
        'surge_price': result['surge_price_inr'],
        'surge_reasoning': result['surge_reasoning'],
    }


# ---------------------------------------------------------------------------
# 7. Route ranking (unchanged, but now also sorts by multiplier on tie)
# ---------------------------------------------------------------------------

def rank_routes(routes_list: list[dict]) -> list[dict]:
    """Rank routes by score desc, then surge_multiplier desc on tie."""
    sorted_routes = sorted(
        routes_list,
        key=lambda x: (x.get("score", 0), x.get("surge_multiplier", 1)),
        reverse=True
    )
    for i, route in enumerate(sorted_routes):
        route["rank"] = i + 1
    return sorted_routes
