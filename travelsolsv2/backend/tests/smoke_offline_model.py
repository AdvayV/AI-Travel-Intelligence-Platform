"""Real cached Bolt inference with HTTP disabled, not a mocked model test."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chronos_engine as engine


def run():
    with (patch('httpx.Client.request', side_effect=AssertionError('HTTP forbidden')),
          patch('httpx.AsyncClient.request', side_effect=AssertionError('HTTP forbidden')),
          patch('requests.sessions.Session.request', side_effect=AssertionError('HTTP forbidden'))):
        predictions = engine.forecast_batch([
            {'12w':.6, '8w':.7, '2w':.8},
            {'12w':.6, '8w':.5, '2w':None},
        ])
    assert engine.STATUS['status'] == 'ready', engine.STATUS
    assert all(p['forecast_method'] == 'chronos_bolt_blend' for p in predictions)
    assert all(len(p['raw_forecast']) == 5 for p in predictions)
    print('Cached Chronos Bolt CPU inference passed with all HTTP disabled.')
    print('Forecast methods:', [p['forecast_method'] for p in predictions])


if __name__ == '__main__':
    run()
