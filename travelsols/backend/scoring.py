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
from typing import Optional

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
    """
    Returns a decay factor in [0.50, 1.00].

    Day 0–3  : 1.00 (full confidence — near-term)
    Day 4–7  : 0.90
    Day 8–14 : 0.80
    Day 15+  : 0.50 (low confidence — far future)
    """
    if forecast_day <= 3:
        return 1.00
    elif forecast_day <= 7:
        return 0.90
    elif forecast_day <= 14:
        return 0.80
    else:
        return 0.50


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


# ---------------------------------------------------------------------------
# 4. Core v2 opportunity score
# ---------------------------------------------------------------------------

# Weights must sum to 1.0
_W_GDS    = 0.40   # GDS booking momentum (most reliable real-world signal)
_W_CHRONOS  = 0.25   # AI time-series forecast momentum
_W_WEATHER  = 0.20   # Weather appeal (MULTIPLICATIVE after scoring)
_W_TRENDS   = 0.15   # Google Trends consumer intent


def compute_opportunity_score_v2(
    gds_momentum: float,
    trend_score: float,
    weather_score: float,
    chronos_momentum_pct: float,
    forecast_day: int = 0,
) -> dict:
    """
    Compute a v2 opportunity score [0–100] with multiplicative weather boost.

    Parameters
    ----------
    gds_momentum      : float  GDS demand signal in [0, 1]
    trend_score         : float  Google Trends signal in [0, 1]
    weather_score       : float  Open-Meteo appeal score in [0, 1]
    chronos_momentum_pct: float  Chronos forecast momentum in %  (-∞, +∞), normalised internally
    forecast_day        : int    Days ahead (0 = today, 7 = next week …)

    Returns
    -------
    dict with keys: score (float), tier (str), weather_multiplier (float),
                    temporal_decay (float), raw_base (float)
    """
    # --- Base additive score (ignores weather) ---
    chronos_norm = min(max(chronos_momentum_pct / 100.0, -1.0), 1.0)
    # Shift chronos to [0,1]: neutral at 0.5
    chronos_0_1 = (chronos_norm + 1.0) / 2.0

    base = (
        gds_momentum  * _W_GDS   +
        chronos_0_1     * _W_CHRONOS +
        trend_score     * _W_TRENDS
    )

    # --- Multiplicative weather boost ---
    w_mult = weather_multiplier_from_score(weather_score)
    # Weather contribution is multiplicative: good weather amplifies demand,
    # bad weather suppresses it, using a blended approach so that
    # weather doesn't zero-out an otherwise strong signal.
    weather_contribution = weather_score * _W_WEATHER
    boosted = (base + weather_contribution) * w_mult

    # --- Temporal decay ---
    decay = compute_temporal_decay(forecast_day)
    final = boosted * decay * 100.0   # scale to 0–100

    # Clamp
    final = max(0.0, min(100.0, final))

    # --- 5-tier classification ---
    if final >= 80:
        tier = "PLATINUM"
    elif final >= 65:
        tier = "HOT"
    elif final >= 45:
        tier = "RISING"
    elif final >= 25:
        tier = "WATCH"
    else:
        tier = "COLD"

    return {
        "score":            round(final, 1),
        "tier":             tier,
        "weather_multiplier": round(w_mult, 3),
        "temporal_decay":   round(decay, 2),
        "raw_base":         round(base * 100, 1),
    }


# Keep legacy alias for any code still calling the old function name
def compute_opportunity_score(
    gds_momentum: float,
    trend_score: float,
    weather_score: float,
    chronos_momentum_pct: float,
) -> dict:
    """Legacy wrapper — delegates to v2 with forecast_day=0."""
    result = compute_opportunity_score_v2(
        gds_momentum=gds_momentum,
        trend_score=trend_score,
        weather_score=weather_score,
        chronos_momentum_pct=chronos_momentum_pct,
        forecast_day=0,
    )
    # Back-compat: strip v2-only keys if caller only expects score + tier
    return {"score": result["score"], "tier": result["tier"]}


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

    Formula (additive stages, then capped):
      1. Base surge from opportunity score  — steeper curve above 45
      2. Weather amplification bonus        — multiplicative component
      3. Alternate-route competitive delta  — additive fine-tuning
      4. Hard cap at 2.50x

    Returns dict with: multiplier, capped, weather_boost, components
    """
    # 1. Demand-driven base surge
    # COLD (<25)     : 0.75x – 0.90x   genuine discount to stimulate demand
    # WATCH (25–45)  : 0.90x – 1.00x   near-flat, slight suppression
    # RISING (45–65) : 1.00x – 1.40x   growing demand premium
    # HOT (65–80)    : 1.40x – 1.85x   high-demand surge
    # PLATINUM (80+) : 1.85x – 2.50x   peak / capped at ceiling
    if opportunity_score < 25:
        # COLD: real discount — maps score 0→24 to 0.75→0.90
        base_surge = 0.75 + (opportunity_score / 25.0) * 0.15
    elif opportunity_score < 45:
        # WATCH: 0.90 → 1.00
        base_surge = 0.90 + ((opportunity_score - 25) / 20.0) * 0.10
    elif opportunity_score < 65:
        # RISING: 1.00 → 1.40
        base_surge = 1.00 + ((opportunity_score - 45) / 20.0) * 0.40
    elif opportunity_score < 80:
        # HOT: 1.40 → 1.85
        base_surge = 1.40 + ((opportunity_score - 65) / 15.0) * 0.45
    else:
        # PLATINUM: 1.85 → 2.50
        base_surge = 1.85 + ((opportunity_score - 80) / 20.0) * 0.65

    # 2. Weather multiplicative boost (only applies positive uplift)
    weather_boost = max(0.0, weather_multiplier - 1.0) * 0.30
    surged = base_surge + weather_boost

    # 3. Alternate-route competitive adjustment
    surged += alternate_route_delta

    # 4. Clamp: cap at 2.50x, floor at 0.75x
    capped = surged > _SURGE_CAP
    final_multiplier = min(surged, _SURGE_CAP)
    final_multiplier = max(final_multiplier, 0.75)  # never below 75% of base

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
    gds_momentum: float,
    trend_score: float,
    weather_score: float,
    chronos_momentum_pct: float,
    origin: str = "",
    dest: str = "",
    alternate_dests: Optional[list[str]] = None,
    all_weather_scores: Optional[dict[str, float]] = None,
    forecast_day: int = 0,
) -> dict:
    """
    One-call full pipeline: score → multiplier → price signals.

    Returns a merged dict suitable for the FORECAST_CACHE entry.
    """
    alternate_dests = alternate_dests or []
    all_weather_scores = all_weather_scores or {}

    # Opportunity score
    score_data = compute_opportunity_score_v2(
        gds_momentum=gds_momentum,
        trend_score=trend_score,
        weather_score=weather_score,
        chronos_momentum_pct=chronos_momentum_pct,
        forecast_day=forecast_day,
    )

    # Competitive route adjustment
    alt_delta = get_alternate_route_adjustment(
        origin=origin,
        primary_dest=dest,
        alternate_dests=alternate_dests,
        weather_scores=all_weather_scores,
    )

    # Surge multiplier
    surge_data = compute_surge_multiplier_v2(
        opportunity_score=score_data["score"],
        weather_score=weather_score,
        weather_multiplier=score_data["weather_multiplier"],
        alternate_route_delta=alt_delta,
    )

    # Weather label for frontend display
    weather_label = _weather_label(weather_score)

    return {
        **score_data,
        **surge_data,
        "weather_label":      weather_label,
        "surge_version":      "v2",
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
