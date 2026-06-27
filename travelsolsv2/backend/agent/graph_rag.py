import re
import logging
from graph.neo4j_client import run_query, get_driver, get_route_info, get_active_waivers, get_corporate_policy
from vector.chroma_client import ChromaClient

logger = logging.getLogger(__name__)

AIRPORTS = ["BOM", "DEL", "BLR", "MAA", "HYD", "DXB", "SIN", "LHR", "JFK", "CDG", "NRT", "BKK", "KUL", "DOH", "SYD"]
AIRLINES = ["AI", "EK", "QR", "SQ", "BA", "6E"]
PASSENGERS = ["Aryan Mehta", "Priya Sharma", "Rajesh Kumar", "Anita Singh", "Vikram Nair"]
FARE_CLASSES = ["Y", "M", "K", "Q", "J", "C", "D", "G"]

def detect_entities(query: str) -> dict:
    query_upper = query.upper()
    entities = {
        "airports": [],
        "airlines": [],
        "passengers": [],
        "policies": [],
        "fare_classes": [],
        "waivers": []
    }
    
    # 1. Detect Airports (3 letter uppercase codes from query, filter with allowed list)
    found_airports = re.findall(r"\b[A-Z]{3}\b", query_upper)
    for code in found_airports:
        if code in AIRPORTS and code not in entities["airports"]:
            entities["airports"].append(code)
            
    # 2. Detect Corporate Policy IDs (CP-001, CP-002, CP-003)
    found_policies = re.findall(r"\bCP-\d{3}\b", query_upper)
    for p_id in found_policies:
        if p_id not in entities["policies"]:
            entities["policies"].append(p_id)
            
    # 3. Detect Airline IATA codes
    words = re.findall(r"\b[A-Z0-9]{2}\b", query_upper)
    for word in words:
        if word in AIRLINES and word not in entities["airlines"]:
            entities["airlines"].append(word)
            
    # 4. Detect Fare Classes (look for standalone letters or expressions like "class Y")
    for fc in FARE_CLASSES:
        # Match "class Y" or "Y class" or "fare class Y" or standalone Y
        pattern = rf"\bclass {fc}\b|\b{fc} class\b|\bfare class {fc}\b"
        if re.search(pattern, query_upper) or (f" {fc} " in f" {query_upper} " and fc not in entities["fare_classes"]):
            if fc not in entities["fare_classes"]:
                entities["fare_classes"].append(fc)
                
    # 5. Detect Passenger Names
    for name in PASSENGERS:
        if name.lower() in query.lower():
            entities["passengers"].append(name)
            
    # Try regex extraction for capitalized words following 'for', 'passenger', or 'traveler'
    match = re.search(r"\b(?:for|passenger|traveler)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", query)
    if match:
        name = match.group(1).strip()
        if name not in entities["passengers"]:
            entities["passengers"].append(name)
            
    # 6. Detect Waivers (like WX-2026-INDIA or OPS-EK-2026-01)
    found_waivers = re.findall(r"\bWX-\d{4}-\w+|\bOPS-\w+-\d{4}-\d+|\bCORP-\w+-\w+|\bEMRG-\d{4}\b", query_upper)
    for w in found_waivers:
        if w not in entities["waivers"]:
            entities["waivers"].append(w)
            
    return entities

