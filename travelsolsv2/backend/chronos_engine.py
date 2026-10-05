"""Local-only Chronos Bolt with conservative sparse-history regularization.

The current inputs are simulated rank indices, NOT observed bookings. Linear
interpolation adds no evidence. Bounds are illustrative and uncalibrated.
"""
import logging
import math
import os
import threading
import numpy as np

logger = logging.getLogger(__name__)
MODEL_ID = os.getenv("CHRONOS_MODEL", "amazon/chronos-bolt-small")
WINDOWS = {"12w": -12, "8w": -8, "2w": -2}
STATUS = {"status": "not_loaded", "model": MODEL_ID, "execution": "local_cpu",
          "external_inference": False, "error": None}
_pipeline = None
_inference_lock = threading.RLock()
_load_failed = False

def get_pipeline():
    global _pipeline, _load_failed
    with _inference_lock:
        if os.getenv("CHRONOS_ENABLED", "true").lower() == "false":
            STATUS.update(status="disabled")
            return None
        if _pipeline is not None: return _pipeline
        if _load_failed: return None
        try:
            from chronos import ChronosBoltPipeline
            import torch
            torch.set_num_threads(min(4, os.cpu_count() or 1))
            STATUS.update(status="loading")
            # No network call or automatic model download at runtime.
            _pipeline = ChronosBoltPipeline.from_pretrained(
                MODEL_ID, device_map="cpu", dtype=torch.float32, local_files_only=True)
            STATUS.update(status="ready", error=None)
        except Exception as exc:
            _load_failed = True
            STATUS.update(status="unavailable", error=type(exc).__name__)
            logger.warning("Local Chronos unavailable (%s); using baseline", type(exc).__name__)
        return _pipeline

def _observations(history):
    points = []
    for key, week in WINDOWS.items():
        value = history.get(key)
        if value is None: continue
        try: value = float(value)
        except (ValueError, TypeError): continue
        if math.isfinite(value) and 0 <= value <= 1:
            points.append((week, value))
    return sorted(points)

def _baseline(points):
    count = len(points)
    age, latest = points[-1] if points else (-2, .5)
    # Median pairwise slope resists one anomalous snapshot; use true week gaps.
    slopes = [(b[1]-a[1])/(b[0]-a[0]) for i, a in enumerate(points) for b in points[i+1:]]
    slope = float(np.clip(np.median(slopes) * .5, -.025, .025)) if slopes else 0.0
    # Weeks 0..4 from today, accounting for the age of the latest observation.
    center = [float(np.clip(latest+slope*(1-.8**(w-age))/.2, 0, 1)) for w in range(5)]
    dispersion = float(np.std([v for _, v in points])) if count > 1 else .1
    width = [.1 + .03*(3-count) + min(.12, dispersion*.5) + .025*w for w in range(5)]
    return {
        "raw_forecast": center,
        "raw_lower": [max(0, v-width[i]) for i,v in enumerate(center)],
        "raw_upper": [min(1, v+width[i]) for i,v in enumerate(center)],
        "forecast_method": "damped_trend", "fallback": True, "model_weight": 0.0,
        "observation_count": count, "last_observation_week": age if count else None,
        "context_kind": "interpolated_sparse_snapshots", "confidence_label": "low",
        "forecast_note": "Simulated sparse rank data; interpolated context is not extra evidence. Ranges are uncalibrated, not probabilities.",
    }

