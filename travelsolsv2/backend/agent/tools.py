import json
import logging
import httpx
from datetime import datetime, date
try:
    from langchain_classic.agents import Tool
except ImportError:
    class Tool:
        def __init__(self, name, func, description):
            self.name = name
            self.func = func
            self.description = description
from travel.flight_search import search_flights_formatted
from travel.pnr_builder import create_pnr_api
from graph.neo4j_client import get_corporate_policy, get_active_waivers, write_booking

logger = logging.getLogger(__name__)

AIRPORT_COORDS = {
    "DXB": (25.2532, 55.3657), "LHR": (51.4700, -0.4543), "SIN": (1.3644, 103.9915),
    "BKK": (13.6900, 100.7501), "JFK": (40.6413, -73.7781), "DOH": (25.2730, 51.6080),
    "KUL": (2.7456, 101.7099), "NRT": (35.7647, 140.3863), "CDG": (49.0097, 2.5479),
    "SYD": (-33.9399, 151.1753), "BOM": (19.0896, 72.8656), "DEL": (28.5562, 77.1000),
    "BLR": (13.1986, 77.7066), "MAA": (12.9941, 80.1709), "HYD": (17.2403, 78.4294)
}

def parse_args(input_str: str) -> list:
    """Helper to parse tool arguments from JSON or comma-separated formats."""
    cleaned = input_str.strip()
    try:
        # Try JSON parsing
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return list(data.values())
        elif isinstance(data, list):
            return data
    except:
        pass
        
    # Comma separation parser (strip quotes and whitespace)
    parts = []
    current = []
    in_quotes = False
    quote_char = None
    
    for char in cleaned:
        if char in ('"', "'"):
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
        elif char == ',' and not in_quotes:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    
    # Strip wrapping quotes from components
    return [p.strip("\"'") for p in parts if p]

# --- Tool 1: search_flights ---
def search_flights_tool(input_str: str) -> str:
    args = parse_args(input_str)
    if len(args) < 3:
        return "ERROR: search_flights requires: origin, destination, date. Example: BOM, DXB, 2026-06-25"
        
    origin = args[0]
    dest = args[1]
    travel_date = args[2]
    cabin_class = args[3] if len(args) > 3 else "ECONOMY"
    
    try:
        return search_flights_formatted(origin, dest, travel_date, cabin_class)
    except Exception as e:
        return f"ERROR: Flight search failed: {e}"

# --- Tool 2: check_policy_compliance ---
def check_policy_compliance_tool(input_str: str) -> str:
    args = parse_args(input_str)
    if len(args) < 5:
        return "ERROR: check_policy_compliance requires: policy_id, fare_class, total_fare, advance_days, airline_code. Example: CP-001, Economy, 32000, 5, AI"
        
    policy_id = args[0].upper().strip()
    fare_class_input = args[1].strip()
    try:
        total_fare = int(float(str(args[2]).replace(",", "")))
    except:
        return f"ERROR: Invalid price/fare input: {args[2]}"
    try:
        advance_days = int(args[3])
    except:
        return f"ERROR: Invalid advance days input: {args[3]}"
    airline_code = args[4].upper().strip()
    
    policy = get_corporate_policy(policy_id)
    if not policy:
        return f"ERROR: Policy ID {policy_id} not found."
        
    violations = []
    
    # Map input class to standard display names: "Economy" or "Business"
    if fare_class_input.upper() in ["Y", "M", "K", "Q", "ECONOMY", "ECON"]:
        display_class = "Economy"
        raw_code = "Y"
    elif fare_class_input.upper() in ["J", "C", "D", "BUSINESS", "BIZ"]:
        display_class = "Business"
        raw_code = "J"
    else:
        display_class = fare_class_input
        raw_code = fare_class_input
    
    # 1. Fare Class compliance
    allowed_fare_classes = policy.get("allowed_fare_classes", [])
    # Map allowed classes list to display classes
    allowed_display_classes = set()
    for code in allowed_fare_classes:
        if code in ["J", "C", "D"]:
            allowed_display_classes.add("Business")
        else:
            allowed_display_classes.add("Economy")
            
    if display_class not in allowed_display_classes:
        violations.append(f"Fare class '{display_class}' is restricted. Allowed class: {', '.join(allowed_display_classes)}")
        
    # 2. Maximum price check
    max_fare = policy.get("max_fare_inr", 999999)
    if total_fare > max_fare:
        violations.append(f"Total fare INR {total_fare:,} exceeds the maximum limit of INR {max_fare:,}")
        
    # 3. Advance booking window check
    min_advance = policy.get("min_advance_days", 0)
    if advance_days < min_advance:
        violations.append(f"Booked {advance_days} days in advance, but policy requires at least {min_advance} days advance booking")
        
    # 4. Airline vendor check
    pref_airlines = policy.get("preferred_airlines", [])
    is_preferred = airline_code in pref_airlines
    
    if violations:
        reason = "; ".join(violations)
        if not is_preferred:
            reason += f" (Note: Non-preferred airline '{airline_code}')"
        return f"NON-COMPLIANT: {reason}"
        
    if not is_preferred:
        return f"COMPLIANT: Route compliance passed, but airline '{airline_code}' is non-preferred. Requires line manager notification."
        
    return "COMPLIANT: All corporate policy checks passed successfully."

