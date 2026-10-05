"""Verify a running v1 service. --advisor opts into one hosted inference call."""
import argparse
import csv
import io
import math
import httpx


def run(advisor=False):
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=45) as client:
        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response
        health = get('/api/health').json()
        assert health['cache_size'] > 0, 'Wait for the initial refresh to finish'
        print('Health:', health['status'], '| Routes:', health['cache_size'])
        all_routes = []
        for origin in get('/api/origins').json():
            routes = get('/api/forecasts?origin='+origin['code']+'&limit=100').json()
            assert routes
            assert all(0 <= r['score'] <= 100 and .75 <= r['surge_multiplier'] <= 2.5 for r in routes)
            assert [r['score'] for r in routes] == sorted([r['score'] for r in routes], reverse=True)
            for route in routes:
                assert len(route['weekly_forecast']) == 4
                assert all(math.isfinite(x) for x in route['weekly_forecast'])
                assert all(0 <= lo <= mid <= hi <= 1 for lo, mid, hi in zip(
                    route['forecast_lower'], route['weekly_forecast'], route['forecast_upper']))
            all_routes.extend(routes)
            print(origin['code']+':',len(routes),'routes')
        assert len(set(tuple(r['weekly_forecast']) for r in all_routes)) > 1
        route = get('/api/forecast/bom/dxb?day_offset=13').json()
        assert len(route['daily_schedules']) == 14
        assert route['current_price'] == route['daily_schedules'][13]['price_usd']
        assert route['selected_day_offset'] == 13
        assert client.get('/api/forecast/BOM/DXB?day_offset=-1').status_code == 422
        assert client.get('/api/forecast/BOM/DXB?day_offset=14').status_code == 422
        assert client.get('/api/forecast/BOM/XXX').status_code == 404
        weather = get('/api/weather/DXB').json()
        print('DXB weather:', weather['source'], '| Days:', len(weather['days']))
        route_csv = list(csv.DictReader(io.StringIO(get('/api/export/forecast/BOM/DXB').text)))
        assert len(route_csv) == 8 and route_csv[0]['currency'] == 'USD'
        all_csv = list(csv.DictReader(io.StringIO(get('/api/export/all-routes').text)))
        assert len(all_csv) == len(all_routes)*8
        print('CSV export:',len(all_csv),'rows; USD and source fields verified')
        if advisor:
            response = client.post('/api/advisor/BOM/DXB',json={'question':'Summarize this route in two sentences.','day_offset':13})
            response.raise_for_status()
            result = response.json()
            assert result['answer']
            print('Advisor:',result['mode'],'| Model:',result['model'],'| Error:',result.get('error'))
            assert result['mode'] == 'live', 'Advisor used local fallback; inspect /api/health for provider error'
        for provider, status in get('/api/health').json()['integrations'].items():
            print(provider+':', status['status'], status.get('model',''), status.get('error') or '')
        print('Live smoke checks passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--advisor', action='store_true')
    run(parser.parse_args().advisor)
