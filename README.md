# TravelSols: TravelRoute Intelligence Suite

Two related demo projects combine route planning with policy-aware flight comparison.

| Project | Purpose | Frontend | Backend |
| --- | --- | --- | --- |
| [v1](travelsols/README.md) | Forecasts, weather/date comparison, AI advisor and CSV exports | http://127.0.0.1:5173 | http://127.0.0.1:8000 |
| [v2](travelsolsv2/README.md) | Local forecasts, GraphRAG, hybrid retrieval and policy-aware flight comparison | http://127.0.0.1:5174 | http://127.0.0.1:8001 |

**Demo boundaries:** historical demand inputs are simulated rank indices, not measured
bookings. Forecast prices are illustrative USD estimates. v2 separately attempts
Google Flights comparison fares in INR and labels estimated fallback results.
Neither project issues tickets. Hosted LLM inference is optional and subject to
provider access, pricing and limits; it is not guaranteed free.

## Quick start

On Windows, double-click [start_v1.bat](start_v1.bat) and/or [start_v2.bat](start_v2.bat).
The launchers start background servers, verify the frontend API proxy, and print URLs.
Both versions can run together. Logs are saved in .startup-logs/.

- Install Python and Node.js/npm compatible with the dependency manifests.
- Copy each backend's .env.example to .env on a new machine; never commit credentials.
- v1 uses travelsols/venv; v2 uses travelsolsv2/backend/venv.
- Initial model/database loading can take several minutes.
- Each project also has start_all.bat, start_backend.bat and start_frontend.bat.
- Individual launchers run in a console; Ctrl+C stops that server.
- Use the individual launcher's --install argument after changing dependencies.
- Re-running the root launcher **reuses**, rather than restarts, responding servers.
  After code/credential changes, stop that version's backend and launch it again.

## Part 1: v1 route intelligence

**Tools:** React 18, Vite, Recharts, FastAPI, Python/PyTorch, local Amazon Chronos Bolt,
APScheduler, Open-Meteo, optional pytrends and an optional hosted Qwen advisor.

**Features:** ranked destination forecasts, demand/range charts, 14-day weather and
illustrative fares, comfort-to-modeled-cost date recommendations, route-specific
advisor chat, integration status and Tableau-compatible CSV exports.

### v1 architecture

~~~mermaid
flowchart TD
    UI["React / Vite / Recharts :5173"] --> API["FastAPI :8000"]
    API --> Cache["Atomic route forecast cache"]
    Scheduler["APScheduler / manual refresh"] --> Samples["Simulated rank-index snapshots"]
    Samples --> Forecast["Damped baseline + local Chronos Bolt"]
    Forecast --> Score["Scoring / illustrative USD pricing"]
    Trends["Optional Google Trends"] --> Score
    Weather["Open-Meteo / weather cache"] --> Score
    Score --> Cache
    Cache --> CSV["CSV / Tableau export"]
    API --> Context["Selected route and date context"]
    Cache --> Context
    Context --> Advisor["Optional hosted Qwen / local fallback answer"]
    Advisor --> API
~~~

The chatbot explains structured route/weather/forecast context.
**v1 does not use Neo4j, ChromaDB or document GraphRAG.**
Sparse simulated history and uncalibrated ranges cannot establish real demand accuracy.

## Part 2: v2 policy-aware travel demo

**Tools:** React/Vite, Recharts/D3, FastAPI, Neo4j/Cypher, ChromaDB,
SentenceTransformers all-MiniLM-L6-v2, local BM25, reciprocal rank fusion (RRF),
pypdf, Chronos Bolt, Open-Meteo, fast-flights, and optional LangChain ReAct/Qwen.

**Features:** independent local forecasting, PDF ingestion, policy graph exploration,
natural-language retrieval, grade-based cabin decisions, flight comparison,
weather/compliance checklists, cited evidence, user-confirmed non-ticketing demo
references and booking history.

### v2 architecture

~~~mermaid
flowchart TD
    UI["React / Vite :5174"] --> API["FastAPI :8001"]
    PDF["Corporate policy PDF"] --> Ingest["pypdf / bounded page-aware chunks"]
    Ingest --> Graph["Neo4j entities and rule relationships"]
    Ingest --> Vector["ChromaDB / local MiniLM embeddings"]
    API --> Parse["Entity / grade / date parsing"]
    Parse --> Traversal["Parameterized graph retrieval"]
    Graph --> Traversal
    Parse --> Dense["Semantic candidates"]
    Vector --> Dense
    Parse --> Sparse["BM25 document ranking"]
    Vector --> Sparse
    Dense --> Fuse["RRF / relevance gate / dedup / context budget"]
    Sparse --> Fuse
    Fuse --> Linked["Matching PDF graph rules"]
    Graph --> Linked
    Traversal --> Evidence["Citations / sources / retrieval diagnostics"]
    Fuse --> Evidence
    Linked --> Evidence
    Evidence --> Answer["Grounded policy excerpts"]
    Evidence --> Booking["Deterministic checks / optional ReAct"]
    Booking --> Flights["Flight comparison / labeled fallback"]
    Booking --> Weather["Open-Meteo"]
    Booking --> Rules["Grade / fare / advance / approval checks"]
    Answer --> UI
    Rules --> UI
    UI --> Confirm["Explicit demo-reference confirmation"]
    Confirm --> Graph
    API --> Forecast["Independent local Chronos forecast cache"]
