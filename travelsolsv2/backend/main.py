import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Setup logging FIRST before any package imports that might log
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import packages — these are now all import-safe with try/except internally
from graph.neo4j_client import close_driver, get_driver, run_query, get_route_info, get_active_waivers
from graph.schema_init import initialize_schema
from vector.chroma_client import ChromaClient
from vector.document_loader import load_documents
from agent.booking_agent import run_booking_agent
from scheduler import (
    start_scheduler,
    stop_scheduler,
    get_cached_forecasts,
    get_single_forecast,
    FORECAST_CACHE,
    LAST_REFRESH,
    run_pipeline
)
from graph.pdf_ingestor import ingest_pdf

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Initializing TravelRoute unified Backend...")
    
    # 1. Initialize Neo4j Schema & Seed Data
    try:
        initialize_schema()
    except Exception as e:
        logger.error(f"Failed to initialize Neo4j schema on startup: {e}")
        
    # 2. Seed Vector Database documents in Chroma
    try:
        load_documents()
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB collections on startup: {e}")
        
    # 3. Start forecasting scheduler
    try:
        start_scheduler()
    except Exception as e:
        logger.error(f"Failed to start forecasting scheduler: {e}")

    # 4. Ingest corporate policy PDF (if present)
    _PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "corporate_travel_policy.pdf")
    _PDF_PATH = os.path.normpath(_PDF_PATH)
    if os.path.exists(_PDF_PATH):
        try:
            logger.info(f"Ingesting corporate policy PDF: {_PDF_PATH}")
            summary = ingest_pdf(_PDF_PATH)
            logger.info(f"PDF ingestion complete: {summary['chunks']} chunks, neo4j={summary['neo4j_written']}, chroma={summary['chroma_indexed']}")
        except Exception as e:
            logger.error(f"PDF ingestion failed on startup: {e}")
    else:
        logger.warning(f"Corporate policy PDF not found at {_PDF_PATH} — skipping auto-ingest.")

    logger.info("TravelRoute unified Backend startup complete!")
    yield
    # Shutdown actions
    logger.info("Tearing down sessions and scheduler...")
    close_driver()
    try:
        stop_scheduler()
    except Exception as e:
        logger.error(f"Failed to stop forecasting scheduler: {e}")


app = FastAPI(
    title="TravelRoute Intelligence v2 Agent API",
    description="Agentic booking layer with GraphRAG (Neo4j + ChromaDB)",
    version="2.0.0",
    lifespan=lifespan
)

# CORS — allow both dev server ports (5173 for v1, 5174 for v2)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentRequest(BaseModel):
    query: str
    passenger_id: str = None

@app.post("/api/agent/run")
async def run_agent(body: AgentRequest):
    if not body.query:
        raise HTTPException(status_code=400, detail="Query string cannot be empty")
    try:
        logger.info(f"Received agent run query: '{body.query}' for passenger: '{body.passenger_id}'")
        result = run_booking_agent(body.query, body.passenger_id)
        return result
    except Exception as e:
        logger.exception("Error executing agent query")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Policy Document Endpoints
# ---------------------------------------------------------------------------

class PolicyIngestRequest(BaseModel):
    pdf_path: str = None  # optional override; defaults to the project PDF

@app.post("/api/policy/ingest")
def api_ingest_policy(body: PolicyIngestRequest = None, background_tasks: BackgroundTasks = None):
    """Re-ingest the corporate policy PDF into ChromaDB + Neo4j."""
    _PDF_PATH = os.path.normpath(
        (body.pdf_path if body and body.pdf_path else None)
        or os.path.join(os.path.dirname(__file__), "..", "..", "corporate_travel_policy.pdf")
    )
    if not os.path.exists(_PDF_PATH):
        raise HTTPException(status_code=404, detail=f"PDF not found at: {_PDF_PATH}")
    try:
        summary = ingest_pdf(_PDF_PATH)
        return {"status": "ok", "summary": summary}
    except Exception as e:
        logger.exception("PDF ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/policy/search")