# --- Tool 3: check_active_waivers ---
def check_active_waivers_tool(input_str: str) -> str:
    args = parse_args(input_str)
    if not args:
        return "ERROR: check_active_waivers requires origin airport code. Example: BOM"
    origin = args[0].upper().strip()
    
    try:
        waivers = get_active_waivers(origin)
        if not waivers:
            return f"No active weather or schedule fee waivers currently apply to origin {origin}."
            
        lines = [f"Active fee waivers for departures from {origin}:"]
        for w in waivers:
            fee_status = "Change fee waived" if w.get("fee_waived") else "Standard change fees apply"
            valid_until = w.get('valid_until', 'Ongoing')
            lines.append(
                f"- Waiver Code: {w.get('id', 'UNKNOWN')} | Type: {w.get('type', 'general')} | Valid until: {valid_until} | "
                f"Description: '{w.get('description', 'N/A')}' | Conditions: {fee_status}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"ERROR: Failed to retrieve waivers: {e}"

# --- Tool 4: get_weather_risk ---
# --- Tool 4: get_weather_risk ---
def get_weather_risk_tool(input_str: str) -> str:
    args = parse_args(input_str)
    if not args:
        return "ERROR: get_weather_risk requires airport code. Example: BOM"
    airport = args[0].upper().strip()
    
    # Parse target date if provided
    target_date = None
    day_offset = 0
    if len(args) > 1 and args[1]:
        target_date_str = str(args[1]).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                target_date = datetime.strptime(target_date_str, fmt).date()
                break
            except ValueError:
                continue
                
        if target_date:
            today = date.today()
            delta = (target_date - today).days
            if 0 <= delta < 16:
                day_offset = delta
    
    if airport not in AIRPORT_COORDS:
        return f"Airport code {airport} coordinates not found in system coords database. Assuming LOW weather risk."
        
    lat, lon = AIRPORT_COORDS[airport]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
        f"&forecast_days=16"
        f"&timezone=auto"
    )
    
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})
        weathercodes = daily.get("weather_code", daily.get("weathercode", []))
        temp_maxes = daily.get("temperature_2m_max", [])
        
        points = 0.0
        days = min(16, len(weathercodes))
        if days == 0:
            return f"Weather data unavailable for {airport}. Assuming MODERATE risk."
            
        for i in range(days):
            wc = weathercodes[i] or 0
            tmax = temp_maxes[i]
            
            if wc < 50:
                points += 1.0
            elif 50 <= wc <= 69:
                points += 0.3
            
            if tmax is not None:
                if 18 <= tmax <= 30:
                    points += 0.5
                elif tmax > 38:
                    points -= 0.5
                    
        max_points = days * 1.5
        score = max(0.0, min(1.0, points / max_points))
        
        if score >= 0.8:
            risk = "LOW weather risk"
        elif score >= 0.5:
            risk = "MODERATE weather risk (Mild precipitation or high/low temperature warnings)"
        else:
            risk = "HIGH weather risk (Severe weather patterns, potential monsoon or schedule disruptions forecasted)"
            
        # Translate WMO weather code to English description
        wmo_codes = {
            0: "Clear sky ☀️",
            1: "Mainly clear 🌤", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
            45: "Foggy 🌫", 48: "Foggy 🌫",
            51: "Light drizzle 🌧", 53: "Moderate drizzle 🌧", 55: "Dense drizzle 🌧",
            61: "Slight rain 🌧", 63: "Moderate rain 🌧", 65: "Heavy rain 🌧",
            71: "Slight snow 🌨", 73: "Moderate snow 🌨", 75: "Heavy snow 🌨",
            80: "Slight rain showers 🌦", 81: "Moderate rain showers 🌦", 82: "Violent rain showers 🌦",
            95: "Thunderstorm ⛈", 96: "Thunderstorm ⛈", 99: "Thunderstorm ⛈"
        }
        
        wc_val = weathercodes[day_offset] if day_offset < len(weathercodes) else 0
        tmax_val = temp_maxes[day_offset] if day_offset < len(temp_maxes) else 25.0
        weather_desc = wmo_codes.get(wc_val, "Fair weather")
        
        date_label = f"on {target_date}" if target_date else "today"
        return f"Weather report for {airport} {date_label}: Risk Level: {risk} (Stability Score: {round(score * 100)}%). Forecasted conditions: Temperature: {tmax_val}°C, condition: {weather_desc}."
    except Exception as e:
        logger.warning(f"Weather API failed for {airport}: {e}")
        return f"Weather API check failed for {airport} due to network timeout. Returning default: MODERATE weather risk (Safety warning: weather conditions should be checked manually before flight confirmation)."

