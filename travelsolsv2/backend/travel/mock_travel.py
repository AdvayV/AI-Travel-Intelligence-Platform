import random
import string
import math
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

def calculate_distance_km(origin: str, dest: str) -> float:
    coords = {
        "DXB": (25.2532, 55.3657), "LHR": (51.4700, -0.4543), "SIN": (1.3644, 103.9915),
        "BKK": (13.6900, 100.7501), "JFK": (40.6413, -73.7781), "DOH": (25.2730, 51.6080),
        "KUL": (2.7456, 101.7099), "NRT": (35.7647, 140.3863), "CDG": (49.0097, 2.5479),
        "SYD": (-33.9399, 151.1753), "BOM": (19.0896, 72.8656), "DEL": (28.5562, 77.1000),
        "BLR": (13.1986, 77.7066), "MAA": (12.9941, 80.1709), "HYD": (17.2403, 78.4294)
    }
    if origin not in coords or dest not in coords:
        return 2000.0  # Default fallback distance
        
    lat1, lon1 = coords[origin]
    lat2, lon2 = coords[dest]
    
    # Haversine formula
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_mock_flights(origin: str, dest: str, travel_date: str, cabin_class: str = "ECONOMY") -> list[dict]:
    origin = origin.upper().strip()
    dest = dest.upper().strip()
    cabin_class = cabin_class.upper().strip()

    distance = calculate_distance_km(origin, dest)
    
    # Base rate per kilometer (Economy vs Business) in INR
    rate_per_km = 12.0 if cabin_class == "ECONOMY" else 45.0
    
    # Airline specific pricing multipliers
    airline_multipliers = {
        "6E": 0.85,  # Budget (IndiGo)
        "AI": 1.00,  # Standard (Air India)
        "EK": 1.30,  # Premium (Emirates)
        "QR": 1.35,  # Premium (Qatar Airways)
        "SQ": 1.30,  # Premium (Singapore Airlines)
        "BA": 1.25,  # Premium (British Airways)
    }

    # Determine operating airlines for this route
    key = (origin, dest)
    airlines = OPERATIONAL_ROUTES.get(key, ["AI"])  # default to Air India
    
    flights = []
    
    # Flight 1: Direct Morning Flight
    airline = airlines[0]
    mult = airline_multipliers.get(airline, 1.0)
    price_1 = int(distance * rate_per_km * mult * random.uniform(0.95, 1.05))
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

    # Flight 2: Direct Afternoon/Evening Flight (Slightly peak priced)
    airline = airlines[1] if len(airlines) > 1 else airlines[0]
    mult = airline_multipliers.get(airline, 1.0)
    price_2 = int(distance * rate_per_km * mult * 1.15 * random.uniform(0.95, 1.05))
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

    # Flight 3: 1-Stop Flight via a transit hub (10% discounted)
    transit_hub = "DOH" if origin != "DOH" and dest != "DOH" else "BOM"
    airline_3 = "QR" if transit_hub == "DOH" else airlines[0]
    mult = airline_multipliers.get(airline_3, 1.0)
    price_3 = int(distance * rate_per_km * mult * 0.90 * random.uniform(0.95, 1.05))
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
