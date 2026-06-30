# TravelRoute Intelligence Suite — v1 & v2

Welcome to the **TravelRoute Intelligence Suite**, a comprehensive travel technology solution combining time-series demand forecasting and autonomous AI booking agents.

This repository hosts two core products:
1. **TravelRoute v1 (Demand Forecasting)**: Predictive analytics engine that forecasts 30-day popularity spikes using Chronos AI, enriches forecasts with Google Trends & Open-Meteo, and runs on port `8000` (frontend on `5173`).
2. **TravelRoute v2 (Autonomous Booking)**: GraphRAG-powered transaction layer that audits corporate policies, checks weather risks, searches flight packages, and books itineraries via a LangChain ReAct agent on port `8001` (frontend on `5174`).

---

## Architecture Overview

### v1: Demand Forecasting Pipeline
```text
[GDS API] ----> gds_client.py ---> (mock fallback data)
                                           |
[Google Trends] -> trends_client.py -------+----> chronos_engine.py
                                           |             |
[Open-Meteo] ----> weather_client.py ------+             v
                                                     scoring.py
                                                         |
                                                    FastAPI Backend (Port 8000)
                                                         |
                                                    React Frontend (Port 5173)
```

### v2: Autonomous Booking Agent
```text
                       [ User Prompt ]
                              │
                              ▼
                ┌───────────────────────────┐
                │    Entity Detection       │
                └─────────────┬─────────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
   ┌───────────────────┐             ┌───────────────────┐
   │    Neo4j Graph    │             │     ChromaDB      │
   │  Waivers, Routes, │             │  Fare Rules, IATA │
   │   Corp Policies   │             │   IROPS History   │
   └─────────┬─────────┘             └─────────┬─────────┘
             │                                 │
             └────────────────┬────────────────┘
                              ▼
                ┌───────────────────────────┐
                │   Combined Context Prompt │
                └─────────────┬─────────────┘
                              │
                              ▼
                ┌───────────────────────────┐
                │  LangChain ReAct Agent    │ <─── [ Meta-Llama-3-8B-Instruct ]
                └──────┬─────────────┬──────┘
                       │             │
        ┌──────────────┘             └──────────────┐
        ▼                                           ▼
┌──────────────┐                             ┌──────────────┐
│  Agent Tools │                             │ Agent Tools  │
│  - Weather   │                             │  - Travel API │
│  - Policy    │                             │  - Graph DB  │
└──────────────┘                             └──────────────┘
```

---

## Free-Tier & Local Integration Limits (v2)

This application runs entirely on zero-cost infrastructure and local resources:

