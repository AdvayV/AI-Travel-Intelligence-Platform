"""Offline regression tests. No external requests, tokens, or model download."""
import csv
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chronos_engine
import scheduler
import scoring
import weather_client
import travel_advisor
from export.tableau_exporter import route_rows, encode_csv
from fastapi.testclient import TestClient
import main


def route_fixture():
    with patch.object(chronos_engine, '_load', return_value=None):
        forecast = chronos_engine.forecast_batch([{'12w': .6, '8w': .7, '2w': .8}])[0]
    return {'origin': 'BOM', 'destination': 'DXB', 'history': {'12w': .6, '8w': .7, '2w': .8},
            **forecast, 'raw_trend_score': .3, 'trend_score': .3, 'trend_source': 'fallback',
            'base_price': 750, 'updated_at': '2026-10-05T00:00:00+00:00',
            'gds_source': 'simulated', 'weather_source': 'Open-Meteo (live)',
            'currency': 'USD', 'price_source': 'illustrative', 'score': 75, 'tier': 'HOT',
            'current_price': 1100, 'weather_score': .8, 'surge_multiplier': 1.5}


def weather_fixture():
    return {'source': 'Open-Meteo (live)', 'days': [
        {'date': f'2026-10-{5+i:02}', 'appeal': .8 if i != 1 else .2,
         'wmo_code': 0 if i != 1 else 95, 'condition': 'Clear' if i != 1 else 'Storm',
         'temp_max_c': 25, 'temp_min_c': 18} for i in range(14)]}


class PricingTests(unittest.TestCase):
    def price(self, **kwargs):
        inputs = dict(origin='BOM', destination='DXB', trend_score=.5, weather_score=.8, demand_score=.7)
        inputs.update(kwargs)
        return scoring.compute_surge_pricing_v2(**inputs)

    def test_better_weather_increases_opportunity(self):
        self.assertGreater(self.price(weather_score=.9)['score'], self.price(weather_score=.1)['score'])

    def test_clear_wmo_zero_is_valid(self):
        self.assertNotEqual(self.price(weathercode=0)['weather_multiplier'], self.price(weathercode=None)['weather_multiplier'])

    def test_weather_unavailable_is_neutral(self):
        self.assertEqual(self.price(weather_available=False)['weather_multiplier'], 1)

    def test_search_fallback_does_not_affect_demand(self):
        self.assertEqual(self.price(trend_score=0, trend_source='fallback')['multiplier'],
                         self.price(trend_score=1, trend_source='fallback')['multiplier'])

    def test_live_search_contributes(self):
        self.assertGreater(self.price(trend_score=1)['multiplier'], self.price(trend_score=0)['multiplier'])

    def test_alternates_include_primary_score(self):
        self.assertGreater(self.price(alternate_weather_scores={'DOH': .1})['alt_route_delta'], 0)

    def test_equal_alternates_are_neutral(self):
        self.assertEqual(self.price(alternate_weather_scores={'DOH': .8})['alt_route_delta'], 0)

    def test_multiplier_bounds(self):
        for demand in [-2, 0, .5, 1, 3]:
            for weather in [0, .5, 1]:
                value = self.price(demand_score=demand, weather_score=weather)['multiplier']
                self.assertTrue(.75 <= value <= 2.5)

    def test_future_signal_shrinks_toward_neutral(self):
        self.assertLess(abs(self.price(forecast_day=13)['multiplier']-1), abs(self.price(forecast_day=0)['multiplier']-1))

    def test_ranking_does_not_mutate_cache(self):
        source = [{'origin': 'BOM', 'destination': 'DXB', 'score': 20}]
        self.assertEqual(scoring.rank_routes(source)[0]['rank'], 1)
        self.assertNotIn('rank', source[0])


class ForecastTests(unittest.TestCase):
    def forecast(self, history):
        with patch.object(chronos_engine, '_load', return_value=None):
            return chronos_engine.forecast_batch([history])[0]

    def test_rising_series_is_not_placeholder(self):
        result = self.forecast({'12w': .4, '8w': .5, '2w': .6})
        self.assertEqual(result['trend'], 'rising')
        self.assertGreater(result['weekly_forecast'][0], .6)
        self.assertEqual(len(result['weekly_forecast']), 4)

    def test_missing_is_not_zero_filled(self):
        result = self.forecast({'12w': None, '8w': None, '2w': .8})
        self.assertEqual(result['weekly_forecast'], [.8]*4)
        self.assertEqual(result['observation_count'], 1)

    def test_empty_history_discloses_zero_observations(self):
        result = self.forecast({'12w': None, '8w': None, '2w': None})
        self.assertEqual(result['observation_count'], 0)
        self.assertEqual(result['forecast_model_weight'], 0)

    def test_intervals_are_ordered_and_bounded(self):
        for history in [{'12w': 0, '8w': .5, '2w': 1}, {'12w': 1, '8w': .5, '2w': 0}]:
            result = self.forecast(history)
            for low, mid, high in zip(result['forecast_lower'], result['weekly_forecast'], result['forecast_upper']):
                self.assertTrue(0 <= low <= mid <= high <= 1)

    def test_chronos_failure_retains_baseline(self):
        class BrokenModel:
            def predict_quantiles(self, *args, **kwargs): raise RuntimeError('test failure')
        with patch.object(chronos_engine, '_load', return_value=BrokenModel()), patch.object(chronos_engine.logger, 'exception'):
            result = chronos_engine.forecast_batch([{'12w': .4, '8w': .5, '2w': .6}])[0]
        self.assertEqual(result['forecast_method'], 'damped_trend')


