import os
import logging
from datetime import date
from dotenv import load_dotenv
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("neo4j driver not installed. Graph database will run in mock mode.")

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

logger = logging.getLogger(__name__)

# Active driver instance
_driver = None
_use_mock = False

def get_driver():
    global _driver, _use_mock
    if not NEO4J_AVAILABLE:
        _use_mock = True
        return None
        
    if _use_mock:
        return None
        
    if _driver is not None:
        return _driver
        
    if not NEO4J_URI or not NEO4J_PASSWORD or NEO4J_URI == "your_neo4j_uri_here":
        logger.warning("Neo4j credentials not set. Falling back to mock Graph database.")
        _use_mock = True
        return None
        
    try:
        logger.info(f"Connecting to Neo4j database at {NEO4J_URI}")
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        # Test connection
        _driver.verify_connectivity()
        logger.info("Successfully connected to Neo4j!")
        return _driver
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j database: {e}. Falling back to mock database.")
        _use_mock = True
        if _driver:
            try:
                _driver.close()
            except:
                pass
            _driver = None
        return None

def close_driver():
    global _driver
    if _driver:
        logger.info("Closing Neo4j driver connection")
        _driver.close()
        _driver = None

def _convert_value(val):
    if not NEO4J_AVAILABLE:
        return val
    try:
        from neo4j.graph import Node, Relationship
        if isinstance(val, Node):
            d = dict(val.items())
            d["_labels"] = list(val.labels)
            d["_id"] = val.element_id
            return d
        elif isinstance(val, Relationship):
            d = dict(val.items())
            d["_type"] = val.type
            d["_start"] = val.start_node.element_id
            d["_end"] = val.end_node.element_id
            return d
    except ImportError:
        return val
    if isinstance(val, list):
        return [_convert_value(item) for item in val]
    elif isinstance(val, dict):
        return {k: _convert_value(v) for k, v in val.items()}
    return val

def run_query(cypher: str, params: dict = None) -> list[dict]:
    driver = get_driver()
    if _use_mock:
        return _run_mock_query(cypher, params)
        
    if params is None:
        params = {}
        
    try:
        with driver.session() as session:
            result = session.run(cypher, params)
            records = []
            for record in result:
                record_dict = {}
                for k, v in record.items():
                    record_dict[k] = _convert_value(v)
                records.append(record_dict)
            return records
    except Exception as e:
        logger.error(f"Neo4j Query Error: {e}. Cypher: {cypher}")
        # Return fallback mock query results
        return _run_mock_query(cypher, params)

def get_route_info(origin: str, dest: str) -> dict:
    origin = origin.upper().strip()
    dest = dest.upper().strip()
    
    query = """
    MATCH (o:Airport {code: $origin})-[r:ROUTE]->(d:Airport {code: $dest})
    OPTIONAL MATCH (d)-[:HAS_WAIVER]->(w:Waiver)
    OPTIONAL MATCH (o)-[:HAS_WAIVER]->(w2:Waiver)
    RETURN o as origin_node, d as dest_node, r as route, collect(distinct w) + collect(distinct w2) as waivers
    """
    results = run_query(query, {"origin": origin, "dest": dest})
    if results and results[0].get("origin_node"):
        row = results[0]
        # Fetch airlines from route metadata or relationship
        airlines = row["route"].get("airlines", [])
        waivers_list = []
        for w in row.get("waivers", []):
            if w:
                waivers_list.append(w)
        return {
            "origin": origin,
            "destination": dest,
            "airlines": airlines,
            "waivers": waivers_list,
            "distance_km": row["route"].get("distance_km", 2000),
            "status": "OPERATIONAL"
        }
    
    # If mock database is active or route wasn't found
    return _get_mock_route_info(origin, dest)

