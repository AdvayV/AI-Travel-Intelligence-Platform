import logging
from travel.mock_travel import get_mock_flights

logger = logging.getLogger(__name__)


def search_flights_api(origin: str, dest: str, date: str, cabin_class: str = "ECONOMY") -> list[dict]:
    origin = origin.upper().strip()
    dest = dest.upper().strip()
    cabin_class = cabin_class.upper().strip()
    
    logger.info(f"Retrieving hardcoded/mock flight search data for {origin} -> {dest} on {date}")
    return get_mock_flights(origin, dest, date, cabin_class)


def search_flights_formatted(origin: str, dest: str, date: str, cabin_class: str = "ECONOMY") -> str:
    flights = search_flights_api(origin, dest, date, cabin_class)
    
    if not flights:
        return "No flights found for this route and date."
        
    lines = [f"Available flight options for {origin} -> {dest} on {date} ({cabin_class}):"]
    for idx, f in enumerate(flights, 1):
        stops_str = "Direct" if f['stops'] == 0 else f"{f['stops']}-stop (via {f.get('transit_airport', 'unknown')})"
        lines.append(
            f"{idx}. {f['airline']} {f['flight_number']} | Dep: {f['departure_time']} - Arr: {f['arrival_time']} | "
            f"{stops_str} | Price: INR {f['price_inr']:,} | Fare Class: {f['fare_class']} | Available seats: {f['availability']}"
        )
    return "\n".join(lines)
