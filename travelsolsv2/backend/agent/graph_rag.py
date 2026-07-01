import re
import logging
from graph.neo4j_client import run_query, get_driver, get_route_info, get_active_waivers, get_corporate_policy
from vector.chroma_client import ChromaClient

logger = logging.getLogger(__name__)

AIRPORTS = [
    "BOM", "DEL", "BLR", "MAA", "HYD", "DXB", "SIN", "LHR", "JFK", "CDG", "NRT", "BKK", "KUL", "DOH", "SYD",
    "FRA", "AMS", "ORD", "LAX", "DFW", "SFO", "HKG", "ICN", "FCO", "ZRH", "VIE", "MUC", "CPH", "ARN", "IST",
    "CAI", "NBO", "JNB", "CMB", "DAC", "KTM", "PEK", "PVG", "CAN", "RGN", "SGN", "HAN", "CGK", "MNL", "KIX",
    "NGO", "CTS", "MEL", "BNE", "AKL", "PER", "YYZ", "JED"
]
AIRLINES = ["AI", "EK", "QR", "SQ", "BA", "6E"]
PASSENGERS = ["Aryan Mehta", "Priya Sharma", "Rajesh Kumar", "Anita Singh", "Vikram Nair"]
FARE_CLASSES = ["Y", "M", "K", "Q", "J", "C", "D", "G"]

CITY_TO_AIRPORT = {
    "mumbai": "BOM", "bombay": "BOM",
    "delhi": "DEL", "new delhi": "DEL",
    "bangalore": "BLR", "bengaluru": "BLR",
    "chennai": "MAA", "madras": "MAA",
    "hyderabad": "HYD",
    "dubai": "DXB",
    "singapore": "SIN",
    "london": "LHR", "heathrow": "LHR",
    "new york": "JFK", "jfk": "JFK",
    "paris": "CDG", "charles de gaulle": "CDG",
    "tokyo": "NRT", "narita": "NRT",
    "bangkok": "BKK", "suvarnabhumi": "BKK",
    "kuala lumpur": "KUL",
    "doha": "DOH",
    "sydney": "SYD",
    "frankfurt": "FRA",
    "amsterdam": "AMS",
    "chicago": "ORD",
    "los angeles": "LAX",
    "dallas": "DFW",
    "san francisco": "SFO",
    "hong kong": "HKG",
    "seoul": "ICN", "incheon": "ICN",
    "rome": "FCO",
    "zurich": "ZRH",
    "vienna": "VIE",
    "munich": "MUC",
    "copenhagen": "CPH",
    "stockholm": "ARN",
    "istanbul": "IST",
    "cairo": "CAI",
    "nairobi": "NBO",
    "johannesburg": "JNB",
    "colombo": "CMB",
    "dhaka": "DAC",
    "kathmandu": "KTM",
    "beijing": "PEK",
    "shanghai": "PVG",
    "guangzhou": "CAN",
    "yangon": "RGN",
    "ho chi minh": "SGN", "saigon": "SGN",
    "hanoi": "HAN",
    "jakarta": "CGK",
    "manila": "MNL",
    "osaka": "KIX",
    "nagoya": "NGO",
    "sapporo": "CTS",
    "melbourne": "MEL",
    "brisbane": "BNE",
    "auckland": "AKL",
    "perth": "PER",
    "toronto": "YYZ",
    "jeddah": "JED"
}

