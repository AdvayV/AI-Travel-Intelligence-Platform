import os
import re
import random
import logging
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from agent.graph_rag import retrieve_context
from agent.tools import ALL_TOOLS

def parse_prompt_date(query: str, current_date_str: str = "2026-06-25") -> str:
    query_lower = query.lower()
    
    # 1. Look for absolute date YYYY-MM-DD
    date_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", query)
    if date_match:
        return date_match.group(0)
        
    try:
        base_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
    except:
        base_date = date(2026, 6, 25)
        
    # 2. Check relative terms
    if "today" in query_lower:
        return base_date.strftime("%Y-%m-%d")
    elif "tomorrow" in query_lower:
        return (base_date + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "day after tomorrow" in query_lower:
        return (base_date + timedelta(days=2)).strftime("%Y-%m-%d")
    elif "next week" in query_lower:
        return (base_date + timedelta(days=7)).strftime("%Y-%m-%d")
        
    # 3. Check for "in X days"
    days_match = re.search(r"\bin\s+(\d+)\s+days\b", query_lower)
    if days_match:
        days = int(days_match.group(1))
        return (base_date + timedelta(days=days)).strftime("%Y-%m-%d")
        
    return current_date_str

load_dotenv()

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

logger = logging.getLogger(__name__)

# Try to import LangChain libraries, set flags to fall back to mock if not installed
try:
    from langchain_openai import ChatOpenAI
    from langchain_classic.agents import create_react_agent, AgentExecutor
    from langchain_classic.prompts import PromptTemplate
    from agent.prompts import SYSTEM_PROMPT, CONTEXT_PROMPT_TEMPLATE
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain packages not installed. Running in mock deterministic mode.")

# Attempt to initialize LLM if LangChain is available
_llm = None
if LANGCHAIN_AVAILABLE and HUGGINGFACE_API_KEY and HUGGINGFACE_API_KEY != "your_huggingface_api_key_here":
    try:
        logger.info("Initializing HuggingFace Llama-3-8B-Instruct via OpenAI-compatible router...")
        _llm = ChatOpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=HUGGINGFACE_API_KEY,
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            max_tokens=600,
            temperature=0.1,
            timeout=20
        )
    except Exception as e:
        logger.error(f"Failed to initialize HuggingFace LLM: {e}. Agent will run in mock deterministic mode.")
        _llm = None
else:
    if LANGCHAIN_AVAILABLE:
        logger.warning("HUGGINGFACE_API_KEY not set. Agent will run in mock deterministic mode.")

def extract_booking_params(query: str, entities: dict, passenger: str = None) -> tuple:
    passenger_bands = {
        "Aryan Mehta": 7,
        "Priya Sharma": 4,
        "Rajesh Kumar": 8,
        "Anita Singh": 3,
        "Vikram Nair": 9
    }
    
    # 1. Parse band
    band = None
    band_match = re.search(r"\b[Bb]and\s*([1-9])\b", query)
    if band_match:
        band = int(band_match.group(1))
    else:
        p_name = passenger
        if p_name and p_name.strip() in passenger_bands:
            band = passenger_bands[p_name.strip()]
        else:
            for k, v in passenger_bands.items():
                if k.lower() in query.lower():
                    band = v
                    break
    if band is None:
        band = 5  # default band
        
    # 2. Determine cabin class
    dest = entities["airports"][1] if entities.get("airports") and len(entities["airports"]) > 1 else "DXB"
    is_long_haul = dest.upper() in ["LHR", "JFK", "SYD", "CDG", "NRT"]
    
    if "business" in query.lower():
        cabin_class = "BUSINESS"
    elif "first" in query.lower():
        cabin_class = "FIRST"
    elif "economy" in query.lower():
        cabin_class = "ECONOMY"
    elif is_long_haul and band >= 6:
        # Long-haul and band permit business class -> Default to BUSINESS
        cabin_class = "BUSINESS"
    else:
        cabin_class = "ECONOMY"
        
    # 3. Determine policy ID
    if not entities.get("policies"):
        if 6 <= band <= 8:
            policy_id = "CP-002"
        elif band == 9:
            policy_id = "CP-003"
        else:
            policy_id = "CP-001"
    else:
        policy_id = entities["policies"][0]
        
    return band, cabin_class, policy_id