def api_search_policy(q: str = Query(..., description="Natural language policy query"), n: int = 4):
    """Semantic search over ingested policy chunks."""
    try:
        from vector.chroma_client import ChromaClient
        client = ChromaClient()
        results = client.query("policy_documents", q, n_results=n)
        return {"query": q, "results": results}
    except Exception as e:
        logger.exception("Policy search failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/policy/graph")
def api_policy_graph():
    """
    Returns the full PDF policy knowledge graph as {nodes, links}
    for force-directed visualisation on the frontend.
    """
    try:
        nodes_map = {}
        links = []

        def add_node(nid, label, node_type, props=None):
            if nid and nid not in nodes_map:
                nodes_map[nid] = {"id": nid, "label": label, "type": node_type, "props": props or {}}

        def add_link(source, target, rel):
            if source and target:
                links.append({"source": source, "target": target, "label": rel})

        # 1. PolicyDocument → PolicySection
        doc_sec = run_query("""
            MATCH (d:PolicyDocument)-[:HAS_SECTION]->(s:PolicySection)
            RETURN d.name as doc, s.id as sec_id, s.title as sec_title
        """)
        for r in doc_sec:
            add_node(r["doc"], r["doc"].replace("_", " ").title(), "document", {"source": "PDF"})
            add_node(r["sec_id"], r["sec_title"][:28], "section", {"title": r["sec_title"]})
            add_link(r["doc"], r["sec_id"], "HAS_SECTION")

        # 2. PolicyDocument → PolicyRule
        doc_rules = run_query("""
            MATCH (d:PolicyDocument)-[:CONTAINS_RULE]->(r:PolicyRule)
            RETURN d.name as doc, r.id as rule_id, r.snippet as snippet,
                   r.max_fare_inr as max_fare, r.requires_approval as req_approval,
                   r.page as page
            LIMIT 80
        """)
        for r in doc_rules:
            snippet = (r.get("snippet") or "")[:32]
            add_node(r["doc"], r["doc"].replace("_", " ").title(), "document")
            add_node(r["rule_id"], f"Rule p.{r.get('page',0)}", "rule", {
                "snippet": r.get("snippet", "")[:120],
                "max_fare_inr": r.get("max_fare"),
                "requires_approval": r.get("req_approval")
            })
            add_link(r["doc"], r["rule_id"], "CONTAINS_RULE")

        # 3. PolicyRule → CorporatePolicy
        rule_pol = run_query("""
            MATCH (r:PolicyRule)-[:GOVERNS_POLICY]->(p:CorporatePolicy)
            RETURN r.id as rule_id, p.id as pol_id, p.name as pol_name
        """)
        for r in rule_pol:
            add_node(r["pol_id"], r["pol_id"], "policy", {"name": r.get("pol_name","")})
            add_link(r["rule_id"], r["pol_id"], "GOVERNS_POLICY")

        # 4. PolicyRule → FareClass
        rule_fc = run_query("""
            MATCH (r:PolicyRule)-[:PERMITS_FARE_CLASS]->(f:FareClass)
            RETURN r.id as rule_id, f.code as code, f.name as name
        """)
        for r in rule_fc:
            add_node(r["code"], f"Class {r['code']}", "fareclass", {"name": r.get("name","")})
            add_link(r["rule_id"], r["code"], "PERMITS_FARE_CLASS")

        # 5. PolicyRule → Airline
        rule_airline = run_query("""
            MATCH (r:PolicyRule)-[:PREFERRED_AIRLINE]->(a:Airline)
            RETURN r.id as rule_id, a.code as code, a.name as name
        """)
        for r in rule_airline:
            add_node(r["code"], r.get("name", r["code"]), "airline", {"code": r["code"]})
            add_link(r["rule_id"], r["code"], "PREFERRED_AIRLINE")

        # 6. EmployeeTier → PolicyRule
        tier_rule = run_query("""
            MATCH (t:EmployeeTier)-[:GOVERNED_BY]->(r:PolicyRule)
            RETURN t.id as tid, t.name as tname, r.id as rule_id
        """)
        for r in tier_rule:
            add_node(r["tid"], r.get("tname", r["tid"]), "tier", {})
            add_link(r["tid"], r["rule_id"], "GOVERNED_BY")

        # 7. Seed: CorporatePolicy → FareClass (allowed_fare_classes)
        cp_nodes = run_query("MATCH (p:CorporatePolicy) RETURN p.id as id, p.name as name, p.allowed_fare_classes as afc, p.max_fare_inr as max_fare")
        for r in cp_nodes:
            add_node(r["id"], r["id"], "policy", {"name": r.get("name",""), "max_fare_inr": r.get("max_fare")})

        return {
            "nodes": list(nodes_map.values()),
            "links": links,
            "stats": {
                "node_count": len(nodes_map),
                "link_count": len(links)
            }
        }
    except Exception as e:
        logger.exception("Policy graph query failed")
        raise HTTPException(status_code=500, detail=str(e))


