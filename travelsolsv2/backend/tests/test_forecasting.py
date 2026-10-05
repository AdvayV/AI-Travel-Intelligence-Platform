"""Offline regression suite; denies network and uses fake quantiles where needed."""
import csv
import io
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import chronos_engine as engine
import scheduler
import scoring
import weather_client as weather
from forecast_api import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def baseline(history=None):
    with patch.object(engine, 'get_pipeline', return_value=None):
        return engine.forecast_route_demand(history or {'12w':.4,'8w':.5,'2w':.6})


def weather_fixture(appeal=.8, count=14, source='Open-Meteo (live)'):
    return {'source':source, 'overall_appeal':appeal, 'days':[
        {'date':(date.today()+timedelta(days=i)).isoformat(), 'appeal':appeal,
         'wmo_code':0,'temp_max_c':25,'temp_min_c':18,'condition':'Clear sky'} for i in range(count)]}


def route_fixture():
    prediction=engine.apply_weather(baseline(),weather_fixture())
    for day in prediction['daily_forecast']: day['price_usd']=round(750*day['surge_multiplier'],2)
    first=prediction['daily_forecast'][0]
    return {**prediction,'origin':'BOM','destination':'DXB','dest_city_name':'Dubai',
            'history':{'12w':.4,'8w':.5,'2w':.6},'history_source':'simulated_rank_snapshots',
            'price_source':'illustrative','base_price':750,'current_price':first['price_usd'],
            'score':first['score'],'tier':first['tier'],'currency':'USD',
            'surge_multiplier':first['surge_multiplier'],'weather_source':'Open-Meteo (live)',
            'weather_score':first['weather_appeal'],'updated_at':'2026-10-05T00:00:00+00:00'}


class NoNetworkTests(unittest.TestCase):
    def setUp(self):
        self.network=patch('httpx.Client.request',side_effect=AssertionError('Unexpected external request'))
        self.network.start()
    def tearDown(self): self.network.stop()


class BaselineTests(NoNetworkTests):
    def test_stable_series_is_stable(self):
        result=baseline({'12w':.7,'8w':.7,'2w':.7})
        self.assertEqual(result['trend'],'stable')
        self.assertEqual(result['weekly_forecast'],[.7]*4)

    def test_missing_observations_are_not_zero(self):
        result=baseline({'12w':None,'8w':None,'2w':.7})
        self.assertEqual(result['observation_count'],1)
        self.assertEqual(result['weekly_forecast'],[.7]*4)

    def test_no_history_is_disclosed(self):
        result=baseline({'12w':None,'8w':None,'2w':None})
        self.assertEqual(result['observation_count'],0)
        self.assertIsNone(result['last_observation_week'])

    def test_nan_and_invalid_values_are_missing(self):
        result=baseline({'12w':float('nan'),'8w':'invalid','2w':1.5})
        self.assertEqual(result['observation_count'],0)

    def test_zero_is_valid_observation(self):
        result=baseline({'12w':0,'8w':0,'2w':0})
        self.assertEqual(result['observation_count'],3)
        self.assertEqual(result['weekly_forecast'],[0]*4)

    def test_true_week_gaps_dampen_extrapolation(self):
        result=baseline({'12w':.4,'8w':.5,'2w':.6})
        self.assertGreater(result['nowcast_demand'],.6)
        self.assertLess(result['weekly_forecast'][-1],.7)

    def test_future_change_is_distinct_from_observed_momentum(self):
        result=baseline()
        self.assertNotEqual(result['momentum_pct'],result['observed_momentum_pct'])

    def test_ordered_ranges_and_bounds(self):
        for history in [{'12w':1,'8w':0,'2w':0},{'12w':0,'8w':1,'2w':1}]:
            result=baseline(history)
            for lo,mid,hi in zip(result['raw_lower'],result['raw_forecast'],result['raw_upper']):
                self.assertTrue(0<=lo<=mid<=hi<=1)


