import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List

def export_chronos_forecast_to_csv(
    origin: str,
    destination: str,
    historical_data: Dict[str, float],  # {'12w': 0.65, '8w': 0.78, '2w': 0.82}
    forecast_data: List[float],  # [0.80, 0.79, 0.78, 0.77] (4 weeks ahead)
    weather_scores: Dict[str, float],  # {'today': 0.95, 'wk1': 0.75, 'wk2': 0.60, ...}
    trend_score: float,  # 0.3 or 0.0
    opportunity_score: float,  # 45.2
    surge_multiplier: float,  # 1.35
    base_price: int,  # 32000
    filepath: str = 'forecast_export.csv'
) -> str:
    '''
    Export Chronos forecast to CSV for Tableau consumption.
    Returns the filepath of the generated CSV.
    '''
    
    today = datetime.now()
    
    # Historical data points (past)
    historical_dates = [
        (today - timedelta(weeks=12)).strftime('%Y-%m-%d'),
        (today - timedelta(weeks=8)).strftime('%Y-%m-%d'),
        (today - timedelta(weeks=2)).strftime('%Y-%m-%d'),
    ]
    
    # Forecast data points (future)
    forecast_dates = [
        (today + timedelta(weeks=i+1)).strftime('%Y-%m-%d')
        for i in range(len(forecast_data))
    ]
    
    # Build rows
    rows = []
    
    # Historical rows
    for i, date in enumerate(historical_dates):
        window = ['12w', '8w', '2w'][i]
        rows.append({
            'date': date,
            'window': window,
            'origin': origin,
            'destination': destination,
            'demand_score': historical_data.get(window, 0),
            'weather_score': 0.75,  # Approximate (historical weather not tracked)
            'trend_signal': trend_score if i == 2 else 0,  # Latest window
            'type': 'Historical',
            'surge_multiplier': 1.0,
            'forecast_price_inr': base_price,
        })
    
    # Forecast rows (today is the boundary)
    rows.append({
        'date': today.strftime('%Y-%m-%d'),
        'window': 'Today',
        'origin': origin,
        'destination': destination,
        'demand_score': historical_data.get('2w', 0.5),  # Current
        'weather_score': weather_scores.get('today', 0.75),
        'trend_signal': trend_score,
        'type': 'Boundary',
        'surge_multiplier': surge_multiplier,
        'forecast_price_inr': int(base_price * surge_multiplier),
    })
    
    for i, date in enumerate(forecast_dates):
        rows.append({
            'date': date,
            'window': f'Wk {i+1}',
            'origin': origin,
            'destination': destination,
            'demand_score': forecast_data[i] if i < len(forecast_data) else 0.5,
            'weather_score': weather_scores.get(f'wk{i+1}', 0.7),
            'trend_signal': 0,
            'type': 'Forecast',
            'surge_multiplier': surge_multiplier * (1.0 - i*0.1),  # Decay over weeks
            'forecast_price_inr': int(base_price * surge_multiplier * (1.0 - i*0.1)),
        })
    
    # Convert to DataFrame
    df = pd.DataFrame(rows)
    
    # Save to CSV
    df.to_csv(filepath, index=False)
    
    return filepath

def export_all_routes_to_csv(routes_dict: Dict, filepath: str = 'all_routes_forecast.csv') -> str:
    '''Export all routes to a single Tableau-compatible CSV.'''
    all_rows = []
    
    for route_key, route_data in routes_dict.items():
        origin, dest = route_key.split('-')
        
        # Generate rows for this route
        today = datetime.now()
        historical_dates = [
            (today - timedelta(weeks=12)).strftime('%Y-%m-%d'),
            (today - timedelta(weeks=8)).strftime('%Y-%m-%d'),
            (today - timedelta(weeks=2)).strftime('%Y-%m-%d'),
        ]
        
        # GDS rank normalization to 0-1
        rank_2w = route_data.get('gds_rank_2w', 25)
        rank_8w = route_data.get('gds_rank_8w', 25)
        rank_12w = route_data.get('gds_rank_12w', 25)
        
        gds_2w_norm = (51 - rank_2w) / 50.0
        gds_8w_norm = (51 - rank_8w) / 50.0
        gds_12w_norm = (51 - rank_12w) / 50.0
        
        historical_norms = [gds_12w_norm, gds_8w_norm, gds_2w_norm]
        
        for i, date in enumerate(historical_dates):
            all_rows.append({
                'date': date,
                'route': f'{origin}->{dest}',
                'origin': origin,
                'destination': dest,
                'demand_score': historical_norms[i],
                'weather_score': route_data.get('weather_score', 0.7),
                'trend_signal': route_data.get('trend_score', 0) if i == 2 else 0,
                'type': 'Historical',
                'opportunity_score': route_data.get('score', 0),
                'tier': route_data.get('tier', 'WATCH'),
                'momentum_pct': route_data.get('momentum_pct', 0),
                'surge_multiplier': 1.0,
            })
        
        # Boundary (Today)
        all_rows.append({
            'date': today.strftime('%Y-%m-%d'),
            'route': f'{origin}->{dest}',
            'origin': origin,
            'destination': dest,
            'demand_score': gds_2w_norm,
            'weather_score': route_data.get('weather_score', 0.7),
            'trend_signal': route_data.get('trend_score', 0),
            'type': 'Boundary',
            'opportunity_score': route_data.get('score', 0),
            'tier': route_data.get('tier', 'WATCH'),
            'momentum_pct': route_data.get('momentum_pct', 0),
            'surge_multiplier': route_data.get('surge_multiplier', 1.0),
        })
        
        # Forecast
        weekly_forecast = route_data.get('weekly_forecast', [0.7, 0.7])
        for i in range(len(weekly_forecast)):
            decay = (1.0 - i * 0.1)
            all_rows.append({
                'date': (today + timedelta(weeks=i+1)).strftime('%Y-%m-%d'),
                'route': f'{origin}->{dest}',
                'origin': origin,
                'destination': dest,
                'demand_score': weekly_forecast[i],
                'weather_score': route_data.get('weather_score', 0.7),
                'trend_signal': 0,
                'type': 'Forecast',
                'opportunity_score': route_data.get('score', 0),
                'tier': route_data.get('tier', 'WATCH'),
                'momentum_pct': route_data.get('momentum_pct', 0),
                'surge_multiplier': route_data.get('surge_multiplier', 1.0) * decay,
            })
    
    df = pd.DataFrame(all_rows)
    df.to_csv(filepath, index=False)
    print(f'✓ Exported {len(all_rows)} forecast rows to {filepath}')
    
    return filepath