class BookingRequest(BaseModel):
    passenger_name: str
    flight_number: str
    origin: str
    destination: str
    date: str
    fare_class: str
    price: int

@app.post("/api/booking/create")
def api_create_booking(body: BookingRequest):
    try:
        from travel.pnr_builder import create_pnr_api
        from graph.neo4j_client import write_booking
        
        logger.info(f"Creating booking PNR for passenger: {body.passenger_name}")
        # Create PNR via Travel / mock Travel
        booking_res = create_pnr_api(
            body.passenger_name,
            body.flight_number,
            body.origin,
            body.destination,
            body.date,
            body.fare_class,
            body.price
        )
        
        # Save node in Graph Database
        write_booking(booking_res)
        
        return booking_res
    except Exception as e:
        logger.exception("Failed to create PNR booking node")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/booking/history")
def get_booking_history():
    try:
        logger.info("Fetching booking logs from Neo4j...")
        # Query bookings sorted by creation time
        q = """
        MATCH (b:Booking)
        RETURN b
        ORDER BY b.created_at DESC
        """
        results = run_query(q)
        bookings = []
        for r in results:
            b_node = r.get("b")
            if b_node:
                bookings.append(b_node)
                
        # Fallback to realistic mock bookings if empty
        if not bookings:
            bookings = [
                {
                    "pnr": "JK992A",
                    "passenger_name": "Aryan Mehta",
                    "flight_number": "AI-101",
                    "origin": "BOM",
                    "destination": "DXB",
                    "date": "2026-06-25",
                    "fare_class": "Y",
                    "price_inr": 28500,
                    "created_at": 1782298000
                },
                {
                    "pnr": "QW004P",
                    "passenger_name": "Anita Singh",
                    "flight_number": "EK-506",
                    "origin": "BOM",
                    "destination": "DXB",
                    "date": "2026-06-27",
                    "fare_class": "Y",
                    "price_inr": 34100,
                    "created_at": 1782299000
                }
            ]
        return bookings
    except Exception as e:
        logger.exception("Failed to retrieve booking history from Neo4j")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/route/{origin}/{dest}")