class ModelTests(NoNetworkTests):
    def test_local_files_only_loader(self):
        # This does not load weights or call the Hub.
        from chronos import ChronosBoltPipeline
        with patch.object(engine,'_pipeline',None),patch.object(engine,'_load_failed',False),patch.dict(os.environ,{'CHRONOS_ENABLED':'true'}),patch.object(ChronosBoltPipeline,'from_pretrained',return_value=object()) as loader:
            engine.get_pipeline()
            self.assertTrue(loader.call_args.kwargs['local_files_only'])
            self.assertEqual(loader.call_args.kwargs['device_map'],'cpu')

    def test_disabled_model_does_not_load(self):
        with patch.dict(os.environ,{'CHRONOS_ENABLED':'false'}):
            self.assertIsNone(engine.get_pipeline())

    def test_batched_age_alignment_and_quantile_ordering(self):
        import torch
        class Model:
            def predict_quantiles(self,contexts,prediction_length,quantile_levels):
                self.contexts=contexts
                self.horizon=prediction_length
                raw=torch.zeros((len(contexts),prediction_length,3))
                for i in range(prediction_length): raw[:,i,:]=torch.tensor([.7,.1*i,.2])
                return raw,None
        model=Model()
        histories=[{'12w':.4,'8w':.5,'2w':.6},{'12w':.4,'8w':.5,'2w':None}]
        with patch.object(engine,'get_pipeline',return_value=model):
            result=engine.forecast_batch(histories)
        self.assertEqual(model.horizon,12)
        self.assertEqual(len(model.contexts[0]),11)
        self.assertEqual(len(model.contexts[1]),5)
        self.assertTrue(all(r['forecast_method']=='chronos_bolt_blend' for r in result))
        self.assertLessEqual(result[1]['model_weight'],.1)
        for r in result:
            self.assertEqual(len(r['raw_forecast']),5)
            for lo,mid,hi in zip(r['raw_lower'],r['raw_forecast'],r['raw_upper']):
                self.assertTrue(0<=lo<=mid<=hi<=1)

    def test_failed_inference_falls_back(self):
        class Broken:
            def predict_quantiles(self,*args,**kwargs): raise RuntimeError('offline test')
        with patch.object(engine,'get_pipeline',return_value=Broken()): result=engine.forecast_route_demand({'12w':.4,'8w':.5,'2w':.6})
        self.assertTrue(result['fallback'])
        self.assertEqual(result['model_weight'],0)

    def test_nan_model_output_rejected(self):
        import torch
        class Broken:
            def predict_quantiles(self,contexts,prediction_length,**kwargs):
                return torch.full((1,prediction_length,3),float('nan')),None
        with patch.object(engine,'get_pipeline',return_value=Broken()): result=engine.forecast_route_demand({'12w':.4,'8w':.5,'2w':.6})
        self.assertTrue(result['fallback'])


class WeatherAdjustmentTests(NoNetworkTests):
    def test_clear_vs_storm_affects_demand_and_price(self):
        clear=engine.apply_weather(baseline(),weather_fixture(1))['daily_forecast'][0]
        storm=engine.apply_weather(baseline(),weather_fixture(.1))['daily_forecast'][0]
        self.assertGreater(clear['demand'],storm['demand'])
        self.assertGreater(clear['surge_multiplier'],storm['surge_multiplier'])

    def test_weather_factor_is_bounded(self):
        for appeal in [0,.5,1]:
            result=engine.apply_weather(baseline(),weather_fixture(appeal))
            self.assertTrue(all(.9<=day['weather_factor']<=1.1 for day in result['daily_forecast']))

    def test_no_weather_after_feed_horizon(self):
        result=engine.apply_weather(baseline(),weather_fixture())
        self.assertEqual(result['weekly_weather_coverage'],[7,7,0,0])
        for day in result['daily_forecast'][14:]:
            self.assertFalse(day['weather_available'])
            self.assertEqual(day['weather_factor'],1)
            self.assertIsNone(day['weather'])

    def test_stale_weather_half_strength(self):
        fresh=engine.apply_weather(baseline(),weather_fixture(1))['daily_forecast'][0]['weather_factor']
        stale=engine.apply_weather(baseline(),weather_fixture(1,source='Open-Meteo (stale)'))['daily_forecast'][0]['weather_factor']
        self.assertAlmostEqual(stale-1,(fresh-1)*.5)

    def test_missing_weather_is_neutral_and_ranges_wider(self):
        result=engine.apply_weather(baseline(),weather_fixture(count=0))
        self.assertTrue(all(day['weather_factor']==1 for day in result['daily_forecast']))
        self.assertEqual(result['weekly_weather_coverage'],[0]*4)

    def test_28_daily_rows_and_weekly_average_agree(self):
        result=engine.apply_weather(baseline(),weather_fixture())
        self.assertEqual(len(result['daily_forecast']),28)
        for w in range(4):
            daily=result['daily_forecast'][w*7:(w+1)*7]
            self.assertAlmostEqual(result['weekly_forecast'][w],sum(d['demand'] for d in daily)/7,places=3)