def get_active_waivers(origin: str) -> list[dict]:
    origin = origin.upper().strip()
    today_str = date.today().isoformat()
    
    query = """
    MATCH (w:Waiver)
    WHERE w.valid_until >= $today
    RETURN w
    """
    results = run_query(query, {"today": today_str})
    active_waivers = []
    
    for r in results:
        w = r.get("w")
        if w:
            origin_codes = w.get("origin_codes", [])
            # Also support applies_to check if it lists route like BOM-DXB
            if not origin_codes or origin in origin_codes:
                active_waivers.append(w)
                
    if _use_mock or not active_waivers:
        # Check mock waivers
        all_mocks = _get_mock_waivers()
        return [w for w in all_mocks if not w.get("origin_codes") or origin in w["origin_codes"]]
        
    return active_waivers

def get_corporate_policy(policy_id: str) -> dict:
    policy_id = policy_id.upper().strip()
    query = """
    MATCH (p:CorporatePolicy {id: $policy_id})
    RETURN p
    """
    results = run_query(query, {"policy_id": policy_id})
    if results and results[0].get("p"):
        return results[0]["p"]
        
    return _get_mock_corporate_policy(policy_id)

def write_booking(booking_data: dict) -> str:
    pnr = booking_data.get("pnr")
    passenger_name = booking_data.get("passenger_name")
    flight_number = booking_data.get("flight_number")
    origin = booking_data.get("origin")
    dest = booking_data.get("destination")
    date_str = booking_data.get("date")
    fare_class = booking_data.get("fare_class")
    price = booking_data.get("price_inr")
    
    query = """
    MERGE (b:Booking {pnr: $pnr})
    ON CREATE SET 
        b.passenger_name = $passenger_name,
        b.flight_number = $flight_number,
        b.origin = $origin,
        b.destination = $destination,
        b.date = $date,
        b.fare_class = $fare_class,
        b.price_inr = $price,
        b.created_at = timestamp()
    RETURN b.pnr as pnr
    """
    params = {
        "pnr": pnr,
        "passenger_name": passenger_name,
        "flight_number": flight_number,
        "origin": origin,
        "destination": dest,
        "date": date_str,
        "fare_class": fare_class,
        "price": price
    }
    
    results = run_query(query, params)
    if results:
        logger.info(f"Saved booking node in Neo4j: {pnr}")
        return results[0]["pnr"]
    return pnr

# ================= MOCK FALLBACK DATA & PARSING =================

def _run_mock_query(cypher: str, params: dict) -> list[dict]:
    # Extremely simple cypher simulator for stats or startup check
    cypher_lower = cypher.lower()
    if "match (a:airport)" in cypher_lower or "limit 1" in cypher_lower:
        # Check if Airport nodes exist for startup
        return [{"a": {"code": "BOM"}}] if "airport" in cypher_lower else []
        
    if "count(" in cypher_lower:
        # Stats query:
        # MATCH (a:Airport) RETURN count(a) as airports
        # MATCH (r:Route) ...
        # Since we just return a dict of stats, we simulate based on query patterns.
        if "airport" in cypher_lower:
            return [{"airports": 15}]
        elif "route" in cypher_lower:
            return [{"routes": 20}]
        elif "waiver" in cypher_lower:
            return [{"waivers": 4}]
        elif "booking" in cypher_lower:
            return [{"bookings": 5}]
            
    return []

