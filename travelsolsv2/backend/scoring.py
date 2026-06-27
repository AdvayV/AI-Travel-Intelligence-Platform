def compute_opportunity_score(travel_momentum: float, trend_score: float, weather_score: float, chronos_momentum_pct: float) -> dict:
    base_score = travel_momentum * 0.45
    trend_bonus = trend_score * 0.20
    weather_bonus = weather_score * 0.20
    chronos_bonus = min(chronos_momentum_pct / 100.0, 1.0) * 0.15
    
    final = (base_score + trend_bonus + weather_bonus + chronos_bonus) * 100
    final = max(0.0, min(100.0, final))
    
    tier = 'WATCH'
    if final >= 65:
        tier = 'HOT'
    elif final >= 40:
        tier = 'RISING'
        
    return {
        'score': round(final, 1),
        'tier': tier
    }

def rank_routes(routes_list: list[dict]) -> list[dict]:
    sorted_routes = sorted(routes_list, key=lambda x: x.get('score', 0), reverse=True)
    for i, route in enumerate(sorted_routes):
        route['rank'] = i + 1
    return sorted_routes