class WeatherCacheTests(NoNetworkTests):
    def setUp(self):
        super().setUp()
        self.temporary=tempfile.TemporaryDirectory()
        self.directory=patch.object(weather,'CACHE_DIR',Path(self.temporary.name))
        self.directory.start()
        self.cache=patch.object(weather,'_DETAIL_CACHE',{})
        self.cache.start()
    def tearDown(self):
        self.cache.stop();self.directory.stop();self.temporary.cleanup();super().tearDown()

    def test_zero_wmo_valid_missing_wmo_unknown(self):
        rows=weather.normalize_daily({'time':[date.today().isoformat(),(date.today()+timedelta(days=1)).isoformat()],
            'weather_code':[0,None],'temperature_2m_max':[25,None]})
        self.assertGreater(rows[0]['appeal'],.9)
        self.assertIsNone(rows[1]['appeal'])
        self.assertIsNone(rows[1]['precipitation_mm'])

    def test_extreme_heat_reduces_comfort(self):
        def appeal(high): return weather.normalize_daily({'time':[date.today().isoformat()],'weather_code':[0],'temperature_2m_max':[high]})[0]['appeal']
        self.assertGreater(appeal(25),appeal(45))

    def test_failure_cached(self):
        with patch.object(weather,'_fetch_raw',return_value=None) as fetch:
            weather.get_weather_detail('DXB');weather.get_weather_detail('dxb')
        self.assertEqual(fetch.call_count,1)

    def test_fresh_disk_cache_avoids_network(self):
        import time
        cached={**weather_fixture(),'dest_code':'DXB'}
        weather._write_disk('DXB',cached,time.time())
        with patch.object(weather,'_fetch_raw',side_effect=AssertionError('Unexpected weather request')):
            self.assertEqual(weather.get_weather_detail('DXB')['source'],'Open-Meteo (live)')

    def test_offline_switch_makes_no_request(self):
        with patch.dict(os.environ,{'WEATHER_NETWORK_ENABLED':'false'}):
            self.assertEqual(weather.get_weather_detail('DXB')['source'],'unavailable')

    def test_stale_cache_disclosed(self):
        import time
        cached={**weather_fixture(),'dest_code':'DXB'}
        weather._write_disk('DXB',cached,time.time()-3600)
        with patch.object(weather,'_fetch_raw',return_value=None): result=weather.get_weather_detail('DXB')
        self.assertTrue(result['stale'])
        self.assertEqual(result['source'],'Open-Meteo (stale)')

    def test_score_and_detail_same_normalization(self):
        with patch.object(weather,'get_weather_detail',return_value={'overall_appeal':.72}):
            self.assertEqual(weather.get_weather_score(['DXB']),{'DXB':.72})