def extract_entities_with_llm(query: str) -> dict:
    import os
    import json
    from langchain_openai import ChatOpenAI
    
    hf_key = os.getenv("HUGGINGFACE_API_KEY")
    if not hf_key or hf_key == "your_huggingface_api_key_here":
        logger.info("HF API key not configured or placeholder. Skipping LLM entity extraction.")
        return {}
        
    try:
        logger.info("Calling Hugging Face LLM for semantic entity extraction...")
        llm = ChatOpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=hf_key,
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            max_tokens=150,
            temperature=0.0,
            timeout=8
        )
        
        prompt = (
            "You are a travel entity extractor. Extract the booking parameters from the user's natural language query.\n"
            "Map city names and airports to their corresponding 3-letter IATA codes (e.g. London -> LHR, Mumbai -> BOM, Bangalore/Bengaluru -> BLR).\n"
            "Return ONLY a valid JSON object. Do not include markdown formatting or explanations.\n"
            "Format:\n"
            "{\n"
            "  \"origin\": \"3-letter IATA code or null\",\n"
            "  \"destination\": \"3-letter IATA code or null\",\n"
            "  \"passenger\": \"name or null\",\n"
            "  \"band\": integer 1-9 or null\n"
            "}\n\n"
            f"Query: \"{query}\"\n"
            "JSON:"
        )
        
        res = llm.invoke(prompt)
        clean_response = res.content.strip()
        if clean_response.startswith("```"):
            clean_response = clean_response.split("```")[1]
            if clean_response.startswith("json"):
                clean_response = clean_response[4:]
        
        data = json.loads(clean_response)
        logger.info(f"LLM entity extraction successful: {data}")
        return data
    except Exception as e:
        logger.warning(f"LLM entity extraction failed: {e}. Falling back to local parser.")
        return {}

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
    
    # 1. Try LLM semantic extraction first
    llm_entities = extract_entities_with_llm(query)
    llm_origin = None
    llm_dest = None
    if llm_entities:
        llm_origin = llm_entities.get("origin")
        llm_dest = llm_entities.get("destination")
        psg = llm_entities.get("passenger")
        if psg:
            entities["passengers"].append(psg)
            
    # 2. Robust positional/directional local identification
    origin_code = llm_origin.upper() if (llm_origin and llm_origin.upper() in AIRPORTS) else None
    dest_code = llm_dest.upper() if (llm_dest and llm_dest.upper() in AIRPORTS) else None
    
    # If LLM didn't extract both, or to ensure robust fallback when typing, use local positional parser
    if not (origin_code and dest_code):
        query_lower = query.lower()
        matches = []
        
        # 2a. Find city name matches (from CITY_TO_AIRPORT mapping)
        for city, code in CITY_TO_AIRPORT.items():
            pattern = rf"\b{re.escape(city.lower())}\b"
            for m in re.finditer(pattern, query_lower):
                matches.append({
                    "code": code,
                    "start": m.start(),
                    "end": m.end(),
                    "text": m.group(0)
                })
                
        # 2b. Find IATA code matches (3-letter uppercase codes)
        for code in AIRPORTS:
            pattern = rf"\b{re.escape(code)}\b"
            for m in re.finditer(pattern, query_upper):
                matches.append({
                    "code": code,
                    "start": m.start(),
                    "end": m.end(),
                    "text": m.group(0)
                })
                
        # Deduplicate overlapping matches (e.g. "BOM" and "mumbai" at same place, keep longer span)
        matches.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
        deduped = []
        last_end = -1
        for m in matches:
            if m["start"] >= last_end:
                deduped.append(m)
                last_end = m["end"]
                
        # Select first 2 unique matched airports to classify
        unique_matches = []
        seen_codes = set()
        for m in deduped:
            if m["code"] not in seen_codes:
                unique_matches.append(m)
                seen_codes.add(m["code"])
                if len(unique_matches) == 2:
                    break
                    
        # Define positional/directional indicator keywords
        ORIGIN_KEYWORDS = ["from", "departing", "depart", "departs", "departure", "origin", "source", "out of", "leaving", "flying from", "start", "starting"]
        DEST_KEYWORDS = ["to", "arriving", "arrive", "arrives", "arrival", "destination", "dest", "going to", "towards", "bound for", "flying to", "flight to"]
        
        def get_closest_indicator(preceding_text: str):
            indicators = []
            for keyword in ORIGIN_KEYWORDS:
                for match in re.finditer(rf"\b{re.escape(keyword)}\b", preceding_text):
                    indicators.append(("origin", match.start()))
            for keyword in DEST_KEYWORDS:
                for match in re.finditer(rf"\b{re.escape(keyword)}\b", preceding_text):
                    indicators.append(("dest", match.start()))
            if not indicators:
                return None
            indicators.sort(key=lambda x: x[1], reverse=True)
            return indicators[0][0]
            
        local_origin = None
        local_dest = None
        
        if len(unique_matches) == 2:
            roles = []
            for m in unique_matches:
                preceding = query_lower[:m["start"]]
                roles.append(get_closest_indicator(preceding))
                
            # Classify based on directional indicators
            if roles[0] == "origin" and roles[1] == "dest":
                local_origin = unique_matches[0]["code"]
                local_dest = unique_matches[1]["code"]
            elif roles[0] == "dest" and roles[1] == "origin":
                local_origin = unique_matches[1]["code"]
                local_dest = unique_matches[0]["code"]
            elif roles[0] == "origin" and roles[1] is None:
                local_origin = unique_matches[0]["code"]
                local_dest = unique_matches[1]["code"]
            elif roles[0] is None and roles[1] == "dest":
                local_origin = unique_matches[0]["code"]
                local_dest = unique_matches[1]["code"]
            elif roles[0] == "dest" and roles[1] is None:
                local_origin = unique_matches[1]["code"]
                local_dest = unique_matches[0]["code"]
            elif roles[0] is None and roles[1] == "origin":
                local_origin = unique_matches[1]["code"]
                local_dest = unique_matches[0]["code"]
            else:
                # Default order of appearance in query
                local_origin = unique_matches[0]["code"]
                local_dest = unique_matches[1]["code"]
        elif len(unique_matches) == 1:
            m = unique_matches[0]
            preceding = query_lower[:m["start"]]
            role = get_closest_indicator(preceding)
            if role == "dest":
                local_dest = m["code"]
            else:
                local_origin = m["code"]
                
        # Merge local extraction with LLM results
        if not origin_code:
            origin_code = local_origin
        if not dest_code:
            dest_code = local_dest
            
    # Set final airports array: origin first, then destination
    if origin_code:
        entities["airports"].append(origin_code)
    if dest_code and dest_code not in entities["airports"]:
        if not origin_code:
            entities["airports"].insert(0, "BOM")  # Pad default origin so dest is at index 1
        entities["airports"].append(dest_code)
            
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
                    if row.get('max_fare'):
                        fact += f" | Max Fare: INR {row['max_fare']:,}"
                    if row.get('advance') is not None:
                        fact += f" | Min Advance: {row['advance']} days"
                    if row.get('approval'):
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