def evaluate_flight_options(origin: str, dest: str, travel_date: str, cabin_class: str, policy_id: str, band: int = None) -> list:
    from travel.flight_search import search_flights_api
    from graph.neo4j_client import get_active_waivers, get_corporate_policy
    from agent.tools import get_weather_risk_tool
    from scheduler import get_single_forecast
    
    try:
        flights = search_flights_api(origin, dest, travel_date, cabin_class)
    except Exception as e:
        logger.error(f"Flight search failed in evaluation: {e}")
        flights = []

    # Calculate travel date offset from today
    try:
        travel_dt = datetime.strptime(travel_date, "%Y-%m-%d").date()
        day_offset = (travel_dt - date.today()).days
        if day_offset < 0:
            day_offset = 0
    except:
        day_offset = 0

    # --- Surge Pricing from Route Forecast for travel date ---
    surge_info = None
    try:
        base_forecast = get_single_forecast(origin.upper(), dest.upper())
        if base_forecast:
            from scheduler import recompute_forecast_for_day
            forecast = recompute_forecast_for_day(base_forecast, day_offset)
            if forecast and forecast.get("surge_multiplier", 1.0) > 0.0:
                surge_info = {
                    "multiplier": forecast["surge_multiplier"],
                    "score": forecast["score"],
                    "tier": forecast["tier"],
                    "trend": forecast["trend"],
                    "momentum_pct": forecast["momentum_pct"]
                }
                logger.info(f"Recomputed surge for {origin}-{dest} on day offset {day_offset}: {surge_info['multiplier']}x (score={surge_info['score']})")
    except Exception as e:
        logger.warning(f"Could not load/recompute surge forecast for {origin}-{dest}: {e}")
        
    try:
        waivers = get_active_waivers(origin)
    except Exception as e:
        logger.error(f"Waiver check failed in evaluation: {e}")
        waivers = []
        
    has_monsoon_waiver = any(w.get("id") == "WX-2026-INDIA" for w in waivers)
    
    # Fetch destination weather for the specific travel date using Open-Meteo
    from weather_client import get_weather_detail
    dest_weather_desc = "Weather information unavailable"
    is_high_weather_risk = False
    try:
        dest_w = get_weather_detail(dest.upper())
        if "days" in dest_w and 0 <= day_offset < len(dest_w["days"]):
            day_data = dest_w["days"][day_offset]
            dest_weather_desc = f"{day_data['temp_max_c']}°C, {day_data['condition']} {day_data['emoji']}"
            # Determine risk level based on daily appeal score
            appeal = day_data.get("appeal", 1.0)
            if appeal <= 0.4:
                is_high_weather_risk = True
            logger.info(f"Retrieved destination weather for day offset {day_offset}: {dest_weather_desc} (is_high_weather_risk={is_high_weather_risk})")
        else:
            temp = dest_w.get("today_temp_max_c")
            cond = dest_w.get("today_condition")
            emoji = dest_w.get("today_emoji", "")
            if temp is not None:
                dest_weather_desc = f"{temp}°C, {cond} {emoji}"
            is_high_weather_risk = dest_w.get("overall_appeal", 1.0) <= 0.4
    except Exception as e:
        logger.warning(f"Could not retrieve weather details for {dest}: {e}")

    weather_summary = dest_weather_desc

    
    try:
        policy = get_corporate_policy(policy_id) or {}
    except Exception as e:
        logger.error(f"Policy retrieval failed in evaluation: {e}")
        policy = {}
        
    evaluated = []
    
    # Calculate advance booking days
    try:
        travel_dt = datetime.strptime(travel_date, "%Y-%m-%d").date()
        advance_days = (travel_dt - date.today()).days
        if advance_days < 0:
            advance_days = 7
    except:
        advance_days = 7
        
    for f in flights:
        f_num = f["flight_number"]
        airline = f["airline"]
        f_class = f["fare_class"]
        price = f["price_inr"]

        display_class = "Business" if f_class in ["J", "C", "D"] or f.get("cabin_class") == "BUSINESS" else "Economy"

        # Apply surge multiplier if demand is high on this route
        surge_applied = None
        if surge_info:
            pre_surge_price = price
            price = int(price * surge_info["multiplier"])
            surge_applied = {
                "multiplier": surge_info["multiplier"],
                "pre_surge_price_inr": pre_surge_price,
                "reason": f"High demand surge ({surge_info['tier']} tier, score {surge_info['score']:.0f}, trend {surge_info['trend']})"
            }
            f["price_inr"] = price  # update so policy cap check uses surged price
        
        # Policy rules
        allowed_fare_classes = policy.get("allowed_fare_classes", [])
        max_fare = policy.get("max_fare_inr", 999999)
        min_advance = policy.get("min_advance_days", 0)
        pref_airlines = policy.get("preferred_airlines", [])
        
        violations = []
        waiver_exceptions = []

        # Check passenger band and destination restrictions
        if band is not None:
            # Bands 1-5: strictly restricted to Economy on all routes
            if 1 <= band <= 5:
                if display_class == "Business":
                    violations.append(f"Passenger is in Band {band} and is restricted to Economy travel only")
            # Bands 6-7: allowed Business only on transcontinental routes
            elif 6 <= band <= 7:
                is_long_haul = dest.upper() in ["LHR", "JFK", "SYD", "CDG", "NRT"]
                if display_class == "Business" and not is_long_haul:
                    violations.append(f"Passenger is in Band {band} and is restricted to Economy on short-haul/medium-haul routes (only transcontinental routes permit Business class)")
            # Bands 8-9: allowed Business on all routes
        
        # Check fare class compliance
        allowed_fare_classes_normalized = list(allowed_fare_classes)
        # If Business class is allowed destination and band-wise, we ensure standard business fare classes are treated as allowed
        if display_class == "Business":
            is_long_haul = dest.upper() in ["LHR", "JFK", "SYD", "CDG", "NRT"]
            if (band >= 8) or (6 <= band <= 7 and is_long_haul):
                # Ensure business classes are allowed
                allowed_fare_classes_normalized.extend(["J", "C", "D"])
                
        if f_class not in allowed_fare_classes_normalized:
            # Waiver Exception: CP-001 monsoon provisions reduces restrictions for Y class
            if policy_id == "CP-001" and has_monsoon_waiver and f_class == "Y":
                waiver_exceptions.append("Economy allowed under Monsoon Waiver Exception (WX-2026-INDIA)")
            else:
                violations.append(f"Fare class '{display_class}' is restricted under policy {policy_id}.")
                
        # Check maximum price
        if price > max_fare:
            violations.append(f"Price INR {price:,} exceeds policy cap of INR {max_fare:,}")
            
        # Check advance booking window
        if advance_days < min_advance:
            # Waiver Exception: CP-001 Monsoon Amendment reduces booking window to 2 days
            if policy_id == "CP-001" and has_monsoon_waiver and advance_days >= 2:
                waiver_exceptions.append("Advance booking reduced to 2 days under Monsoon Amendment")
            # Senior management transcontinental exception (dest LHR, JFK is > 8h)
            elif policy_id == "CP-002" and dest in ["LHR", "JFK"] and advance_days < min_advance:
                waiver_exceptions.append("Advance booking window exception applied for transcontinental sector > 8h")
            else:
                violations.append(f"Booked {advance_days} days in advance, policy requires {min_advance} days")
                
        # Check preferred carrier
        is_preferred = airline in pref_airlines
        carrier_note = None
        if not is_preferred:
            carrier_note = f"Non-preferred airline '{airline}'"
            
        # Overall status
        if violations:
            compliant = False
            compliance_details = "NON-COMPLIANT: " + "; ".join(violations)
        elif waiver_exceptions:
            compliant = True
            compliance_details = "COMPLIANT via Waiver Exception: " + "; ".join(waiver_exceptions)
        else:
            compliant = True
            compliance_details = "COMPLIANT: All checks passed."
            if carrier_note:
                compliance_details += f" ({carrier_note} requires notification)"
                
        # Check if booking requires approval
        requires_approval = False
        approval_threshold = policy.get("requires_approval_above_inr", 999999)
        if compliant and price > approval_threshold:
            requires_approval = True
            compliance_details += f" (Requires executive approval above INR {approval_threshold:,})"
        elif compliant and carrier_note:
            requires_approval = True
            
        disruption_risk = "LOW"
        disruption_warning = ""
        # Weather warnings
        if is_high_weather_risk:
            if "08:30" in f["departure_time"] or "09:00" in f["departure_time"]:
                disruption_risk = "HIGH"
                disruption_warning = "Severe weather warning during departure window. High delay probability."
            else:
                disruption_risk = "MODERATE"
                disruption_warning = "Monsoon warning active. Afternoon flights carry lower delay probability."
                
        # Corporate discount: CORP-AI-ANNUAL gives 12% discount on Air India (AI) flights
        original_price = price
        discount_applied = None
        if airline == "AI" and any(w.get("id") == "CORP-AI-ANNUAL" for w in waivers):
            discounted_price = int(price * 0.88)
            price = discounted_price
            discount_applied = "12% Corporate AI Discount"
            
        evaluated.append({
            "flight_number": f_num,
            "airline": airline,
            "origin": f["origin"],
            "destination": f["destination"],
            "departure_time": f["departure_time"],
            "arrival_time": f["arrival_time"],
            "duration": f["duration"],
            "stops": f["stops"],
            "fare_class": display_class,
            "price_inr": price,
            "original_price_inr": original_price,
            "discount_applied": discount_applied,
            "surge_applied": surge_applied,
            "compliant": compliant,
            "requires_approval": requires_approval,
            "compliance_details": compliance_details,
            "disruption_risk": disruption_risk,
            "disruption_warning": disruption_warning,
            "weather": weather_summary,
            "is_alternative": False
        })
        
    # Generate weather resilient or rerouting alternatives
    if is_high_weather_risk and origin == "BOM":
        try:
            blr_flights = search_flights_api("BLR", dest, travel_date, cabin_class)
        except Exception as e:
            logger.error(f"Alternative BLR flight search failed: {e}")
            blr_flights = []
            
        for f in blr_flights[:2]:
            airline = f["airline"]
            f_class = f["fare_class"]
            price = f["price_inr"]

            display_class = "Business" if f_class in ["J", "C", "D"] or f.get("cabin_class") == "BUSINESS" else "Economy"
            
            # Policy evaluation
            violations = []
            if band is not None:
                if 1 <= band <= 5:
                    if display_class == "Business":
                        violations.append(f"Passenger is in Band {band} and is restricted to Economy travel only")
            if f_class not in allowed_fare_classes:
                violations.append(f"Fare class '{display_class}' is restricted. Allowed class: Economy")
            if price > max_fare:
                violations.append(f"Price INR {price:,} exceeds cap.")
            if advance_days < min_advance:
                violations.append(f"Requires {min_advance} days advance booking.")
                
            compliant = len(violations) == 0
            details = "COMPLIANT: Weather-resilient reroute from BLR." if compliant else "NON-COMPLIANT: " + "; ".join(violations)
            
            evaluated.append({
                "flight_number": f["flight_number"],
                "airline": airline,
                "origin": f["origin"],
                "destination": f["destination"],
                "departure_time": f["departure_time"],
                "arrival_time": f["arrival_time"],
                "duration": f["duration"],
                "stops": f["stops"],
                "fare_class": display_class,
                "price_inr": price,
                "original_price_inr": price,
                "discount_applied": None,
                "compliant": compliant,
                "requires_approval": not compliant,
                "compliance_details": details,
                "disruption_risk": "LOW",
                "disruption_warning": "Departure from BLR hub is unaffected by Mumbai Monsoon.",
                "weather": weather_summary,
                "is_alternative": True
            })
            
    return evaluated

