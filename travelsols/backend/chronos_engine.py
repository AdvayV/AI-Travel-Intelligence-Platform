"""Conservative rank-index forecasting, NOT booking-volume or fare prediction.

Sparse mock snapshots cannot support a validated demand model. Interpolation
is disclosed and Chronos contributes only a small experimental blend weight.
"""
import logging
import os
import threading
import numpy as np
import network_config  # noqa: F401

logger = logging.getLogger(__name__)
MODEL_ID = os.getenv('CHRONOS_MODEL', 'amazon/chronos-bolt-small')
_pipeline = None
_lock = threading.Lock()
STATUS = {'status': 'not_loaded', 'model': MODEL_ID, 'error': None}
WINDOWS = {'12w': -12, '8w': -8, '2w': -2}


def _load():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if os.getenv('CHRONOS_ENABLED', 'true').lower() == 'false':
        STATUS.update(status='disabled')
        return None
    try:
        from chronos import ChronosBoltPipeline
        import torch
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        STATUS.update(status='loading')
        _pipeline = ChronosBoltPipeline.from_pretrained(
            MODEL_ID, device_map='cpu', torch_dtype=torch.float32,
            local_files_only=os.getenv('CHRONOS_ALLOW_DOWNLOAD', 'false').lower() != 'true',
        )
        STATUS.update(status='ready', error=None)
    except Exception as exc:
        STATUS.update(status='unavailable', error=type(exc).__name__)
        logger.warning('Chronos unavailable (%s); damped baseline retained', type(exc).__name__)
    return _pipeline


def forecast_batch(histories):
    """Four weeks from today; missing observations are never zero-filled."""
    results, contexts, eligible = [], [], []
    for history in histories:
        points = sorted((WINDOWS[k], float(v)) for k, v in history.items() if v is not None)
        observation_count = len(points)
        if not points:
            points = [(-2, .5)]
        xs, ys = zip(*points)
        slope = float(np.polyfit(xs, ys, 1)[0]) if len(points) > 1 else 0.0
        slope = float(np.clip(slope * .5, -.025, .025))
        baseline = [float(np.clip(ys[-1] + slope * (1 - .8 ** (w - xs[-1])) / .2, 0, 1)) for w in range(1, 5)]
        widths = [.12 + .025 * i + .04 * (3 - len(points)) for i in range(4)]
        results.append({
            'weekly_forecast': baseline,
            'forecast_lower': [max(0, v - widths[i]) for i, v in enumerate(baseline)],
            'forecast_upper': [min(1, v + widths[i]) for i, v in enumerate(baseline)],
            'forecast_method': 'damped_trend', 'forecast_confidence': 'low',
            'observation_count': observation_count, 'forecast_model_weight': 0,
            'forecast_note': 'Sparse simulated rank snapshots; illustrative, not validated booking demand. Bands are heuristic, not calibrated probabilities.',
        })
        if len(points) >= 2:
            contexts.append(np.interp(np.arange(xs[0], xs[-1] + 1), xs, ys))
            eligible.append((len(results) - 1, xs[-1]))
    with _lock:
        pipeline = _load()
        if pipeline is not None and contexts:
            try:
                import torch
                horizon = max(4 - age for _, age in eligible)
                with torch.inference_mode():
                    quantiles, _ = pipeline.predict_quantiles(
                        [torch.tensor(c, dtype=torch.float32) for c in contexts],
                        prediction_length=horizon, quantile_levels=[.1, .5, .9],
                    )
                for row, (idx, age) in enumerate(eligible):
                    result = results[idx]
                    values = np.clip(quantiles[row, -age:4-age].cpu().numpy(), 0, 1)
                    weight = .2 if result['observation_count'] == 3 else .1
                    for key, col in [('forecast_lower', 0), ('weekly_forecast', 1), ('forecast_upper', 2)]:
                        result[key] = [(1-weight) * b + weight * float(q) for b, q in zip(result[key], values[:, col])]
                    result.update(forecast_method='chronos_bolt_blend', forecast_model_weight=weight,
                                  forecast_note='Experimental Chronos + damped trend blend. Weekly context is interpolated from sparse simulated snapshots; bands are uncalibrated.')
                STATUS.update(status='ready', error=None)
            except Exception as exc:
                STATUS.update(status='inference_failed', error=type(exc).__name__)
                logger.exception('Chronos inference failed; baseline retained')
    for result, history in zip(results, histories):
        for key in ['weekly_forecast', 'forecast_lower', 'forecast_upper']:
            result[key] = [round(v, 4) for v in result[key]]
        observed = [float(history[k]) for k in WINDOWS if history.get(k) is not None]
        change = ((observed[-1] - observed[0]) / max(observed[0], .05) * 100) if len(observed) > 1 else 0
        result.update(momentum_pct=round(change, 1), trend='rising' if change > 3 else 'falling' if change < -3 else 'stable',
                      mean_demand=round(float(np.mean(result['weekly_forecast'])), 4), peak_demand=max(result['weekly_forecast']))
    return results