| Service / Tool | Tier Details | Capacity Limit | Cost | Account Required |
| --- | --- | --- | --- | --- |
| **Neo4j AuraDB Free** | Cloud graph database | 200,000 nodes & 400,000 relationships | Free | [console.neo4j.io](https://console.neo4j.io/) |
| **ChromaDB** | Fully local vector store | Unlimited storage | Free | Local (No key) |
| **Hugging Face Hub** | Serverless inference API | ~1,000 queries per day (Meta-Llama-3-8B-Instruct) | Free | [huggingface.co](https://huggingface.co/) |
| **Travel Developer Sandbox**| Dev Studio certification environment | Free sandbox testing | Free | [developer.travel.com](https://developer.travel.com/) |
| **Open-Meteo API** | Weather forecasting | Unlimited queries | Free | Local (No key) |

> [!NOTE]
> **Chroma Embedding Model Notice**: On first launch, the local SentenceTransformers embedding model (`all-MiniLM-L6-v2`) will automatically download from Hugging Face. The model is extremely compact (~22MB) and runs entirely on the CPU.

---

## Setup & Quick Start

### The Easiest Way: Auto Launchers (Windows)
Double-click the launcher batch files located in the project folders:
* 🚀 **[start_v2.bat](file:///C:/Advay%20study/VIT/Coforge%20Internship%20Project/start_v2.bat)** (Workspace root): Launches both backend and frontend servers for v2 simultaneously in separate Windows command prompts.
* 🚀 **[travelsols/start_backend.bat](file:///C:/Advay%20study/VIT/Coforge%20Internship%20Project/travelsols/start_backend.bat)** & **[start_frontend.bat](file:///C:/Advay%20study/VIT/Coforge%20Internship%20Project/travelsols/start_frontend.bat)** (v1 folder): Manages and launches the servers for the v1 forecasting interface.

---

## Step-by-Step Manual Setup

### 1. Prerequisites
- Python 3.10 to 3.14 installed on your system.
- Node.js (v18+) and npm installed.

### 2. Configure Environment Variables
Create a `.env` file inside `travelsolsv2/backend/` and configure your API tokens:
```env
HUGGINGFACE_API_KEY=your_huggingface_token
NEO4J_URI=neo4j+s://your_neo4j_db_id.databases.neo4j.io
NEO4J_USERNAME=your_neo4j_username
NEO4J_PASSWORD=your_neo4j_password
TRAVEL_CLIENT_ID=your_travel_certification_client_id
TRAVEL_CLIENT_SECRET=your_travel_certification_client_secret
```

### 3. Run TravelRoute v1 (Port 8000 & 5173)
**Backend:**
```bash
cd travelsols/backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
**Frontend:**
```bash
cd travelsols/frontend
npm install
npm run dev
# Dashboard available at http://localhost:5173
```

### 4. Run TravelRoute v2 (Port 8001 & 5174)
**Backend:**
```bash
cd travelsolsv2/backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```
**Frontend:**
```bash
cd travelsolsv2/frontend
npm install
npm run dev
# Autonomous Agent UI available at http://localhost:5174
```

---

## Dynamic Cabin & Weather-Resilient Booking Rules (v2)

TravelRoute v2 features smart compliance rules and weather integration driven by the booking query details:

* **Band- and Route-based Cabin Allowance**:
  * **Bands 1-5**: Strictly restricted to Economy Class on all flight routes.
  * **Bands 6-7**: Automatically permitted to fly Business Class on transcontinental long-haul sectors (e.g. `LHR`, `JFK`, `SYD`, `CDG`, `NRT`), but restricted to Economy Class on short/medium-haul routes (e.g. `DXB`, `SIN`, `BKK`).
  * **Bands 8-9**: Permitted to fly Business Class on any route.
* **Smart Policy Mapping**: If no policy ID is provided in the query, the engine dynamically maps the passenger's band level to the corresponding policy (`CP-001` for bands 1-5, `CP-002` for bands 6-8, `CP-003` for band 9).
* **Live Travel Date Weather**: Integrates daily weather forecasts from Open-Meteo for the specific travel date offset, updating the surge multiplier for the date's forecast and displaying the weather directly alongside flight fares.
* **LLM-Based Entity Parsing & City Resolution**: Uses the Hugging Face AI API (with local regex fallback) to semantically extract passenger names, dates, and bands, and automatically map full city names (e.g. "Bangalore" or "London") to IATA codes (e.g. `BLR` or `LHR`).
* **Collapsible Compliance Checklist**: Displays clear checklist audit logs (with green `✓` or red `✗` indicators) inside a collapsible "Booking Proposal" panel to maximize viewport workspace.
* **Fully Offline Flight Selection**: Completely deprecated and removed the third-party Kiwi API integration, routing all flight bookings through deterministic local simulated endpoints.

### Corporate Passenger Band Segmentation

| Corporate Grade | Band Range | Default Policy | Cabin Class Rules | Seeded Mock Employees |
| :--- | :--- | :--- | :--- | :--- |
| **Standard Grade** | Bands 1-5 | `CP-001` (Standard Policy) | Economy only on all routes | Anita Singh (Band 3), Priya Sharma (Band 4) |
| **Senior Management** | Bands 6-8 | `CP-002` (Senior Mgmt) | Business allowed *only* on long-haul/transcontinental routes (e.g., LHR, JFK); restricted to Economy on short-haul routes. | Aryan Mehta (Band 7), Rajesh Kumar (Band 8) |
| **Executive Grade** | Band 9 | `CP-003` (Executive Policy) | Business/First allowed on all routes | Vikram Nair (Band 9) |

---

## Offline & Connection Resilience (Auto-Fallback Mode)

TravelRoute v2 features an advanced, bulletproof fallback system designed to ensure the application works even when third-party cloud services or API connections are down:

* **Neo4j Offline Fallback**: If the Neo4j Graph DB connection is offline, blocked, or has incorrect credentials, the backend automatically transitions to a local mock database that simulates the knowledge graph facts and seeding structures.
* **ChromaDB & Hugging Face Model Fallback**: If ChromaDB files are locked, or if the Hugging Face Hub is down (preventing the SentenceTransformers `all-MiniLM-L6-v2` embedding model from being downloaded on first run), ChromaClient falls back to a high-fidelity, local, in-memory **Keyword-Overlap Vector Store**.
* **LLM Fallback**: If the Hugging Face Inference API is down, rate-limited, or unauthorized, the agent executor intercepts the failure and falls back to a mock deterministic execution loop (`run_mock_agent`), preserving full system functionality.