def api_route_info(origin: str, dest: str):
    try:
        return get_route_info(origin, dest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/graph/waivers/{origin}")
def api_waiver_info(origin: str):
    try:
        return get_active_waivers(origin)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/graph/stats")
def api_graph_stats():
    driver = get_driver()
    if driver is None:
        return {
            "airports": 15,
            "routes": 20,
            "bookings": 3,
            "waivers": 4,
            "policies": 3,
            "passengers": 5,
            "db_mode": "MOCK"
        }
    try:
        airports = run_query("MATCH (a:Airport) RETURN count(a) as cnt")[0].get("cnt", 0)
        routes = run_query("MATCH ()-[r:ROUTE]->() RETURN count(r) as cnt")[0].get("cnt", 0)
        bookings = run_query("MATCH (b:Booking) RETURN count(b) as cnt")[0].get("cnt", 0)
        waivers = run_query("MATCH (w:Waiver) RETURN count(w) as cnt")[0].get("cnt", 0)
        policies = run_query("MATCH (p:CorporatePolicy) RETURN count(p) as cnt")[0].get("cnt", 0)
        passengers = run_query("MATCH (p:Passenger) RETURN count(p) as cnt")[0].get("cnt", 0)
        
        return {
            "airports": airports,
            "routes": routes,
            "bookings": bookings,
            "waivers": waivers,
            "policies": policies,
            "passengers": passengers,
            "db_mode": "LIVE"
        }
    except Exception as e:
        logger.error(f"Failed to query database stats: {e}")
        return {
            "airports": 15,
            "routes": 20,
            "bookings": 0,
            "waivers": 4,
            "policies": 3,
            "passengers": 5,
            "db_mode": "LIVE_FALLBACK_MOCK"
        }

@app.get("/api/vector/search")
def api_vector_search(q: str = Query(..., description="Query text to search vector DB")):
    try:
        chroma = ChromaClient()
        results = {}
        for col in ["fare_rules", "corporate_policies", "irops_history"]:
            results[col] = chroma.query(col, q, n_results=3)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CypherQueryRequest(BaseModel):
    query: str

@app.post("/api/graph/query")
def api_run_cypher(body: CypherQueryRequest):
    try:
        from graph.neo4j_client import run_query
        logger.info(f"Running custom Cypher query: {body.query}")
        results = run_query(body.query)
        return {"status": "success", "results": results}
    except Exception as e:
        logger.exception("Cypher query execution failed")
        raise HTTPException(status_code=500, detail=str(e))

class NLQueryRequest(BaseModel):
    question: str
    api_key: str = None

@app.post("/api/graph/query/nl")
def api_run_nl_query(body: NLQueryRequest):
    try:
        from graph.neo4j_client import run_query
        import json
        import re
        import httpx
        
        # Check for Gemini key in request or env
        gemini_key = body.api_key or os.getenv("GEMINI_API_KEY")
        use_gemini = bool(gemini_key)
        
        cypher_query = ""
        answer = ""
        results = []
        
        # 1. Introspect schema from live Neo4j database
        try:
            rel_res = run_query("CALL db.relationshipTypes()")
            rels = [list(r.values())[0] for r in rel_res if r]
            schema_str = (
                "Neo4j Schema and Properties:\n"
                "- Node 'Airport' properties: code, name, city\n"
                "- Node 'Airline' properties: code, name, alliance\n"
                "- Node 'Passenger' properties: id, name, tier, policy_id\n"
                "- Node 'CorporatePolicy' properties: id, name, allowed_cabins, allowed_fare_classes, max_fare_inr, min_advance_days, preferred_airlines, requires_approval_above_inr\n"
                "- Node 'Waiver' properties: id, type, description, valid_until, origin_codes, fee_waived, discount_pct\n"
                "- Node 'Booking' properties: pnr, passenger_name, flight_number, origin, destination, date, fare_class, price_inr\n"
                "- Node 'PolicyDocument' properties: name\n"
                "- Node 'PolicySection' properties: id, title, document\n"
                "- Node 'PolicyRule' properties: id, snippet, page, chunk_index, max_fare_inr, min_advance_days, requires_approval, allowed_cabins, allowed_fare_classes, document\n"
                "- Node 'EmployeeTier' properties: id, name\n"
                f"- Relationship Types: {', '.join(rels)}"
            )
        except Exception as schema_err:
            logger.error(f"Failed to fetch live schema: {schema_err}")
            schema_str = (
                "Node Labels: Airport, Airline, CorporatePolicy, Passenger, Waiver, PolicyDocument, PolicySection, PolicyRule. "
                "Relationship Types: ROUTE, HAS_POLICY, HAS_WAIVER, HAS_SECTION, CONTAINS_RULE, GOVERNS_POLICY, PERMITS_FARE_CLASS."
            )

        # 2. Call the new Gemma model to generate Cypher query
        try:
            from cypher_generator import generate_cypher
            cypher_query = generate_cypher(body.question, schema_str)
        except Exception as hf_err:
            logger.error(f"Gemma Cypher generation failed: {hf_err}")
            cypher_query = ""
        
        # Rule-based fallback if LLM is unavailable or translation was empty
        if not cypher_query:
            q = body.question.lower()
            section_match = re.search(r"sec(?:tion)?\s*(\d+(?:\.\d+)?)", q)
            if section_match:
                sec_num = section_match.group(1)
                cypher_query = (
                    f"MATCH (s:PolicySection) "
                    f"WHERE s.title STARTS WITH '{sec_num}' "
                    f"OPTIONAL MATCH (s)-[:HAS_RULE]->(r:PolicyRule) "
                    f"RETURN s.title AS SectionTitle, COALESCE(r.snippet, s.title) AS PolicySnippet, COALESCE(r.page, 0) AS PageNumber LIMIT 5"
                )
            else:
                stopwords = {"what", "is", "the", "rule", "for", "explain", "about", "policy", "document", "in", "on", "of", "and", "to", "a", "from", "any", "kind", "must", "show", "get"}
                words = [w.strip() for w in re.split(r'\W+', q) if w.strip() and w.strip() not in stopwords]
                
                if "waiver" in q or "weather" in q or "monsoon" in q or "smog" in q:
                    cypher_query = "MATCH (w:Waiver) RETURN w LIMIT 5"
                elif "passenger" in q or "who is" in q or "grade" in q:
                    cypher_query = "MATCH (p:Passenger)-[r:HAS_POLICY]->(pol) RETURN p, r, pol"
                elif words:
                    conditions = []
                    for w in words[:4]:
                        conditions.append(f"toLower(s.title) CONTAINS '{w}'")
                        conditions.append(f"toLower(s.snippet) CONTAINS '{w}'")
                    cypher_query = (
                        "MATCH (s) "
                        f"WHERE {' OR '.join(conditions)} "
                        "RETURN s.title AS SectionTitle, s.snippet AS PolicySnippet, s.page AS PageNumber LIMIT 5"
                    )
                else:
                    cypher_query = "MATCH (n) RETURN n LIMIT 10"
                
        results = run_query(cypher_query)
        
        # Dual-layer safety: if the generated query returns 0 records, use our keyword-based database search
        if not results:
            q = body.question.lower()
            fallback_query = ""
            section_match = re.search(r"sec(?:tion)?\s*(\d+(?:\.\d+)?)", q)
            if section_match:
                sec_num = section_match.group(1)
                fallback_query = (
                    f"MATCH (s:PolicySection) "
                    f"WHERE s.title STARTS WITH '{sec_num}' "
                    f"OPTIONAL MATCH (s)-[:HAS_RULE]->(r:PolicyRule) "
                    f"RETURN s.title AS SectionTitle, COALESCE(r.snippet, s.title) AS PolicySnippet, COALESCE(r.page, 0) AS PageNumber LIMIT 5"
                )
            else:
                stopwords = {"what", "is", "the", "rule", "for", "explain", "about", "policy", "document", "in", "on", "of", "and", "to", "a", "from", "any", "kind", "must", "show", "get"}
                words = [w.strip() for w in re.split(r'\W+', q) if w.strip() and w.strip() not in stopwords]
                if words:
                    conditions = []
                    for w in words[:4]:
                        conditions.append(f"toLower(s.title) CONTAINS '{w}'")
                        conditions.append(f"toLower(s.snippet) CONTAINS '{w}'")
                    fallback_query = (
                        "MATCH (s) "
                        f"WHERE {' OR '.join(conditions)} "
                        "RETURN s.title AS SectionTitle, s.snippet AS PolicySnippet, s.page AS PageNumber LIMIT 5"
                    )
            if fallback_query:
                logger.info(f"LLM query returned 0 records. Activating fallback query lookup: {fallback_query}")
                cypher_query = fallback_query
                results = run_query(cypher_query)
        
        # 2. Synthesize answer using LLM
        summary_prompt = (
            f"You are a Neo4j travel data analyst. Based on this question and the database query results, write a concise natural language answer.\n"
            f"Question: \"{body.question}\"\n"
            f"Cypher Query Used: \"{cypher_query}\"\n"
            f"Database Results:\n{json.dumps(results[:15], indent=2)}\n\n"
            f"Instructions:\n"
            f"1. Give a direct answer to the user's question.\n"
            f"2. Format your answer as a short paragraph followed by a clear bulleted list if there are multiple items.\n"
            f"3. Do NOT output raw JSON or raw Cypher queries.\n"
            f"Answer:"
        )
        
        if use_gemini:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{
                        "parts": [{"text": summary_prompt}]
                    }]
                }
                with httpx.Client(timeout=20.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                logger.error(f"Gemini synthesis failed: {e}")
        else:
            api_key = os.getenv("HUGGINGFACE_API_KEY")
            if api_key:
                try:
                    from openai import OpenAI
                    logger.info("Synthesizing natural response using Qwen/Qwen2.5-7B-Instruct...")
                    client = OpenAI(
                        base_url="https://router.huggingface.co/v1",
                        api_key=api_key
                    )
                    completion = client.chat.completions.create(
                        model="Qwen/Qwen2.5-7B-Instruct",
                        messages=[
                            {"role": "user", "content": summary_prompt}
                        ],
                        max_tokens=400,
                        temperature=0.3
                    )
                    answer = completion.choices[0].message.content.strip()
                except Exception as e:
                    logger.error(f"Qwen synthesis failed: {e}")
            
            if not answer:
                from agent.booking_agent import _llm
                if _llm:
                    try:
                        logger.info("Qwen failed or not available. Falling back to default Llama model...")
                        ans_res = _llm.invoke(summary_prompt)
                        answer = ans_res.content.strip()
                    except Exception as e:
                        logger.error(f"Fallback LLM synthesis failed: {e}")
                
        if not answer:
            answer = f"Found {len(results)} records matching your query."
            
        return {
            "status": "success",
            "cypher": cypher_query,
            "results": results,
            "answer": answer
        }
    except Exception as e:
        logger.exception("Natural language graph query failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def api_health():
    # 1. Neo4j Status
    neo4j_ok = (get_driver() is not None)
    
    # 2. Chroma Status
    chroma_counts = {}
    try:
        chroma = ChromaClient()
        for col in ["fare_rules", "corporate_policies", "irops_history"]:
            c = chroma.get_or_create_collection(col)
            chroma_counts[col] = c.count()
    except Exception as e:
        chroma_counts = {"error": str(e)}
        
    # 3. HF Model Connection Status
    hf_ok = False
    if HUGGINGFACE_API_KEY and HUGGINGFACE_API_KEY != "your_huggingface_api_key_here":
        try:
            from agent.booking_agent import _llm
            hf_ok = (_llm is not None)
        except Exception:
            hf_ok = False
        
    return {
        "status": "ok",
        "neo4j": neo4j_ok,
        "chroma": chroma_counts,
        "huggingface": hf_ok,
        "chronos_model": "chronos-bolt-small",
        "forecast_cache_size": len(FORECAST_CACHE),
        "last_forecast_refresh": LAST_REFRESH.isoformat() if LAST_REFRESH else None
    }

@app.get("/api/origins")
def get_origins():
    return [
        {"code": "BOM", "name": "Mumbai"},
        {"code": "DEL", "name": "Delhi"},
        {"code": "BLR", "name": "Bengaluru"},
        {"code": "MAA", "name": "Chennai"},
        {"code": "HYD", "name": "Hyderabad"}
    ]

@app.get("/api/forecasts")
def list_forecasts(origin: str = "BOM", limit: int = 20):
    try:
        results = get_cached_forecasts(origin)
        return results[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/forecast/{origin}/{dest}")
def single_forecast(origin: str, dest: str):
    try:
        data = get_single_forecast(origin, dest)
        if not data:
            raise HTTPException(status_code=404, detail="Route not found")
            
        trend_word = "present" if data["trend_score"] > 0 else "absent"
        diff_pct = data["momentum_pct"]
        travel_diff = data["travel_rank_2w"] - data["travel_rank_12w"]
        travel_dir = "up" if travel_diff < 0 else "down" # lower rank is better
        gds_momentum = abs(int(((data["travel_rank_12w"] - data["travel_rank_2w"]) / 50.0) * 100))
        
        explanation = (
            f"Travel GDS demand {travel_dir} {gds_momentum}% in last 2 weeks. "
            f"Google Trends signal {trend_word}. "
            f"Destination weather score {data['weather_score']}. "
            f"Chronos model forecasts {data['trend']} demand over next 30 days."
        )
        data["signal_explanation"] = explanation
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/refresh")
def refresh_data(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(run_pipeline)
        return {"status": "refreshing", "eta_seconds": 30}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