def retrieve_context(query: str, passenger_name: str = None) -> dict:
    logger.info(f"Running Hybrid GraphRAG for query: '{query}'")
    entities = detect_entities(query)
    
    # If passenger_name is explicitly provided, ensure it is in entities
    if passenger_name and passenger_name.strip():
        name = passenger_name.strip()
        if name not in entities["passengers"]:
            entities["passengers"].append(name)
            
    logger.info(f"Detected entities: {entities}")
    
    graph_facts = []
    
    # Check if Neo4j is available or in mock mode
    driver = get_driver()
    is_mock = (driver is None)
    
    # STEP 2: Neo4j Traversal (or simulated traversal using mock helpers)
    # A) Passenger Query
    passenger_bands = {
        "Aryan Mehta": 7,
        "Priya Sharma": 4,
        "Rajesh Kumar": 8,
        "Anita Singh": 3,
        "Vikram Nair": 9
    }
    band_match = re.search(r"\b[Bb]and\s*([1-9])\b", query)
    query_band = int(band_match.group(1)) if band_match else None

    for p_name in entities["passengers"]:
        band = query_band if query_band is not None else passenger_bands.get(p_name, 5)
        if not is_mock:
            p_res = run_query(
                """
                MATCH (p:Passenger {name: $name})-[:HAS_POLICY]->(pol:CorporatePolicy)
                RETURN p.name as name, p.tier as tier, pol.id as policy_id, pol.name as policy_name
                """,
                {"name": p_name}
            )
            if p_res:
                r = p_res[0]
                graph_facts.append(f"Passenger {r['name']} holds tier {r['tier']}, is in Band {band}, and is subject to Corporate Policy {r['policy_id']} ({r['policy_name']}).")
        else:
            # Fallback mock fact
            policy_map = {"Aryan Mehta": "CP-001", "Priya Sharma": "CP-001", "Rajesh Kumar": "CP-002", "Anita Singh": "CP-001", "Vikram Nair": "CP-003"}
            tiers = {"Aryan Mehta": "Gold", "Priya Sharma": "Silver", "Rajesh Kumar": "Platinum", "Anita Singh": "Standard", "Vikram Nair": "Executive"}
            p_id = policy_map.get(p_name, "CP-001")
            p_tier = tiers.get(p_name, "Standard")
            graph_facts.append(f"Passenger {p_name} holds tier {p_tier}, is in Band {band}, and is subject to Corporate Policy {p_id}.")
            # Auto-inject the policy id to fetch its rules
            if p_id not in entities["policies"]:
                entities["policies"].append(p_id)

    # B) Policy Query
    for pol_id in entities["policies"]:
        policy = get_corporate_policy(pol_id)
        if policy:
            graph_facts.append(
                f"Corporate Policy {policy.get('id')} ({policy.get('name')}) rules: Allowed Cabins = {policy.get('allowed_cabins')}; "
                f"Allowed Fare Classes = {policy.get('allowed_fare_classes')}; Max Allowable Fare = INR {policy.get('max_fare_inr'):,}; "
                f"Booking window advance days required = {policy.get('min_advance_days')}; Preferred Airlines = {policy.get('preferred_airlines')}; "
                f"Approval required for bookings above INR {policy.get('requires_approval_above_inr'):,}."
            )

    # C) Route Query
    origin = entities["airports"][0] if len(entities["airports"]) > 0 else None
    dest = entities["airports"][1] if len(entities["airports"]) > 1 else None
    
    if origin and dest:
        route_info = get_route_info(origin, dest)
        if route_info:
            graph_facts.append(
                f"Route {origin}-{dest} is operational (distance {route_info.get('distance_km')} km) and is operated by airlines: "
                f"{', '.join(route_info.get('airlines', []))}."
            )
            for w in route_info.get("waivers", []):
                fee_str = "Change fees waived" if w.get("fee_waived") else "Standard change fees apply"
                disc_str = f"Discount of {w['discount_pct']}% applies" if w.get("discount_pct", 0) > 0 else "No additional discount"
                graph_facts.append(
                    f"Active Waiver {w.get('id')} ({w.get('type')}) is active on route {origin}-{dest} until {w.get('valid_until')}. "
                    f"Description: '{w.get('description')}'. Conditions: {fee_str}, {disc_str}."
                )

    # D) Waiver Query (General check by origin if no route was matched yet)
    elif origin:
        waivers = get_active_waivers(origin)
        for w in waivers:
            fee_str = "Change fees waived" if w.get("fee_waived") else "Standard change fees apply"
            graph_facts.append(
                f"Active Waiver {w.get('id')} ({w.get('type')}) is active at origin {origin} until {w.get('valid_until')}. "
                f"Description: '{w.get('description')}'. Conditions: {fee_str}."
            )

    # E) Airline/Fare Classes details query
    for airline in entities["airlines"]:
        if not is_mock:
            air_res = run_query("MATCH (a:Airline {code: $code}) RETURN a.name as name, a.alliance as alliance", {"code": airline})
            if air_res:
                graph_facts.append(f"Airline {airline} is {air_res[0]['name']} and belongs to alliance '{air_res[0]['alliance']}'.")
        else:
            names = {"AI": "Air India (Star Alliance)", "EK": "Emirates (None)", "QR": "Qatar Airways (Oneworld)", "SQ": "Singapore Airlines (Star Alliance)", "BA": "British Airways (Oneworld)", "6E": "IndiGo (None)"}
            graph_facts.append(f"Airline {airline} is {names.get(airline, airline)}.")
            
    for fc in entities["fare_classes"]:
        if not is_mock:
            fc_res = run_query("MATCH (f:FareClass {code: $code}) RETURN f.name as name, f.change_fee_inr as fee, f.refund_pct as refund", {"code": fc})
            if fc_res:
                graph_facts.append(f"Fare Class {fc} ({fc_res[0]['name']}) details: Change fee = INR {fc_res[0]['fee']:,}; Refund = {fc_res[0]['refund']}% of base fare.")
        else:
            fees = {"Y": 8000, "M": 5000, "K": 3000, "Q": 999999, "J": 0, "C": 15000, "D": 25000, "G": 10000}
            refunds = {"Y": 75, "M": 50, "K": 0, "Q": 0, "J": 100, "C": 80, "D": 0, "G": 25}
            names = {"Y": "Full Economy", "M": "Semi-restricted economy", "K": "Restricted economy", "Q": "Deep discount", "J": "Full Business", "C": "Semi-restricted business", "D": "Discounted business", "G": "Group fare"}
            graph_facts.append(f"Fare Class {fc} ({names.get(fc)}) details: Change fee = INR {fees.get(fc, 0):,}; Refund = {refunds.get(fc, 0)}% of base fare.")

    # E-2) PDF Policy Document nodes from Neo4j (if ingested)
    policy_keywords = ["policy", "rule", "compliance", "approval", "travel", "booking", "advance", "cabin", "fare"]
    if any(kw in query.lower() for kw in policy_keywords):
        try:
            if not is_mock:
                pdf_rules = run_query(
                    """
                    MATCH (d:PolicyDocument)-[:CONTAINS_RULE]->(r:PolicyRule)
                    WHERE r.snippet CONTAINS $kw OR r.max_fare_inr IS NOT NULL
                    RETURN d.name as doc, r.snippet as snippet, r.max_fare_inr as max_fare,
                           r.min_advance_days as advance, r.requires_approval as approval,
                           r.allowed_cabins as cabins, r.allowed_fare_classes as fare_classes
                    LIMIT 5
                    """,
                    {"kw": query[:40]}
                )
                for row in pdf_rules:
                    fact = f"[PDF: {row.get('doc')}] Policy rule: {row.get('snippet', '')[:200]}"
                    if row.get('max_fare_inr'):
                        fact += f" | Max Fare: INR {row['max_fare_inr']:,}"
                    if row.get('min_advance_days') is not None:
                        fact += f" | Min Advance: {row['min_advance_days']} days"
                    if row.get('requires_approval'):
                        fact += " | Requires Approval: Yes"
                    graph_facts.append(fact)
        except Exception as e:
            logger.warning(f"PolicyRule Neo4j query failed: {e}")

    # STEP 3: ChromaDB Semantic Search (retrieve n_results=3 from all collections)
    chroma = ChromaClient()
    semantic_chunks = []
    
    collections = ["fare_rules", "corporate_policies", "irops_history", "policy_documents"]
    labels = {
        "fare_rules": "FARE RULE",
        "corporate_policies": "POLICY",
        "irops_history": "IROPS",
        "policy_documents": "PDF POLICY"
    }
    
    for col_name in collections:
        try:
            results = chroma.query(col_name, query, n_results=3)
            for item in results:
                semantic_chunks.append({
                    "source": labels[col_name],
                    "id": item["id"],
                    "document": item["document"],
                    "metadata": item["metadata"]
                })
        except Exception as e:
            logger.error(f"Error querying Chroma collection '{col_name}': {e}")
            
    # STEP 4: Format combined context for the LLM
    facts_str = "\n".join([f"- {fact}" for fact in graph_facts]) if graph_facts else "- No specific knowledge graph facts retrieved."
    
    chunks_list = []
    for chunk in semantic_chunks:
        chunks_list.append(f"[{chunk['source']}] (ID: {chunk['id']})\n{chunk['document']}")
    chunks_str = "\n\n".join(chunks_list) if chunks_list else "No relevant document chunks retrieved."
    
    combined_context = (
        f"KNOWLEDGE GRAPH FACTS:\n{facts_str}\n\n"
        f"RELEVANT DOCUMENTS:\n{chunks_str}"
    )
    
    return {
        "graph_facts": graph_facts,
        "semantic_chunks": semantic_chunks,
        "combined_context": combined_context,
        "entities": entities
    }
