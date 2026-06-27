import os
import httpx
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

KIWI_API_KEY = os.getenv("KIWI_API_KEY")
KIWI_API_URL = "https://tequila-api.kiwi.com/v2/search"

logger = logging.getLogger(__name__)

def has_kiwi_credentials() -> bool:
    return bool(KIWI_API_KEY and "your_" not in KIWI_API_KEY)

def search_kiwi_flights(origin: str, dest: str, departure_date: str, cabin_class: str = "ECONOMY") -> list:
    """
    Search flights using Kiwi.com Tequila API
    departure_date should be in YYYY-MM-DD format
    """
    if not has_kiwi_credentials():
        logger.warning("Kiwi.com API key missing. Returning simulated search results.")
        return get_mock_kiwi_flights(origin, dest, departure_date, cabin_class)
        
    try:
        # Convert YYYY-MM-DD to Kiwi's DD/MM/YYYY format
        dt = datetime.strptime(departure_date, "%Y-%m-%d")
        formatted_date = dt.strftime("%d/%m/%Y")
        
        # Map cabin classes to Kiwi codes (M = economy, W = premium economy, C = business, F = first)
        selected_cabin = "M"
        if cabin_class.upper() == "BUSINESS":
            selected_cabin = "C"
        elif cabin_class.upper() == "FIRST":
            selected_cabin = "F"
            
        params = {
            "fly_from": origin.upper().strip(),
            "fly_to": dest.upper().strip(),
            "date_from": formatted_date,
            "date_to": formatted_date,
            "selected_cabins": selected_cabin,
            "curr": "INR",
            "max_stopovers": 1,
            "limit": 10
        }
        
        headers = {
            "apikey": KIWI_API_KEY,
            "accept": "application/json"
        }
        
        logger.info(f"Querying Kiwi Tequila API: {origin} -> {dest} on {departure_date}")
        response = httpx.get(KIWI_API_URL, headers=headers, params=params, timeout=15)
        
        if response.status_code != 200:
            logger.warning(f"Kiwi API returned HTTP {response.status_code}. Using mock data.")
            return get_mock_kiwi_flights(origin, dest, departure_date, cabin_class)
            
        data = response.json()
        raw_flights = data.get("data", [])
        
        # Format raw Kiwi data to match our application's unified flight schema
        flights = []
        for index, item in enumerate(raw_flights):
            # Parse route details
            routes = item.get("route", [])
            carrier = routes[0].get("airline", "AI") if routes else "AI"
            flight_num = f"{carrier}-{routes[0].get('flight_no', '101')}" if routes else "AI-101"
            
            flight = {
                "id": item.get("id", f"kiwi_{index}"),
                "flight_number": flight_num,
                "carrier": carrier,
                "origin": origin,
                "destination": dest,
                "departure_time": item.get("local_departure", f"{departure_date}T08:00:00"),
                "arrival_time": item.get("local_arrival", f"{departure_date}T10:30:00"),
                "price_inr": int(item.get("price", 15000)),
                "fare_class": cabin_class,
                "airline": carrier,
                "stops": len(routes) - 1 if len(routes) > 0 else 0
            }
            flights.append(flight)
            
        return flights
    except Exception as e:
        logger.warning(f"Kiwi API query failed: {e}. Using mock flight search data.")
        return get_mock_kiwi_flights(origin, dest, departure_date, cabin_class)

def get_mock_kiwi_flights(origin: str, dest: str, travel_date: str, cabin_class: str) -> list:
    """Fallback simulated flight options."""
    carrier = "AI" if origin == "BOM" else "SQ"
    base_price = 14500 if cabin_class == "ECONOMY" else 42000
    
    return [
        {
            "id": "mock_kiwi_1",
            "flight_number": f"{carrier}-502",
            "carrier": carrier,
            "origin": origin,
            "destination": dest,
            "departure_time": f"{travel_date}T07:15:00",
            "arrival_time": f"{travel_date}T10:30:00",
            "price_inr": base_price,
            "fare_class": cabin_class,
            "airline": carrier,
            "stops": 0
        },
        {
            "id": "mock_kiwi_2",
            "flight_number": f"{carrier}-911",
            "carrier": carrier,
            "origin": origin,
            "destination": dest,
            "departure_time": f"{travel_date}T14:00:00",
            "arrival_time": f"{travel_date}T18:45:00",
            "price_inr": int(base_price * 1.15),
            "fare_class": cabin_class,
            "airline": carrier,
            "stops": 1
        }
    ]
