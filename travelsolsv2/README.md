# TravelRoute Intelligence v2 — Autonomous Travel Booking Agent

TravelRoute Intelligence v2 is the autonomous transaction and booking layer that sits alongside TravelRoute v1. While v1 focuses on time-series travel demand forecasting and surge pricing simulations, v2 focuses on autonomous booking workflows using GraphRAG (Neo4j + ChromaDB), flight shopping APIs (Travel Dev Studio), and a LangChain ReAct agent powered by Meta-Llama-3-8B-Instruct.

---

## Architecture Diagram

```
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
                │  LangChain ReAct Agent    │ <─── [ Mistral-7B-Instruct ]
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

## Free-Tier & Local Integration Limits

This application runs entirely on zero-cost infrastructure and local resources:

| Service / Tool | Tier Details | Capacity Limit | Cost | Account Required |
| --- | --- | --- | --- | --- |
| **Neo4j AuraDB Free** | Cloud graph database | 200,000 nodes & 400,000 relationships | Free | [console.neo4j.io](https://console.neo4j.io/) |
| **ChromaDB** | Fully local vector store | Unlimited storage | Free | Local (No key) |
| **Hugging Face Hub** | Serverless inference API | ~1,000 queries per day (Meta-Llama-3-8B-Instruct) | Free | [huggingface.co](https://huggingface.co/) |
| **Travel Developer Sandbox**| Dev Studio certification environment | Free sandbox testing | Free | [developer.travel.com](https://developer.travel.com/) |
| **Open-Meteo API** | Weather forecasting | Unlimited queries | Free | Local (No key) |

> [!NOTE]
> **Chroma Embedding Model Notice**: On first launch, the local SentenceTransformers embedding model (`all-MiniLM-L6-v2`) will automatically download from Hugging Face. The model is extremely compact (~22MB) and runs entirely on the CPU. Please allow 30 seconds for the model to download and initialize on the first request.

---

## Step-by-Step Configuration & Launch Sequence

### 1. Prerequisites
- Python 3.10 to 3.14 installed on your system.
- Node.js (v18+) and npm installed.

### 2. Getting Credentials
* **Hugging Face Token**: Register/login at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) and generate a **Read** token.
* **Neo4j database**: Spin up a free instance at [console.neo4j.io](https://console.neo4j.io/). Download the credentials file containing the Connection URI, Username (`neo4j`), and Password.
* **Travel Credentials**: Request access at [developer.travel.com](https://developer.travel.com/) for sandbox access. Retrieve your Client ID and Client Secret.

### 3. Setup and Run Backend (v2)
Navigate to the backend folder:
```bash
cd travelroute_v2/backend
```

Create a virtual environment and activate it:
```bash
# Windows
python -m venv venv
venv\Scripts\activate
```

Install requirements:
```bash
pip install -r requirements.txt
```

Launch the FastAPI backend server (Runs on port `8000` by default. Note: if running simultaneously with v1, confirm that ports do not conflict. v1 runs on 8000, v2 runs on 8000 and proxies on 5174):
```bash
uvicorn main:app --reload --port 8000
```
On startup, the backend automatically initializes database constraints, seeds 15 airports and 20 routes in Neo4j, and loads 24 PDF-equivalent travel policy/fare rule text chunks into ChromaDB.

### 4. Setup and Run Frontend (v2)
Open a new terminal window and navigate to the frontend directory:
```bash
cd travelroute_v2/frontend
```

Install node packages:
```bash
npm install
```

Start the Vite development server:
```bash
npm run dev
```
The frontend application will start on **`http://localhost:5174`** (preventing any conflict with v1 which runs on port `5173`).

---

## Side-by-Side Execution (v1 and v2)

You can run both TravelRoute products concurrently to demo the complete workflow:
1. **Demand Forecasting (v1)**: Access the dashboard at `http://localhost:5173` to analyze travel routes, view time-series forecasts, and examine surge-pricing variables.
2. **Autonomous Booking (v2)**: Access the booking interface at `http://localhost:5174`. Paste a booking request (e.g. *"Book economy BOM to DXB tomorrow for Aryan Mehta under policy CP-001"*).
3. **Trace the Agent**: Watch the v2 Agent Trace check active waivers, query weather risks, look up flight options in Travel, perform policy audits, and save transactions to Neo4j.

---

## Offline & Integration Resilience (Auto-Fallback Mode)

TravelRoute v2 features an advanced, bulletproof fallback system designed to ensure the application works even when third-party cloud services or API connections are down:

* **Neo4j Offline Fallback**: If the Neo4j Graph DB connection is offline, blocked, or has incorrect credentials, the backend automatically transitions to a local mock database that simulates the knowledge graph facts and seeding structures.
* **ChromaDB & Hugging Face Model Fallback**: If ChromaDB files are locked, or if the Hugging Face Hub is down (preventing the SentenceTransformers `all-MiniLM-L6-v2` embedding model from being downloaded on first run), ChromaClient falls back to a high-fidelity, local, in-memory **Keyword-Overlap Vector Store**.
* **LLM Fallback**: If the Hugging Face Inference API is down, rate-limited, or unauthorized, the agent executor intercepts the failure and falls back to a mock deterministic execution loop (`run_mock_agent`), preserving full system functionality.