~~~

### RAG and hybrid retrieval

v2 combines **structured graph retrieval** with **dense semantic + sparse BM25
document search**, not just fixed hits concatenated from each collection:

1. Parse entities and enrich the query with policy, route and fare identifiers.
2. Traverse Neo4j for structured facts; validate waiver dates, scope and conditions.
3. Search fare rules, configured policies, historical IROPS reports and PDF chunks.
4. Fuse ranks with sum(1 / (60 + rank)), gate weak semantic matches, deduplicate
   text, and select at most six excerpts within a 6,500-character document budget.
5. Fetch matching PDF graph rules using the retrieved chunk IDs.
6. Return [G#]/[D#] citations, source/page metadata, ranking details and
   live/mock/lexical fallback diagnostics.

The default deterministic agent answers informational questions with evidence
excerpts, without flight searches. Booking proposals also expose supporting evidence.
Optional LLM mode receives the same cited context. Documents are evidence, not
instructions; historical incidents and heuristically extracted PDF amounts do not
override configured compliance rules or prove an active waiver.

This improves grounding and observability, but is **not** proof of perfect retrieval
or hallucination-free hosted generation. Detailed behavior and limitations:
[v2 README](travelsolsv2/README.md).

## Neo4j in brief

Neo4j stores **nodes** for airports, passengers, policies, waivers, fare classes,
document rules and demo bookings, and **relationships** connecting them.
Cypher traverses these relationships for structured facts; ChromaDB separately
handles embedding-based document retrieval. Neo4j is used only in v2.

~~~mermaid
graph LR
    Passenger -->|HAS_POLICY| CorporatePolicy
    Origin["Airport: origin"] -->|ROUTE| Destination["Airport: destination"]
    Origin -->|HAS_WAIVER| Waiver
    PolicyDocument -->|HAS_SECTION| PolicySection
    PolicyDocument -->|CONTAINS_RULE| PolicyRule
    PolicySection -->|HAS_RULE| PolicyRule
    PolicyRule -->|GOVERNS_POLICY| CorporatePolicy
    PolicyRule -->|PERMITS_FARE_CLASS| FareClass
    PolicyRule -->|PREFERRED_AIRLINE| Airline
    EmployeeTier -->|GOVERNED_BY| PolicyRule
~~~

Demo Booking nodes currently store itinerary properties separately. The booking
panel's entity map illustrates inferred links; the policy graph explorer reads
actual database relationships.

Configure travelsolsv2/backend/.env:
~~~env
NEO4J_URI=neo4j+s://YOUR_INSTANCE_ID.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=YOUR_DATABASE_PASSWORD
AGENT_MODE=deterministic
FLIGHT_DATA_MODE=google_flights
ALLOW_MOCK_FLIGHT_FALLBACK=true
~~~

These are database credentials, **not an Aura management API key**. If unavailable,
check the [Aura console](https://console.neo4j.io/) for status and connection URI.
Resume a paused instance or create a replacement for a deleted one.
Free instances can be deleted after remaining paused for more than 30 days.
Save credentials privately, restart v2, and verify /api/health and /api/graph/stats.
New instances receive demo seeds and PDF rules, not deleted booking history.
[Neo4j instance lifecycle documentation](https://neo4j.com/docs/aura/managing-instances/instance-actions/).

## Verification

From travelsolsv2/backend:
~~~powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe tests\smoke_live.py
.\venv\Scripts\python.exe tests\smoke_retrieval_live.py
~~~

The retrieval smoke check requires the running v2 backend, live Neo4j and semantic
Chroma retrieval. It does not book, scrape fares or call hosted inference.
POST /api/retrieval inspects evidence alone.

From travelsols/backend:
~~~powershell
..\venv\Scripts\python.exe -m unittest discover -s tests -v
~~~
From either frontend: npm run build.

## Design references

- [Chroma collection API](https://docs.trychroma.com/reference/python/collection):
  query distances, metadata and document upserts.
- [Reciprocal rank fusion paper](https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/).
- [Neo4j Python query manual](https://neo4j.com/docs/python-manual/current/query-simple/).
