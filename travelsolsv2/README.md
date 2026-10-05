# TravelSols v2 — Local Forecasting and Policy-Aware Booking Demo

Three workspaces share one React/FastAPI app:

- Forecasts: local Amazon Chronos Bolt, route-rank sample history and weather.
- Booking: deterministic corporate-policy decisions, flight comparison and
  non-ticketing demo itinerary references.
- Policy graph: Neo4j relationships, policy search and local Chroma retrieval.

The forecasting pipeline is independent of Neo4j, Chroma, flight-search services,
Google Trends and hosted LLM inference. The existing weather feed is its only
network data source. Other booking/graph integrations remain separate features.

## Run

Backend (PowerShell, from travelsolsv2/backend):

    .\venv\Scripts\python.exe -m pip install -r requirements.txt
    .\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001

Frontend (from travelsolsv2/frontend):

    npm install
    npm run dev -- --host 127.0.0.1

Open http://127.0.0.1:5174. API docs: http://127.0.0.1:8001/docs.
v1 can remain on ports 5173/8000 without conflicts. The Windows launchers use
the same v2 ports. Create backend/.env from backend/.env.example when setting
up a new machine. Never commit credentials.

## Local forecasting

The current dataset contains three **simulated rank-index snapshots**, at
12, 8 and 2 weeks ago. These are not observed booking counts, market fares,
or a dataset sufficient to establish real forecasting accuracy.

The pipeline:

1. Preserves missing observations as missing, including in the UI. Zero is a
   valid value, not a substitute for a missing snapshot.
2. Interpolates only between observed points to form a weekly Chronos context.
   Interpolated points do not count as additional observations.
3. Uses a robust median pairwise slope, damped extrapolation and bounded
   rank indices for its baseline; accounts for the age of the last observation.
4. Loads amazon/chronos-bolt-small from local cached files, performs one batched
   CPU inference, and extracts p10/p50/p90 quantiles aligned to today.
5. Blends the model conservatively: at most 20% with three observations, 10%
   with two, and 0% with fewer. Model/baseline disagreement reduces the weight.
   Load/inference errors retain the baseline and are reported in status.
6. Interpolates a nowcast and four future weekly points into 28 daily estimates.
7. Applies a small weather factor, at most +/-10%, fading with distance.
   **Weather is post-processing, not a covariate supplied to Chronos Bolt.**
8. Summarizes the actual daily estimates into four 7-day means and exports the
   same values shown in the UI.

Forecast ranges combine heuristic baseline bounds and model quantiles. They
are **uncalibrated illustrative ranges**, not confidence probabilities.
Confidence is explicitly low. Momentum is not used as a confidence percentage.
Before production, connect regularly sampled real booking data, evaluate
rolling-origin holdouts against naive/seasonal baselines, and calibrate coverage.

### Weather

Open-Meteo supplies up to 14 days of weather; no API key is required. Condition,
temperature comfort, rain and wind determine a consistent 0–1 appeal score.
WMO zero means clear sky; missing WMO or measurements are not silently zeroed.

A shared per-destination cache prevents duplicate requests across routes.
Fresh data lasts 30 minutes and is persisted locally in backend/.cache/weather.
Failed requests have a 5-minute retry cache. On failure, cached data up to six
hours old is labeled stale and receives half the weather adjustment strength.
Beyond supplied dates, weather is unavailable and its adjustment is neutral.
Nothing is copied or invented for forecast weeks 3–4.

Set WEATHER_NETWORK_ENABLED=false to prevent weather HTTP requests. Fresh
cached weather remains usable; stale/absent data follows the same disclosed
fallback. TLS certificate verification stays enabled through OS truststore.

### Pricing and recommendations

All forecasting prices are **illustrative USD estimates**. Base fares are
deterministic sample values. The modeled multiplier is:

    clamp(0.75 + 1.25 × weather-adjusted demand index, 0.75, 2.50)

