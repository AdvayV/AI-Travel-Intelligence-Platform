"""Explainable illustrative USD pricing, not market-calibrated airline fares."""
import math

def clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))

def get_base_price(origin, dest):
    return float(300 + sum(ord(c) for c in origin + dest) % 900)

def weather_multiplier_from_wmo(code):
    if code in (0, 1, 2): return 1.15
    if code == 3: return 1.0
    if code in (95, 96, 99): return .7
    if code in (71, 73, 75, 77, 85, 86): return .8
    if code in (45, 48): return .9
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82): return .85
    return 1.0

def weather_multiplier_from_score(score):
    return .8 + .4 * clamp(score)

def compute_temporal_decay(forecast_day):
    """Shrink uncertain signals toward neutral, not blanket future discounts."""
    return math.exp(-max(0, forecast_day) / 28)

def get_alternate_route_adjustment(origin, primary_dest, alternate_dests, weather_scores):
    scores = [weather_scores[d] for d in alternate_dests if d in weather_scores and d != primary_dest]
    if not scores or primary_dest not in weather_scores: return 0.0
    return round(clamp((weather_scores[primary_dest] - sum(scores)/len(scores)) * .15, -.08, .08), 4)

def compute_demand_score(trend_score):
    return round(clamp(trend_score), 4)

def _tier(score):
    for threshold, tier in [(80, 'PLATINUM'), (65, 'HOT'), (45, 'RISING'), (25, 'WATCH')]:
        if score >= threshold: return tier
    return 'COLD'

def _weather_label(score):
    return 'Excellent' if score >= .85 else 'Good' if score >= .7 else 'Fair' if score >= .5 else 'Poor' if score >= .3 else 'Severe'

def compute_opportunity_score_v2(trend_score, weather_score, forecast_day=0):
    score = round((.7 * clamp(trend_score) + .3 * clamp(weather_score)) * 100, 1)
    return dict(score=score, tier=_tier(score), weather_multiplier=weather_multiplier_from_score(weather_score),
                temporal_decay=compute_temporal_decay(forecast_day), raw_base=clamp(trend_score)*100)

def compute_surge_multiplier_v2(opportunity_score, weather_score, weather_multiplier, alternate_route_delta=0):
    base = .75 + 1.25 * clamp(opportunity_score/100)
    raw = base * weather_multiplier * (1 + alternate_route_delta)
    return dict(multiplier=round(clamp(raw, .75, 2.5), 3), capped=raw > 2.5,
                weather_boost=weather_multiplier, base_surge=base, alt_route_delta=alternate_route_delta)

def compute_surge_pricing_v2(origin, destination, trend_score, weather_score, weathercode=None,
                             forecast_day=0, alternate_weather_scores=None, demand_score=None,
                             trend_source='live', weather_available=True):
    demand = clamp(trend_score if demand_score is None else demand_score)
    # Per-keyword normalized Trends is weak evidence, not absolute demand.
    search_weight = .2 if trend_source == 'live' else 0
    combined = (1-search_weight) * demand + search_weight * clamp(trend_score)
    weather = clamp(weather_score) if weather_available else .5
    opportunity = compute_opportunity_score_v2(combined, weather, forecast_day)
    decay = compute_temporal_decay(forecast_day)
    base = .75 + 1.25 * combined
    weather_factor = weather_multiplier_from_score(weather) if weather_available else 1.0
    # Zero is valid clear sky, not "missing".
    if weather_available and weathercode is not None:
        weather_factor = .7 * weather_factor + .3 * weather_multiplier_from_wmo(weathercode)
    scores = dict(alternate_weather_scores or {})
    scores[destination] = weather
    delta = get_alternate_route_adjustment(origin, destination, list(scores), scores) if weather_available else 0
    raw = (1 + (base - 1) * decay) * (1 + (weather_factor - 1) * decay) * (1 + delta * decay)
    multiplier = round(clamp(raw, .75, 2.5), 3)
    reasoning = (f"Rank forecast {demand:.2f}; search weight {search_weight:.0%}. "
                 f"Weather factor {weather_factor:.2f}x; alternative adjustment {delta:+.3f}. "
                 f"Signal strength day {forecast_day}: {decay:.2f}. Illustrative USD fare, not a quote.")
    return {**opportunity, 'opportunity_score': opportunity['score'], 'base_surge': round(base, 4),
            'weather_boost': round(weather_factor, 4), 'weather_multiplier': round(weather_factor, 4),
            'weather_label': _weather_label(weather) if weather_available else 'Unavailable',
            'alt_route_delta': delta, 'temporal_decay': round(decay, 4), 'multiplier': multiplier,
            'final_surge_multiplier': multiplier, 'capped': raw > 2.5, 'surge_reasoning': reasoning,
            'base_price': get_base_price(origin, destination), 'currency': 'USD'}

def compute_opportunity_score(trend_score, weather_score):
    result = compute_surge_pricing_v2('BOM', 'DXB', trend_score, weather_score)
    return {**result, 'surge_multiplier': result['multiplier']}

def rank_routes(routes_list):
    routes = sorted((dict(r) for r in routes_list), key=lambda r: (-r.get('score', 0), r['destination']))
    return [{**r, 'rank': i+1} for i, r in enumerate(routes)]
