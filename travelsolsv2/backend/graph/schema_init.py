import logging
from graph.neo4j_client import run_query, get_driver
from graph.seed_data import SEED_DATA

logger = logging.getLogger(__name__)

def initialize_schema():
    driver = get_driver()
    if driver is None:
        logger.warning("Neo4j database is in mock mode. Skipping schema initialization.")
        return
        
    try:
        # 1. Create constraints
        logger.info("Initializing constraints in Neo4j...")
        constraints = [
            "CREATE CONSTRAINT airport_code_idx IF NOT EXISTS FOR (a:Airport) REQUIRE a.code IS UNIQUE",
            "CREATE CONSTRAINT airline_code_idx IF NOT EXISTS FOR (a:Airline) REQUIRE a.code IS UNIQUE",
            "CREATE CONSTRAINT fare_class_idx IF NOT EXISTS FOR (f:FareClass) REQUIRE f.code IS UNIQUE",
            "CREATE CONSTRAINT waiver_id_idx IF NOT EXISTS FOR (w:Waiver) REQUIRE w.id IS UNIQUE",
            "CREATE CONSTRAINT policy_id_idx IF NOT EXISTS FOR (p:CorporatePolicy) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT passenger_id_idx IF NOT EXISTS FOR (p:Passenger) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT booking_pnr_idx IF NOT EXISTS FOR (b:Booking) REQUIRE b.pnr IS UNIQUE"
        ]
        for c in constraints:
            try:
                run_query(c)
            except Exception as ce:
                logger.warning(f"Failed to create constraint ({c}): {ce}")

        # 2. Check if airports are already seeded
        logger.info("Checking if Airport nodes exist...")
        chk = run_query("MATCH (a:Airport) RETURN count(a) as cnt")
        if chk and chk[0].get("cnt", 0) > 0:
            logger.info("Database is already seeded. Skipping seeding.")
            return

        logger.info("Seeding Neo4j database...")
        
        # Seed Airports
        for airport in SEED_DATA["airports"]:
            run_query(
                "MERGE (a:Airport {code: $code}) SET a.name = $name, a.latitude = $lat, a.longitude = $lon",
                airport
            )
            
        # Seed Airlines
        for airline in SEED_DATA["airlines"]:
            run_query(
                "MERGE (a:Airline {code: $code}) SET a.name = $name, a.alliance = $alliance",
                airline
            )

        # Seed Fare Classes
        for fc in SEED_DATA["fare_classes"]:
            run_query(
                "MERGE (f:FareClass {code: $code}) SET f.name = $name, f.change_fee_inr = $change_fee_inr, f.refund_pct = $refund_pct, f.description = $description",
                fc
            )

        # Seed Waivers
        for waiver in SEED_DATA["waivers"]:
            run_query(
                "MERGE (w:Waiver {id: $id}) SET w.type = $type, w.description = $description, w.valid_from = $valid_from, w.valid_until = $valid_until, w.origin_codes = $origin_codes, w.applies_to = $applies_to, w.fee_waived = $fee_waived, w.discount_pct = $discount_pct",
                waiver
            )

        # Seed Corporate Policies
        for policy in SEED_DATA["corporate_policies"]:
            run_query(
                "MERGE (p:CorporatePolicy {id: $id}) SET p.name = $name, p.allowed_cabins = $allowed_cabins, p.allowed_fare_classes = $allowed_fare_classes, p.max_fare_inr = $max_fare_inr, p.min_advance_days = $min_advance_days, p.preferred_airlines = $preferred_airlines, p.requires_approval_above_inr = $requires_approval_above_inr",
                policy
            )

        # Seed Passengers
        for passenger in SEED_DATA["passengers"]:
            run_query(
                "MERGE (p:Passenger {id: $id}) SET p.name = $name, p.tier = $tier, p.policy_id = $policy_id",
                passenger
            )
            
        # Create relationships (Routes)
        for route in SEED_DATA["routes"]:
            run_query(
                """
                MATCH (o:Airport {code: $origin})
                MATCH (d:Airport {code: $destination})
                MERGE (o)-[r:ROUTE]->(d)
                SET r.airlines = $airlines, r.distance_km = $distance_km
                """,
                route
            )

        # Relate Passengers to Corporate Policies
        run_query(
            """
            MATCH (pa:Passenger)
            MATCH (po:CorporatePolicy {id: pa.policy_id})
            MERGE (pa)-[:HAS_POLICY]->(po)
            """
        )

        # Relate Waivers to Airports or Routes where applicable
        # Weather waiver applies to BOM, DEL origins
        run_query(
            """
            MATCH (w:Waiver {id: 'WX-2026-INDIA'})
            MATCH (a:Airport) WHERE a.code IN ['BOM', 'DEL']
            MERGE (a)-[:HAS_WAIVER]->(w)
            """
        )
        
        # Emirates schedule waiver applies to BOM-DXB, DEL-DXB, BLR-DXB
        run_query(
            """
            MATCH (w:Waiver {id: 'OPS-EK-2026-01'})
            MATCH (o:Airport)-[r:ROUTE]->(d:Airport {code: 'DXB'})
            WHERE o.code IN ['BOM', 'DEL', 'BLR']
            MERGE (o)-[:HAS_WAIVER]->(w)
            """
        )

        logger.info("Graph schema initialised")
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