class PipelineTests(NoNetworkTests):
    def setUp(self):
        super().setUp()
        self.cache=patch.object(scheduler,'FORECAST_CACHE',{})
        self.cache.start()
        self.refresh=patch.object(scheduler,'REFRESH_STATUS',{'running':False,'error':None})
        self.refresh.start()
    def tearDown(self): self.cache.stop();self.refresh.stop();super().tearDown()

    def test_refresh_batches_routes_and_deduplicates_weather(self):
        with patch.object(engine,'get_pipeline',return_value=None),patch.object(scheduler,'get_weather_detail',return_value=weather_fixture()) as feed:
            self.assertTrue(scheduler.run_pipeline())
        routes=scheduler.get_cached_forecasts()
        self.assertGreater(len(routes),100)
        self.assertEqual(feed.call_count,len({r['destination'] for r in routes}))
        self.assertTrue(all(r['trend_source']=='disabled' for r in routes))
        self.assertTrue(all(r['currency']=='USD' for r in routes))

    def test_failure_keeps_previous_cache(self):
        scheduler.FORECAST_CACHE['BOM-DXB']=route_fixture()
        before=deepcopy(scheduler.FORECAST_CACHE)
        with patch.object(scheduler,'get_top_destinations',side_effect=RuntimeError('test')),patch.object(scheduler.logger,'exception'):
            self.assertFalse(scheduler.run_pipeline())
        self.assertEqual(scheduler.FORECAST_CACHE,before)

    def test_single_flight_refresh(self):
        scheduler._refresh_lock.acquire()
        try: self.assertFalse(scheduler.run_pipeline())
        finally: scheduler._refresh_lock.release()

    def test_getters_and_ranking_do_not_mutate_cache(self):
        scheduler.FORECAST_CACHE['BOM-DXB']=route_fixture()
        returned=scheduler.get_single_forecast('bom','dxb')
        returned['daily_forecast'][0]['demand']=0
        self.assertNotEqual(scheduler.FORECAST_CACHE['BOM-DXB']['daily_forecast'][0]['demand'],0)
        scheduler.get_cached_forecasts('bom')
        self.assertNotIn('rank',scheduler.FORECAST_CACHE['BOM-DXB'])

    def test_recompute_prices_match_calendar(self):
        route=route_fixture()
        chosen=scheduler.recompute_forecast_for_day(route,27)
        self.assertEqual(chosen['current_price'],route['daily_forecast'][27]['price_usd'])
        self.assertIsNone(chosen['selected_weather'])


class ApiTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(router)
        self.client=TestClient(app)
        self.cache=patch.object(scheduler,'FORECAST_CACHE',{'BOM-DXB':route_fixture()})
        self.cache.start()
    def tearDown(self): self.cache.stop();self.client.close()

    def test_lowercase_route_and_day(self):
        reply=self.client.get('/api/forecast/bom/dxb?day_offset=27')
        self.assertEqual(reply.status_code,200)
        self.assertEqual(reply.json()['selected_day_offset'],27)

    def test_invalid_input(self):
        for url in ['/api/forecast/BOM/DXB?day_offset=-1','/api/forecast/BOM/DXB?day_offset=28',
                    '/api/forecasts?origin=XXX','/api/forecasts?limit=-2','/api/forecasts?limit=101']:
            self.assertEqual(self.client.get(url).status_code,422)

    def test_missing_route(self):
        self.assertEqual(self.client.get('/api/forecast/BOM/XXX').status_code,404)

    def test_status_discloses_sources(self):
        result=self.client.get('/api/forecast/status').json()
        self.assertEqual(result['hosted_inference'],'not_used')
        self.assertEqual(result['search_interest'],'disabled')
        self.assertEqual(result['confidence'],'low')

    def test_csv_contains_daily_ranges_and_sources(self):
        reply=self.client.get('/api/forecast/BOM/DXB/export')
        self.assertEqual(reply.status_code,200)
        rows=list(csv.DictReader(io.StringIO(reply.text)))
        self.assertEqual(len(rows),28)
        self.assertEqual(rows[0]['currency'],'USD')
        self.assertEqual(rows[-1]['weather_appeal'],'')
        self.assertEqual(rows[0]['confidence'],'low')

    def test_list_sorted_without_mutation(self):
        self.assertEqual(self.client.get('/api/forecasts?origin=bom').json()[0]['rank'],1)
        self.assertNotIn('rank',scheduler.FORECAST_CACHE['BOM-DXB'])


if __name__=='__main__': unittest.main()
