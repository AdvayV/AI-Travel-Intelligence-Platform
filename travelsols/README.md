# Route Intelligence (v1)

Route Intelligence is an Autonomous Travel Demand Forecasting and Dynamic Pricing engine. It ranks travel opportunities, computes weather-and-demand surged fare multipliers, locates the most optimal travel dates, and consults an interactive AI Travel Advisor (Qwen3-4B-Instruct) for routing summaries.

---

## 1. Core Logic & Pricing Model

### Dynamic Weighting Engine
The opportunities are ranked using a unified **Opportunity Score** ($0\text{–}100$) derived from live consumer interest and destination comfort signals.
* **Google Trends Component:** Normalised consumer query interest ($0.0\text{–}1.0$) representing $55\%$ of the score.
* **Weather Comfort Component:** Travel appeal score ($0.0\text{–}1.0$) based on precipitation and temperature representing $45\%$ of the score.
* **Surge Pricing Formula:**
  $$\text{Opportunity Score} = \text{round}((\text{Demand} \times 0.55 + (1.0 - \text{Weather Score}) \times 0.45) \times 100, 1)$$

### Optimal Date Recommendation
Analyzes the 14-day schedule to automatically select and recommend the single best day to fly based on:
1. **Weather Comfort:** Ideal temperature ranges ($18\text{–}30^\circ\text{C}$) and clear sky conditions.
2. **Lowest Surge Price:** Minimal dynamic pricing markup.
The optimal day is marked in the UI calendar using golden star badges and recommendation banners.

---

## 2. Technical Architecture

```text
[GDS API Client] ───> gds_client.py ───> (Mock fallback structures)
                                                 │
[Google Trends]  ───> trends_client.py ──────────┼───> scoring.py (Dynamic Surge & Rank)
                                                 │           │
[Open-Meteo API] ───> weather_client.py ─────────┘           ▼
                                                     FastAPI Backend (Port 8000)
                                                     - /api/forecasts
                                                     - /api/advisor (Qwen3 LLM)
                                                             │
                                                             ▼
                                                     React Frontend (Port 5173)
```

---

## 3. Quick Start & Setup

### Backend Setup
1. Create a virtual environment and install requirements:
   ```bash
   cd travelsols/backend
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
2. Create your `.env` file containing the Hugging Face API key:
   ```env
   HUGGINGFACE_API_KEY=your_huggingface_token_here
   ```
3. Launch the Uvicorn web server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

### Frontend Setup
1. Install node dependencies and run the dev server:
   ```bash
   cd travelsols/frontend
   npm install
   npm run dev
   # Server runs at http://localhost:5173
   ```

---

## 4. API Endpoints Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Check system health and backend configurations |
| `/api/origins` | GET | List available origin airport codes |
| `/api/forecasts` | GET | List ranked route forecasts and surge pricing for an origin |
| `/api/forecast/{origin}/{dest}` | GET | Get detailed weather comfort indexes and daily surge details |
| `/api/advisor/{origin}/{dest}` | POST | Query Qwen3-4B-Instruct travel advisor on-demand for route context |
| `/api/refresh` | POST | Trigger background pipeline refresh (optimized to run in under 31s) |
| `/api/export/forecast/{origin}/{dest}` | GET | Export CSV containing dynamic pricing parameters |