def forecast_batch(histories):
    """Batched local inference; return nowcast and four future weekly points."""
    points = [_observations(h) for h in histories]
    results = [_baseline(p) for p in points]
    eligible = [i for i,p in enumerate(points) if len(p) >= 2]
    with _inference_lock:
        pipeline = get_pipeline() if eligible else None
        if pipeline is not None:
            try:
                import torch
                contexts = []
                for i in eligible:
                    xs, ys = zip(*points[i])
                    contexts.append(torch.tensor(np.interp(np.arange(xs[0],xs[-1]+1),xs,ys),dtype=torch.float32))
                horizon = max(4-points[i][-1][0] for i in eligible)
                with torch.inference_mode():
                    quantiles, _ = pipeline.predict_quantiles(contexts, prediction_length=horizon, quantile_levels=[.1,.5,.9])
                # Validate the entire batch before applying it; failure retains baseline.
                raw = quantiles.detach().cpu().numpy()
                if raw.shape != (len(eligible), horizon, 3) or not np.isfinite(raw).all():
                    raise ValueError("Invalid quantile output")
                for row, i in enumerate(eligible):
                    age, latest = points[i][-1]
                    model = np.sort(np.clip(raw[row,-age-1:4-age],0,1),axis=1)
                    # Downweight disagreement instead of letting sparse context dominate.
                    disagreement = float(np.mean(np.abs(model[:,1]-results[i]["raw_forecast"])))
                    weight = (.2 if len(points[i]) == 3 else .1) * max(.25,1-disagreement)
                    for key, col in [("raw_lower",0),("raw_forecast",1),("raw_upper",2)]:
                        results[i][key] = [(1-weight)*b+weight*float(q) for b,q in zip(results[i][key],model[:,col])]
                    results[i].update(forecast_method="chronos_bolt_blend", fallback=False, model_weight=round(weight,4))
                STATUS.update(status="ready", error=None)
            except Exception as exc:
                STATUS.update(status="inference_failed",error=type(exc).__name__)
                logger.warning("Chronos inference failed (%s); baseline retained",type(exc).__name__)
    for result, observed in zip(results,points):
        for key in ["raw_lower","raw_forecast","raw_upper"]:
            result[key] = [round(v,4) for v in result[key]]
        result["weekly_forecast"] = result["raw_forecast"][1:]
        result["forecast_lower"] = result["raw_lower"][1:]
        result["forecast_upper"] = result["raw_upper"][1:]
        result["nowcast_demand"] = result["raw_forecast"][0]
        result["mean_demand"] = round(float(np.mean(result["weekly_forecast"])),4)
        result["peak_demand"] = max(result["weekly_forecast"])
        # Forecast change is distinct from observed history change.
        change = result["weekly_forecast"][-1]-result["nowcast_demand"]
        result["trend"] = "rising" if change > .01 else "falling" if change < -.01 else "stable"
        result["momentum_pct"] = round(change/max(result["nowcast_demand"],.05)*100,1)
        result["observed_momentum_pct"] = round((observed[-1][1]-observed[0][1])/max(observed[0][1],.05)*100,1) if len(observed)>1 else None
    return results

def forecast_route_demand(history_dict):
    return forecast_batch([history_dict])[0]

def apply_weather(forecast, weather):
    """Post-process model output; Bolt itself has NO weather covariate input.

    The same small adjustment drives daily prices and weekly forecast summaries,
    avoiding double counting. Outside available weather days it is exactly neutral.
    """
    from scoring import day_metrics
    days = {d["date"]: d for d in weather.get("days",[]) if d.get("date")}
    from datetime import date, timedelta
    today = date.today()
    daily = []
    for offset in range(28):
        week = offset/7
        mid = float(np.interp(week,range(5),forecast["raw_forecast"]))
        lower = float(np.interp(week,range(5),forecast["raw_lower"]))
        upper = float(np.interp(week,range(5),forecast["raw_upper"]))
        day_date = (today+timedelta(days=offset)).isoformat()
        conditions = days.get(day_date,{})
        appeal = conditions.get("appeal")
        source = weather.get("source","unavailable") if appeal is not None else "unavailable"
        # Max +/-10%, fades with horizon. Stale inputs contribute half strength.
        strength = .5 if source == "Open-Meteo (stale)" else 1.0
        factor = 1+.1*(2*appeal-1)*math.exp(-offset/28)*strength if appeal is not None else 1.0
        adjusted = float(np.clip(mid*factor,0,1))
        lo, hi = float(np.clip(lower*factor,0,1)), float(np.clip(upper*factor,0,1))
        # Widen illustrative bounds when weather is not available.
        if appeal is None: lo, hi = max(0,lo-.03), min(1,hi+.03)
        daily.append({"day_offset":offset,"date":day_date,"raw_demand":round(mid,4),
            "demand":round(adjusted,4),"lower":round(lo,4),"upper":round(hi,4),
            "weather_factor":round(factor,4),"weather_appeal":appeal,"weather_source":source,
            "weather_available":appeal is not None,"weather":conditions or None,
            **day_metrics(adjusted,appeal)})
    weekly = [daily[w*7:(w+1)*7] for w in range(4)]
    means = lambda key: [round(float(np.mean([d[key] for d in group])),4) for group in weekly]
    predicted = means("demand")
    change = predicted[-1]-daily[0]["demand"]
    return {**forecast,"weekly_forecast":predicted,"forecast_lower":means("lower"),"forecast_upper":means("upper"),
        "raw_weekly_forecast":forecast["weekly_forecast"],
        "weekly_weather_coverage":[sum(d["weather_available"] for d in group) for group in weekly],
        "daily_forecast":daily,"mean_demand":round(float(np.mean(predicted)),4),"peak_demand":max(predicted),
        "trend":"rising" if change>.01 else "falling" if change<-.01 else "stable",
        "momentum_pct":round(change/max(daily[0]["demand"],.05)*100,1)}
