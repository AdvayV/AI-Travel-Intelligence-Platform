# Route Intelligence

1. **What it does**
Route Intelligence is an Autonomous Travel Demand Forecasting Agent that predicts upcoming route popularity spikes. It ingests historical data from GDS, enriches it with Google Trends and Open-Meteo weather signals, and uses a local Chronos AI model to forecast 30-day demand.

2. **Architecture**
```text
[GDS API] ----> gds_client.py ---> (fallback to mock_gds_data.py)
                                           |
[Google Trends] -> trends_client.py -------+----> chronos_engine.py
                                           |             |
[Open-Meteo] ----> weather_client.py ------+             v
                                                     scoring.py
                                                         |
                                                    FastAPI Backend
                                                         |
                                                    React Frontend
```

3. **Setup — Backend**
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt  # note: chronos install takes 2-3 min
cp .env.example .env
# fill in GDS CERT credentials OR leave blank to use mock data
uvicorn main:app --reload --port 8000
```

4. **Setup — Frontend**
```bash
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

5. **First run note**
"Chronos-bolt-small (~100MB) downloads on first run. Allow 2-3 minutes. Subsequent starts are instant."

6. **GDS sandbox credentials**
You can get free CERT credentials by signing up for a developer account at https://developer.gds.com. The app works fully without them using the built-in mock data fallback.

7. **API endpoints reference table**
| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Check system health and model status |
| `/api/origins` | GET | List available origin cities |
| `/api/forecasts` | GET | List ranked route forecasts for an origin |
| `/api/forecast/{origin}/{dest}` | GET | Get detailed forecast for a single route |
| `/api/refresh` | POST | Trigger background pipeline refresh |
