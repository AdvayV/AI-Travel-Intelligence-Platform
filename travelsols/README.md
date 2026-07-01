# Route Intelligence (v1)

Route Intelligence is an Autonomous Travel Demand Forecasting and Dynamic Pricing engine. It ranks travel opportunities, computes weather-and-demand surged fare multipliers, locates the most optimal travel dates, and consults an interactive AI Travel Advisor (Qwen3-4B-Instruct) for routing summaries.

---

## 1. Core Logic & Pricing Model

### Raw Base Score (Demand Score)
The **Raw Base** represents the clean demand interest of a route extracted entirely from normalized Google Trends search volume data:
$$\text{Demand Score} = \text{clamp}(\text{Trend Score}, 0.0, 1.0)$$
$$\text{Raw Base (\%)} = \text{round}(\text{Demand Score} \times 100, 1)$$

### Dynamic Opportunity Score
The **Opportunity Score** is a weighted rating from `0` to `100` that evaluates how favorable a travel route currently is. It combines high traveler interest with good weather at the destination (where $1.0 - \text{Weather Score}$ represents good weather):
$$\text{Opportunity Score} = \text{round}\left( \left( \text{Demand Score} \times 0.55 + (1.0 - \text{Weather Score}) \times 0.45 \right) \times 100, 1 \right)$$
* **Demand Weight:** 55%
* **Inverse Weather Comfort Weight:** 45%

### Opportunity Tiers
* **$\ge 80$:** `PLATINUM` (Extremely high demand/perfect weather)
* **$65 - 79$:** `HOT`
* **$45 - 64$:** `RISING`
* **$25 - 44$:** `WATCH`
* **$< 25$:** `COLD` (Triggers discount pricing)

### Base Surge Multiplier
The **Base Surge** is calculated progressively depending on which tier bracket the Opportunity Score falls into:
* **Cold ($< 25$):** 
  $$\text{Base Surge} = 0.75 + \left(\frac{\text{Opportunity Score}}{25.0}\right) \times 0.15 \quad \text{[0.75× to 0.90× discounts]}$$
* **Watch ($25 - 44$):** 
  $$\text{Base Surge} = 0.90 + \left(\frac{\text{Opportunity Score} - 25}{20.0}\right) \times 0.10 \quad \text{[0.90× to 1.00× standard]}$$
* **Rising ($45 - 64$):** 
  $$\text{Base Surge} = 1.00 + \left(\frac{\text{Opportunity Score} - 45}{20.0}\right) \times 0.40 \quad \text{[1.00× to 1.40× surges]}$$
* **Hot ($65 - 79$):** 
  $$\text{Base Surge} = 1.40 + \left(\frac{\text{Opportunity Score} - 65}{15.0}\right) \times 0.45 \quad \text{[1.40× to 1.85× surges]}$$
* **Platinum ($\ge 80$):** 
  $$\text{Base Surge} = 1.85 + \left(\frac{\text{Opportunity Score} - 80}{20.0}\right) \times 0.65 \quad \text{[1.85× to 2.50× maximum surge]}$$

### Final Surged Multiplier
The final multiplier applied to the base ticket fare adds weather-based adjustments and alternate routing details:
$$\text{Final Surge} = \text{clamp}(\text{Base Surge} + \text{Weather Boost} + \text{Alternate Route Delta}, 0.75, 2.50)$$
* **Weather Boost:** calculated as $\max(0.0, \text{Weather Multiplier} - 1.0) \times 0.30$.
* **Surge Cap Ceiling:** Hard-capped at **`2.50×`** (flags `CAPPED` on the travel cards).
* **Surge Floor:** Floor-limited to **`0.75×`** (ensuring maximum discount never falls below 25% off base fare).

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