def _get_mock_route_info(origin: str, dest: str) -> dict:
    # Safe default route info matching seed specs
    route_operators = {
        ("BOM", "DXB"): ["AI", "EK"],
        ("BOM", "LHR"): ["AI", "BA"],
        ("BOM", "SIN"): ["AI", "SQ", "6E"],
        ("BOM", "JFK"): ["AI"],
        ("BOM", "DOH"): ["QR"],
        ("BOM", "BKK"): ["AI"],
        ("DEL", "DXB"): ["AI", "EK"],
        ("DEL", "LHR"): ["AI", "BA"],
        ("DEL", "JFK"): ["AI"],
        ("DEL", "SIN"): ["AI", "SQ"],
        ("DEL", "CDG"): ["AI"],
        ("BLR", "DXB"): ["AI", "EK"],
        ("BLR", "SIN"): ["SQ"],
        ("BLR", "BKK"): ["AI"],
        ("MAA", "SIN"): ["SQ"],
        ("MAA", "KUL"): ["AI"],
        ("HYD", "DXB"): ["EK"],
        ("HYD", "SIN"): ["SQ"],
        ("BOM", "NRT"): ["AI"],
        ("DEL", "SYD"): ["AI"]
    }
    
    key = (origin, dest)
    airlines = route_operators.get(key, ["AI"])
    
    # Check for mock waivers that apply
    applicable_waivers = []
    for w in _get_mock_waivers():
        # weather waiver: BOM / DEL origins
        if w.get("origin_codes") and origin in w["origin_codes"]:
            applicable_waivers.append(w)
        # operations waiver: EK to DXB
        elif "DXB" in dest and "EK" in airlines and "EK" in w.get("description", ""):
            applicable_waivers.append(w)
            
    return {
        "origin": origin,
        "destination": dest,
        "airlines": airlines,
        "waivers": applicable_waivers,
        "distance_km": 1930 if "DXB" in dest else 7200,
        "status": "OPERATIONAL"
    }

def _get_mock_waivers() -> list[dict]:
    return [
        {
            "id": "WX-2026-INDIA",
            "type": "weather",
            "description": "Mumbai monsoon weather disruption",
            "valid_from": "2026-06-22",
            "valid_until": "2026-06-30",
            "origin_codes": ["BOM", "DEL"],
            "applies_to": ["all routes"],
            "fee_waived": True
        },
        {
            "id": "OPS-EK-2026-01",
            "type": "irops",
            "description": "Emirates schedule disruption Middle East",
            "valid_from": "2026-06-01",
            "valid_until": "2026-07-31",
            "applies_to": ["BOM-DXB", "DEL-DXB", "BLR-DXB"],
            "fee_waived": True
        },
        {
            "id": "CORP-AI-ANNUAL",
            "type": "corporate",
            "description": "Air India corporate agreement discount",
            "applies_to": ["all AI routes"],
            "discount_pct": 12
        },
        {
            "id": "EMRG-2026",
            "type": "emergency",
            "description": "Emergency travel exception, all routes all airlines",
            "requires_code": True,
            "approval_required": True
        }
    ]

def _get_mock_corporate_policy(policy_id: str) -> dict:
    policies = {
        "CP-001": {
            "id": "CP-001",
            "name": "Standard Travel Policy",
            "allowed_cabins": ["ECONOMY"],
            "allowed_fare_classes": ["Y", "M", "K", "Q"],
            "max_fare_inr": 150000,
            "min_advance_days": 7,
            "preferred_airlines": ["AI", "6E"],
            "requires_approval_above_inr": 100000
        },
        "CP-002": {
            "id": "CP-002",
            "name": "Senior Management Travel Policy",
            "allowed_cabins": ["ECONOMY", "BUSINESS"],
            "allowed_fare_classes": ["Y", "M", "K", "J", "C", "D"],
            "max_fare_inr": 500000,
            "min_advance_days": 3,
            "preferred_airlines": ["AI", "EK", "QR"],
            "requires_approval_above_inr": 400000
        },
        "CP-003": {
            "id": "CP-003",
            "name": "Executive Grade Policy",
            "allowed_cabins": ["ECONOMY", "BUSINESS", "FIRST"],
            "allowed_fare_classes": ["Y", "M", "K", "Q", "J", "C", "D", "G"],
            "max_fare_inr": 9999999,
            "min_advance_days": 0,
            "preferred_airlines": ["AI", "EK", "QR", "SQ", "BA", "6E"],
            "requires_approval_above_inr": 9999999
        }
    }
    return policies.get(policy_id, policies["CP-001"])