class ScheduleTests(unittest.TestCase):
    def test_daily_calendar_and_selected_price_agree(self):
        with patch.object(scheduler, 'get_weather_detail', return_value=weather_fixture()):
            result = scheduler.recompute_forecast_for_day(route_fixture(), 1)
        self.assertEqual(result['current_price'], result['daily_schedules'][1]['price_usd'])
        self.assertEqual(result['selected_weather']['wmo_code'], 95)
        self.assertNotEqual(result['optimal_day_offset'], 1)

    def test_no_weather_means_no_recommendation(self):
        with patch.object(scheduler, 'get_weather_detail', return_value={'days': []}):
            result = scheduler.recompute_forecast_for_day(route_fixture(), 13)
        self.assertNotIn('optimal_day_offset', result)
        self.assertFalse(result['weather_available'])
        self.assertIsNone(result['weather_appeal'])

    def test_day_offset_bounds(self):
        for offset in [-1, 14]:
            with self.assertRaises(ValueError): scheduler.recompute_forecast_for_day(route_fixture(), offset)

    def test_failed_refresh_retains_atomic_cache(self):
        old_cache = scheduler.FORECAST_CACHE
        with patch.object(scheduler, 'get_top_destinations', side_effect=RuntimeError('test')), patch.object(scheduler.logger, 'exception'):
            self.assertFalse(scheduler.run_pipeline())
        self.assertIs(scheduler.FORECAST_CACHE, old_cache)
        scheduler.REFRESH_STATUS['error'] = None

    def test_refresh_single_flight(self):
        scheduler._refresh_lock.acquire()
        try: self.assertFalse(scheduler.run_pipeline())
        finally: scheduler._refresh_lock.release()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.cache_patch = patch.object(scheduler, 'FORECAST_CACHE', {'BOM-DXB': route_fixture()})
        self.weather_patch = patch.object(scheduler, 'get_weather_detail', return_value=weather_fixture())
        self.cache_patch.start(); self.weather_patch.start()

    def tearDown(self):
        self.cache_patch.stop(); self.weather_patch.stop(); self.client.close()

    def test_lowercase_route_and_day_selection(self):
        response = self.client.get('/api/forecast/bom/dxb?day_offset=13')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['selected_day_offset'], 13)

    def test_invalid_queries(self):
        for path in ['/api/forecast/BOM/DXB?day_offset=-1', '/api/forecast/BOM/DXB?day_offset=14',
                     '/api/forecasts?limit=-1', '/api/forecasts?origin=XXX']:
            self.assertEqual(self.client.get(path).status_code, 422)

    def test_missing_route(self):
        self.assertEqual(self.client.get('/api/forecast/BOM/XXX').status_code, 404)

    def test_advisor_receives_selected_date(self):
        with patch.object(travel_advisor, 'get_travel_advisor_result', return_value={'answer': 'test', 'mode': 'local_fallback'}) as advisor:
            response = self.client.post('/api/advisor/BOM/DXB', json={'question': 'Hello', 'day_offset': 5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(advisor.call_args[0][0]['selected_day_offset'], 5)

    def test_csv_provenance_and_units(self):
        response = self.client.get('/api/export/forecast/bom/dxb')
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]['demand_score'], '0.6')
        self.assertEqual(rows[0]['currency'], 'USD')
        self.assertEqual(rows[0]['weather_score'], '')
        self.assertEqual(rows[-1]['forecast_price_usd'], '')

    def test_health_discloses_simulation_and_no_neo4j(self):
        integrations = self.client.get('/api/health').json()['integrations']
        self.assertEqual(integrations['gds']['status'], 'simulated')
        self.assertEqual(integrations['neo4j']['status'], 'not_used')

    def test_missing_advisor_key_is_not_labeled_live(self):
        with patch.dict(os.environ, {'HUGGINGFACE_API_KEY': '', 'HF_TOKEN': ''}):
            result = travel_advisor.get_travel_advisor_result(route_fixture())
        self.assertEqual(result['mode'], 'local_fallback')
        self.assertIsNone(result['model'])


class WeatherTests(unittest.TestCase):
    def test_score_uses_same_detail_normalization(self):
        with patch.object(weather_client, 'get_weather_detail', return_value={'overall_appeal': .72}):
            self.assertEqual(weather_client.get_weather_score(['DXB']), {'DXB': .72})

    def test_failed_fetch_is_cached_not_assumed_clear(self):
        weather_client._DETAIL_CACHE.pop('DXB', None)
        with patch.object(weather_client, '_fetch_raw', return_value=None) as request:
            first = weather_client.get_weather_detail('DXB')
            second = weather_client.get_weather_detail('DXB')
        self.assertEqual(request.call_count, 1)
        self.assertEqual(first['source'], 'unavailable')
        self.assertEqual(second['days'], [])
        weather_client._DETAIL_CACHE.pop('DXB', None)


if __name__ == '__main__':
    unittest.main()
