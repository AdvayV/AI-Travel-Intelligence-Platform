"""Read-only running-v2 checks; no bookings or hosted inference requests."""
import csv
import io
import math
import httpx


def run():
    with httpx.Client(base_url='http://127.0.0.1:8001',timeout=20) as client:
        def get(path):
            response=client.get(path)
            response.raise_for_status()
            return response
        status=get('/api/forecast/status').json()
        assert status['cache_size']>0,'Wait for the initial refresh to finish'
        assert status['hosted_inference']=='not_used'
        assert status['search_interest']=='disabled'
        print('Chronos:',status['chronos'])
        print('Weather:',status['weather'])
        print('Refresh:',status['refresh'])
        all_routes=[]
        for origin in get('/api/origins').json():
            routes=get('/api/forecasts?origin='+origin['code']+'&limit=100').json()
            assert routes
            assert [r['score'] for r in routes]==sorted([r['score'] for r in routes],reverse=True)
            all_routes.extend(routes)
            print(origin['code'],len(routes),'routes')
        assert len(all_routes)==status['cache_size']
        assert len({tuple(r['weekly_forecast']) for r in all_routes})>1
        for route in all_routes:
            days=route['daily_forecast']
            assert len(days)==28
            assert route['history_source']=='simulated_rank_snapshots'
            assert route['currency']=='USD'
            assert route['confidence_label']=='low'
            for day in days:
                assert 0<=day['lower']<=day['demand']<=day['upper']<=1
                assert math.isfinite(day['demand'])
                assert .75<=day['surge_multiplier']<=2.5
                assert day['price_usd']==round(route['base_price']*day['surge_multiplier'],2)
                if not day['weather_available']: assert day['weather_factor']==1
            for i in range(4):
                average=sum(day['demand'] for day in days[i*7:(i+1)*7])/7
                assert abs(average-route['weekly_forecast'][i])<.0002
        chosen=get('/api/forecast/bom/dxb?day_offset=27').json()
        assert chosen['selected_day_offset']==27
        assert chosen['selected_weather'] is None
        assert chosen['current_price']==chosen['daily_forecast'][27]['price_usd']
        for day in [-1,28]:
            assert client.get('/api/forecast/BOM/DXB?day_offset='+str(day)).status_code==422
        assert client.get('/api/forecast/BOM/XXX').status_code==404
        rows=list(csv.DictReader(io.StringIO(get('/api/forecast/BOM/DXB/export').text)))
        assert len(rows)==28 and rows[0]['currency']=='USD' and rows[-1]['weather_appeal']==''
        proxy=httpx.get('http://127.0.0.1:5174/api/forecast/status',timeout=10)
        assert proxy.status_code==200
        # Existing app features: read-only availability, not an accuracy claim.
        assert get('/api/booking/history').status_code==200
        assert get('/api/health').json()['agent_mode']=='deterministic'
        print('Verified:',len(all_routes),'routes,',len(all_routes)*28,'daily estimates; CSV and proxy OK.')
        print('Live smoke checks passed. No bookings or hosted model calls submitted.')


if __name__=='__main__': run()
