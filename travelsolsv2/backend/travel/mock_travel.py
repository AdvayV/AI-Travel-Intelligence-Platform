import random
import string
from datetime import datetime, timedelta

# Operational routes matching Neo4j seed data
OPERATIONAL_ROUTES = {
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

AIRPORTS_INFO = {
    "BOM": "Mumbai", "DEL": "Delhi", "BLR": "Bengaluru", "MAA": "Chennai", "HYD": "Hyderabad",
    "DXB": "Dubai", "SIN": "Singapore", "LHR": "London Heathrow", "JFK": "New York JFK",
    "CDG": "Paris CDG", "NRT": "Tokyo Narita", "BKK": "Bangkok Suvarnabhumi",
    "KUL": "Kuala Lumpur", "DOH": "Doha", "SYD": "Sydney"
}

def generate_pnr() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_mock_flights(origin: str, dest: str, travel_date: str, cabin_class: str = "ECONOMY") -> list[dict]:
    origin = origin.upper().strip()
    dest = dest.upper().strip()
    cabin_class = cabin_class.upper().strip()

    # Determine base pricing based on city pairs (in INR)
    key = (origin, dest)
    if key == ("BOM", "DXB"):
        base_price_range = (28000, 45000)
    elif key == ("BOM", "LHR"):
        base_price_range = (65000, 95000)
    elif "JFK" in key:
        base_price_range = (85000, 140000)
    elif "SIN" in key or "BKK" in key or "KUL" in key:
        base_price_range = (30000, 55000)
    elif "CDG" in key or "LHR" in key or "NRT" in key or "SYD" in key:
        base_price_range = (60000, 110000)
    else:
        base_price_range = (25000, 50000)

    # Adjust base price for business class (3x to 5x economy)
    if cabin_class == "BUSINESS":
        base_price_range = (base_price_range[0] * 3, base_price_range[1] * 4)

    # Determine operating airlines for this route
    airlines = OPERATIONAL_ROUTES.get(key, ["AI"])  # default to Air India
    
    # Generate 3 flights: 2 direct (if supported), 1-2 with stops
    flights = []
    
    # Flight 1: Direct Flight
    airline = airlines[0]
    price_1 = random.randint(base_price_range[0], int(base_price_range[0] * 1.2))
    flight_num_1 = f"{airline}-{random.randint(100, 999)}"
    flights.append({
        "flight_number": flight_num_1,
        "airline": airline,
        "origin": origin,
        "destination": dest,
        "departure_time": f"{travel_date} 08:30",
        "arrival_time": f"{travel_date} 12:45",
        "duration": "4h 15m" if "DXB" in key or "SIN" in key else "9h 30m",
        "stops": 0,
        "cabin_class": cabin_class,
        "fare_class": "J" if cabin_class == "BUSINESS" else "Y",
        "price_inr": price_1,
        "availability": 9
    })

    # Flight 2: Direct Flight (with a different airline if available, otherwise same airline later in day)
    airline = airlines[1] if len(airlines) > 1 else airlines[0]
    price_2 = random.randint(int(base_price_range[0] * 1.1), int(base_price_range[1] * 0.9))
    flight_num_2 = f"{airline}-{random.randint(100, 999)}"
    flights.append({
        "flight_number": flight_num_2,
        "airline": airline,
        "origin": origin,
        "destination": dest,
        "departure_time": f"{travel_date} 16:45",
        "arrival_time": f"{travel_date} 21:00",
        "duration": "4h 15m" if "DXB" in key or "SIN" in key else "9h 30m",
        "stops": 0,
        "cabin_class": cabin_class,
        "fare_class": "C" if cabin_class == "BUSINESS" else "M",
        "price_inr": price_2,
        "availability": 7
    })

    # Flight 3: 1-Stop Flight via a transit hub
    transit_hub = "DOH" if origin != "DOH" and dest != "DOH" else "BOM"
    airline_3 = "QR" if transit_hub == "DOH" else airlines[0]
    price_3 = random.randint(int(base_price_range[0] * 0.85), int(base_price_range[0] * 0.98))  # 1-stop is often slightly cheaper
    flight_num_3 = f"{airline_3}-{random.randint(100, 999)}"
    flights.append({
        "flight_number": flight_num_3,
        "airline": airline_3,
        "origin": origin,
        "destination": dest,
        "departure_time": f"{travel_date} 22:00",
        "arrival_time": f"{travel_date} +1 Day 06:15",
        "duration": "8h 15m",
        "stops": 1,
        "transit_airport": transit_hub,
        "cabin_class": cabin_class,
        "fare_class": "D" if cabin_class == "BUSINESS" else "K",
        "price_inr": price_3,
        "availability": 4
    })

    return flights