# --- Tool 5: create_pnr ---
def create_pnr_tool(input_str: str) -> str:
    args = parse_args(input_str)
    if len(args) < 7:
        return "ERROR: create_pnr requires: passenger_name, flight_number, origin, destination, date, fare_class, price. Example: Aryan Mehta, AI-201, BOM, DXB, 2026-06-25, Economy, 32000"
        
    passenger_name = args[0]
    flight_number = args[1]
    origin = args[2]
    destination = args[3]
    date_str = args[4]
    fare_class = args[5]
    try:
        price = int(float(str(args[6]).replace(",", "")))
    except:
        return f"ERROR: Invalid price/fare input: {args[6]}"
        
    # Standardize fare class name
    if fare_class.upper() in ["Y", "M", "K", "Q", "ECONOMY", "ECON"]:
        fare_class = "Economy"
    elif fare_class.upper() in ["J", "C", "D", "BUSINESS", "BIZ"]:
        fare_class = "Business"
        
    try:
        # Create PNR via Travel endpoint / mock
        booking_res = create_pnr_api(passenger_name, flight_number, origin, destination, date_str, fare_class, price)
        pnr = booking_res.get("pnr")
        
        # Save node in Graph Database
        write_booking(booking_res)
        
        return (
            f"SUCCESS: PNR created successfully! PNR Code: {pnr}. "
            f"Passenger: {passenger_name} | Flight: {flight_number} | Sector: {origin}->{destination} on {date_str} | "
            f"Fare Class: {fare_class} | Price: INR {price:,} | Booking engine source: {booking_res.get('source')}."
        )
    except Exception as e:
        return f"ERROR: Booking execution failed: {e}"

# Expose LangChain Tool list
ALL_TOOLS = [
    Tool(
        name="check_active_waivers",
        func=check_active_waivers_tool,
        description="Check if any active fee waivers or weather disruptions apply to an origin airport. Input: origin_airport_code. Example: BOM"
    ),
    Tool(
        name="get_weather_risk",
        func=get_weather_risk_tool,
        description="Get current weather risk score for an airport. Input: airport_code. Example: BOM"
    ),
    Tool(
        name="search_flights",
        func=search_flights_tool,
        description="Search available flights between two airports on a given date. Input: origin, destination, date, cabin_class. Example: BOM, DXB, 2026-06-25, ECONOMY"
    ),
    Tool(
        name="check_policy_compliance",
        func=check_policy_compliance_tool,
        description="Check if a proposed booking complies with corporate travel policies. Input: policy_id, fare_class, total_fare, advance_days, airline_code. Example: CP-001, Economy, 32000, 5, AI"
    ),
    Tool(
        name="create_pnr",
        func=create_pnr_tool,
        description="Create a passenger name record (PNR) booking. Use ONLY after verifying weather, waivers, flight options, and policy compliance. Input: passenger_name, flight_number, origin, destination, date, fare_class, price. Example: Aryan Mehta, AI-201, BOM, DXB, 2026-06-25, Economy, 32000"
    )
]
