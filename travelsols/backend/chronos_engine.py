import logging
import torch
from chronos import ChronosBoltPipeline

logger = logging.getLogger(__name__)

# Cache pipeline as module-level singleton
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        try:
            # CPU-only inference for laptop compatibility
            logger.info("Loading chronos-bolt-small model...")
            _pipeline = ChronosBoltPipeline.from_pretrained(
                "amazon/chronos-bolt-small",
                device_map="cpu",
                torch_dtype=torch.float32
            )
            logger.info("Chronos model loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load chronos pipeline: {e}")
            return None
    return _pipeline


def forecast_route_demand(history_dict: dict) -> dict:
    score_12w = float(history_dict.get("12w", 0.0))
    score_8w  = float(history_dict.get("8w",  0.0))
    score_2w  = float(history_dict.get("2w",  0.0))

    pipeline = get_pipeline()

    if pipeline:
        try:
            # ChronosBoltPipeline.predict() signature:
            #   predict(inputs, prediction_length, limit_prediction_length=False)
            # - first arg is called 'inputs' (NOT 'context')
            # - NO num_samples parameter (Bolt is a quantile model, not a sampling model)
            # - returns shape: (batch_size, num_quantiles=9, prediction_length)
            #   quantiles are [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
            #   so index 4 = median (0.5)

            context_tensor = torch.tensor(
                [[score_12w, score_8w, score_2w]], dtype=torch.float32
            )

            # Pass tensor as positional arg 'inputs'
            forecasts = pipeline.predict(
                context_tensor,
                prediction_length=4,
                limit_prediction_length=False
            )

            # forecasts: (1, 9, 4) — take batch 0, quantile index 4 (median 0.5)
            forecast_median = forecasts[0, 4, :]          # shape: [4]
            forecast_median = torch.clamp(forecast_median, 0.0, 1.0)

            mean_forecast   = float(forecast_median.mean())
            peak_forecast   = float(forecast_median.max())
            trend_direction = "rising" if float(forecast_median[-1]) > float(forecast_median[0]) else "falling"
            momentum_score  = float((forecast_median[-1] - score_2w) / max(score_2w, 0.01))

            return {
                "mean_demand":    mean_forecast,
                "peak_demand":    peak_forecast,
                "trend":          trend_direction,
                "momentum_pct":   round(momentum_score * 100, 2),
                "weekly_forecast": [round(float(v), 4) for v in forecast_median.tolist()]
            }

        except Exception as e:
            logger.warning(f"Chronos prediction failed: {e}")

    # --- Fallback: simple linear extrapolation ---
    slope = (score_2w - score_12w) / 2.0
    extrapolated = [min(1.0, max(0.0, score_2w + slope * i)) for i in range(1, 5)]
    mean_forecast   = sum(extrapolated) / 4.0
    peak_forecast   = max(extrapolated)
    trend_direction = "rising" if extrapolated[-1] > extrapolated[0] else "falling"
    momentum_score  = float((extrapolated[-1] - score_2w) / max(score_2w, 0.01))

    return {
        "mean_demand":    mean_forecast,
        "peak_demand":    peak_forecast,
        "trend":          trend_direction,
        "momentum_pct":   round(momentum_score * 100, 2),
        "weekly_forecast": [round(v, 4) for v in extrapolated],
        "fallback":        True
    }
