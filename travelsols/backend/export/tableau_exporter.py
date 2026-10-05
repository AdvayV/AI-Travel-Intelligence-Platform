"""Tableau exports with explicit units, missing values and data provenance."""
import csv
import io
from datetime import datetime, timedelta

def route_rows(route):
    today = datetime.fromisoformat(route['updated_at']).date()
    common = {k: route.get(k) for k in ['origin', 'destination', 'score', 'tier', 'forecast_method',
               'forecast_confidence', 'observation_count', 'gds_source', 'trend_source', 'weather_source', 'price_source', 'currency']}
    rows = []
    for window, weeks in [('12w', 12), ('8w', 8), ('2w', 2)]:
        rows.append({**common, 'date': (today-timedelta(weeks=weeks)).isoformat(), 'window': window,
                     'type': 'Historical', 'demand_score': route['history'].get(window),
                     'lower': None, 'upper': None, 'weather_score': None, 'trend_signal': None,
                     'surge_multiplier': None, 'forecast_price_usd': None})
    rows.append({**common, 'date': today.isoformat(), 'window': 'Today', 'type': 'Boundary',
                 'demand_score': route['weekly_forecast'][0], 'lower': route['forecast_lower'][0],
                 'upper': route['forecast_upper'][0], 'weather_score': route['weather_score'],
                 'trend_signal': route['trend_score'], 'surge_multiplier': route['surge_multiplier'],
                 'forecast_price_usd': route['current_price']})
    for idx, demand in enumerate(route['weekly_forecast']):
        rows.append({**common, 'date': (today+timedelta(weeks=idx+1)).isoformat(), 'window': f'Wk {idx+1}',
                     'type': 'Forecast', 'demand_score': demand, 'lower': route['forecast_lower'][idx],
                     'upper': route['forecast_upper'][idx], 'weather_score': None, 'trend_signal': None,
                     'surge_multiplier': None, 'forecast_price_usd': None})
    return rows

def encode_csv(rows):
    output = io.StringIO(newline='')
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue()