def run_booking_agent(query: str, passenger_name: str = None) -> dict:
    # 1. Retrieve GraphRAG context
    context = retrieve_context(query, passenger_name)
    
    # Extract flight parameters for standard structure
    entities = context["entities"]
    passenger = passenger_name if passenger_name else (entities["passengers"][0] if entities["passengers"] else "Aryan Mehta")
    origin = entities["airports"][0] if entities["airports"] else "BOM"
    dest = entities["airports"][1] if len(entities["airports"]) > 1 else "DXB"
    date_str = parse_prompt_date(query)
    
    # Dynamically extract passenger band, cabin class, and policy
    band, cabin_class, policy_id = extract_booking_params(query, entities, passenger)
    
    # If LLM is not available or LangChain is not installed, run fallback mock execution directly
    if _llm is None or not LANGCHAIN_AVAILABLE:
        logger.info("Executing mock agent loop...")
        return run_mock_agent(query, context, passenger)
        
    try:
        # Create PromptTemplate
        prompt = PromptTemplate.from_template(SYSTEM_PROMPT)
        
        # Initialize ReAct Agent
        agent = create_react_agent(llm=_llm, tools=ALL_TOOLS, prompt=prompt)
        
        # Initialize AgentExecutor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=ALL_TOOLS,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            max_iterations=10
        )
        
        # Build the input for the agent prompt using template
        prompt_input = CONTEXT_PROMPT_TEMPLATE.format(
            graph_facts="\n".join([f"- {f}" for f in context["graph_facts"]]) if context["graph_facts"] else "- No specific knowledge graph facts retrieved.",
            semantic_chunks="\n\n".join([f"[{c['source']}] (ID: {c['id']})\n{c['document']}" for c in context["semantic_chunks"]]) if context["semantic_chunks"] else "No relevant documents found.",
            query=query,
            entities=str(context["entities"])
        )
        
        logger.info("Invoking LangChain ReAct agent...")
        res = agent_executor.invoke({"input": prompt_input})
        
        final_answer = res.get("output", "")
        intermediate_steps = res.get("intermediate_steps", [])
        
        # Format intermediate steps for frontend
        steps = []
        for action, obs in intermediate_steps:
            steps.append({
                "tool_name": action.tool,
                "tool_input": action.tool_input,
                "tool_output": str(obs)
            })
            
        # Parse PNR code and compliance status from steps or answer
        pnr_code = None
        compliant = True
        
        # Find PNR in PNR tool output
        for s in steps:
            if s["tool_name"] == "create_pnr":
                match = re.search(r"PNR Code: ([A-Z0-9]{6})", s["tool_output"])
                if match:
                    pnr_code = match.group(1)
            if s["tool_name"] == "check_policy_compliance":
                if "NON-COMPLIANT" in s["tool_output"]:
                    compliant = False
                    
        # Check final answer text if not found in steps
        if not pnr_code:
            match = re.search(r"\b([A-Z0-9]{6})\b", final_answer)
            if match:
                pnr_code = match.group(1)
        if "NON-COMPLIANT" in final_answer:
            compliant = False

        # Passenger band and policy determined at start of function
        pass
            
        flight_options = evaluate_flight_options(origin, dest, date_str, cabin_class, policy_id, band)
        if flight_options and not any(f["compliant"] for f in flight_options):
            compliant = False
            
        return {
            "answer": final_answer,
            "steps": steps,
            "graph_context": context,
            "pnr": pnr_code,
            "compliant": compliant,
            "flight_options": flight_options
        }
        
    except Exception as err:
        logger.error(f"Error during LLM agent execution: {err}. Falling back to mock agent loop.")
        return run_mock_agent(query, context, passenger)