Weather is not multiplied a second time. Opportunity score is:

    100 × (0.80 × weather-adjusted demand + 0.20 × travel comfort)

Unknown comfort uses a neutral score, while remaining visibly unavailable.
Date recommendations compare comfort / multiplier only among dates with
available, fresh weather and appeal >= 0.5. They do not guarantee the cheapest
flight. Live flight comparison fares are not overwritten by forecasting prices.

Refresh is single-flight, batched and atomic. A failed refresh retains the
previous complete route cache. Readers receive independent copies. Status
reports the actual completed refresh timestamp, duration and model state.

## Forecast API

- GET /api/forecast/status — local model, weather coverage, refresh state.
- GET /api/origins — five Indian departure airports.
- GET /api/forecasts?origin=BOM&limit=25 — ranked route forecasts.
- GET /api/forecast/BOM/DXB?day_offset=0 — selected day plus 28-day calendar.
- GET /api/forecast/BOM/DXB/export — CSV with demand bounds, weather source,
  model contribution, confidence label and explicit USD units.
- GET /api/weather/DXB — shared cached weather feed.
- POST /api/refresh — asynchronous refresh, returns HTTP 202.

Day offsets are 0–27; invalid offsets/limits are rejected. Lowercase IATA codes
are normalized. Missing routes return 404. /api/health includes forecasting
status alongside the existing graph/vector/agent indicators.

## Configuration

- CHRONOS_MODEL=amazon/chronos-bolt-small
- CHRONOS_ENABLED=true
- WEATHER_NETWORK_ENABLED=true
- AGENT_MODE=deterministic (local booking-policy engine)

Chronos runtime always uses local_files_only=True. Provision the model cache
before startup, or copy pre-downloaded model files into the appropriate local
cache. It is already cached on the development machine. A missing model does
not trigger a download; the disclosed damped baseline remains available.

Forecasting does not require Hugging Face, Travel or Neo4j API credentials.
Optional hosted booking-agent / natural-language graph features are separate
from forecasting and may use hosted APIs when invoked/configured. The graph
NL console has its own provider path; do not treat this whole application as
network-isolated merely because local forecasts are enabled.

## Existing booking and policy features

The default agent uses local parsing and corporate-policy rules, retrieves
graph facts and Chroma policy snippets, and compares available flight options.
FLIGHT_DATA_MODE controls the separate flight comparison adapter;
ALLOW_MOCK_FLIGHT_FALLBACK controls its demo fallback. Comparison results are
not ticket issuance, and saved demo references are not airline reservations.

Neo4j credentials are only needed for the graph feature. The configured Aura
hostname currently fails DNS resolution on this machine; the app therefore
uses its mock graph fallback. Forecasting remains fully usable. Mock graph
writes are not proof of persistence to the remote database. Check /api/health
before relying on stored bookings or graph policy updates.

Chroma uses local all-MiniLM-L6-v2 embeddings when available, or keyword-overlap
fallback. Initial embedding setup may contact the Hub independently of the
forecasting model. The policy PDF is corporate_travel_policy.pdf at the repo
root; startup indexes its text locally and attempts graph ingestion.

## Verification

Offline regression suite (from travelsolsv2/backend):

    .\venv\Scripts\python.exe -m unittest discover -s tests -v

Tests deny external HTTP requests for forecasting/model/cache scenarios. They
cover sparse history, real time gaps, quantile alignment, local-only loading,
failure retention, weather expiry and offline mode, API validation and exports.

Real model audit with HTTP disabled (requires cached model weights):

    .\venv\Scripts\python.exe tests\smoke_offline_model.py

Running-app smoke check (same directory):

    .\venv\Scripts\python.exe tests\smoke_live.py

It checks the existing local server, all five origins, daily/weekly consistency,
model/source labels, bounded forecasts, date validation, CSV and the Vite proxy.
It does not submit bookings or hosted inference requests.

Frontend production build (from travelsolsv2/frontend):

    npm run build