def run_mock_agent(query: str, context: dict, passenger_name: str = None) -> dict:
    entities = context["entities"]
    passenger = passenger_name if passenger_name else (entities["passengers"][0] if entities["passengers"] else "Aryan Mehta")
    origin = entities["airports"][0] if entities["airports"] else "BOM"
    dest = entities["airports"][1] if len(entities["airports"]) > 1 else "DXB"
    date_str = parse_prompt_date(query)
        
    # Dynamically extract passenger band, cabin class, and policy
    band, cabin_class, policy_id = extract_booking_params(query, entities, passenger)
    
    steps = []
    
    # Step 1: check_active_waivers
    from agent.tools import check_active_waivers_tool, get_weather_risk_tool, search_flights_tool
    
    waiver_out = check_active_waivers_tool(origin)
    steps.append({
        "tool_name": "check_active_waivers",
        "tool_input": origin,
        "tool_output": waiver_out
    })
    
    # Step 2: get_weather_risk
    weather_out = get_weather_risk_tool(dest)
    steps.append({
        "tool_name": "get_weather_risk",
        "tool_input": dest,
        "tool_output": weather_out
    })
    
    # Step 3: search_flights
    flight_in = f"{origin}, {dest}, {date_str}, {cabin_class}"
    flight_out = search_flights_tool(flight_in)
    steps.append({
        "tool_name": "search_flights",
        "tool_input": flight_in,
        "tool_output": flight_out
    })
    
    # Get evaluated flight options
    flight_options = evaluate_flight_options(origin, dest, date_str, cabin_class, policy_id, band)
    
    # Step 4: check_policy_compliance
    if flight_options:
        first_opt = flight_options[0]
        comp_in = f"{policy_id}, {first_opt['fare_class']}, {first_opt['price_inr']}, 1, {first_opt['airline']}"
        comp_out = first_opt["compliance_details"]
    else:
        comp_in = f"{policy_id}, Y, 32000, 1, AI"
        comp_out = "NON-COMPLIANT: No flights available to check."
        
    steps.append({
        "tool_name": "check_policy_compliance",
        "tool_input": comp_in,
        "tool_output": comp_out
    })
    
    compliant = any(f["compliant"] for f in flight_options) if flight_options else False
    
    from graph.neo4j_client import get_active_waivers
    active_w = get_active_waivers(origin)
    w_details = ""
    if active_w:
        w_details = f" Note that active fee waiver(s) {', '.join([w['id'] for w in active_w])} are in effect for {origin} departures."
    
    # Summarise surge status for the answer
    from scheduler import get_single_forecast
    surge_summary = ""
    try:
        fc = get_single_forecast(origin.upper(), dest.upper())
        if fc and fc.get("surge_multiplier", 1.0) > 1.0:
            surge_summary = (
                f"\n\n⚡ **Surge Pricing Active**: High demand detected on the {origin}→{dest} route "
                f"(Demand Tier: **{fc['tier']}**, Score: **{fc['score']:.0f}**, Trend: **{fc['trend']}**). "
                f"A **{fc['surge_multiplier']}x multiplier** has been applied to base fares."
            )
    except Exception:
        pass

    final_ans = (
        f"I have successfully analyzed the travel booking parameters for passenger {passenger} from {origin} to {dest} on {date_str}.\n\n"
        f"1. **Waiver Check**: Checked active waivers for {origin}.{w_details}\n\n"
        f"2. **Weather Risk**: Checked destination weather for {dest}. Stability score computed.\n\n"
        f"3. **Flight Options**: Checked available flight options on {date_str} and retrieved {len(flight_options)} possible routes (including weather-resilient alternatives).{surge_summary}\n\n"
        f"4. **Compliance Status**: Evaluated flight details against corporate policy {policy_id}.\n\n"
        f"Please select your preferred itinerary option from the interactive Selector Card below to complete the booking registry."
    )
    
    return {
        "answer": final_ans,
        "steps": steps,
        "graph_context": context,
        "pnr": None,
        "compliant": compliant,
        "flight_options": flight_options
    }
