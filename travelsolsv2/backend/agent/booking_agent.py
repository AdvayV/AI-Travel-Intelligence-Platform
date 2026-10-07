import os
import re
import logging
from datetime import date
from dotenv import load_dotenv
from tls_config import enable_system_trust_store
from agent.graph_rag import retrieve_context
from agent.policy_resolver import resolve_booking_policy
from agent.query_parser import parse_prompt_date
from agent.tools import ALL_TOOLS

load_dotenv()
enable_system_trust_store()

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
AGENT_MODE = os.getenv("AGENT_MODE", "deterministic").strip().lower()

logger = logging.getLogger(__name__)

# Try to import LangChain libraries, set flags to fall back to mock if not installed
try:
    from langchain_openai import ChatOpenAI
    from langchain_classic.agents import create_react_agent, AgentExecutor
    from langchain_classic.prompts import PromptTemplate
    from agent.prompts import SYSTEM_PROMPT
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain packages not installed. Running in mock deterministic mode.")

# Attempt to initialize LLM if LangChain is available
_llm = None
if AGENT_MODE == "llm" and LANGCHAIN_AVAILABLE and HUGGINGFACE_API_KEY and HUGGINGFACE_API_KEY != "your_huggingface_api_key_here":
    try:
        logger.info("Initializing Hugging Face Qwen2.5-7B-Instruct via OpenAI-compatible router...")
        _llm = ChatOpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=HUGGINGFACE_API_KEY,
            model="Qwen/Qwen2.5-7B-Instruct",
            max_tokens=600,
            temperature=0.1,
            timeout=20
        )
    except Exception as e:
        logger.error(f"Failed to initialize HuggingFace LLM: {e}. Agent will run in mock deterministic mode.")
        _llm = None
else:
    if LANGCHAIN_AVAILABLE and AGENT_MODE != "llm":
        logger.info("AGENT_MODE is deterministic; using the local policy engine without paid LLM calls.")
    elif LANGCHAIN_AVAILABLE:
        logger.warning("HUGGINGFACE_API_KEY not set. Agent will run in deterministic mode.")

def extract_booking_params(query: str, entities: dict, passenger: str = None) -> tuple:
    decision = resolve_booking_policy(query, entities, passenger)
    return decision["employee_grade"], decision["cabin_class"], decision["policy_id"]

def _display_cabin(flight: dict) -> str:
    cabin = flight.get("cabin_class", "ECONOMY")
    fare_class = flight.get("fare_class")
    if cabin == "FIRST" or fare_class == "F":
        return "First"
    if cabin == "BUSINESS" or fare_class in ["J", "C", "D"]:
        return "Business"
    if cabin == "PREMIUM_ECONOMY" or fare_class == "W":
        return "Premium Economy"
    return "Economy"


def evaluate_flight_options(
    origin: str,
    dest: str,
    travel_date: str,
    cabin_class: str,
    policy_id: str,
    band: int = None,
    policy_decision: dict = None,
) -> list:
    from travel.flight_search import search_flights_api
    from graph.neo4j_client import get_active_waivers, get_corporate_policy, get_driver
    from scheduler import get_single_forecast, recompute_forecast_for_day
    from weather_client import get_weather_detail
    from agent.policy_audit import evaluate_policy_checks

    try:
        flights = search_flights_api(origin, dest, travel_date, cabin_class)
    except Exception as error:
        logger.error("Flight search failed in evaluation: %s", error)
        flights = []

    try:
        day_offset = max(0, (date.fromisoformat(travel_date) - date.today()).days)
    except (ValueError, TypeError):
        day_offset = 0

    surge_info = None
    try:
        base_forecast = get_single_forecast(origin.upper(), dest.upper())
        forecast = recompute_forecast_for_day(base_forecast, day_offset) if base_forecast else None
        if forecast and forecast.get("surge_multiplier", 1.0) > 0:
            surge_info = {"multiplier": forecast["surge_multiplier"], "score": forecast["score"],
                          "tier": forecast["tier"], "trend": forecast["trend"]}
    except Exception as error:
        logger.warning("Could not load route forecast: %s", error)

    weather_summary = "Weather information unavailable"
    is_high_weather_risk = False
    try:
        weather = get_weather_detail(dest.upper())
        if 0 <= day_offset < len(weather.get("days", [])):
            day_weather = weather["days"][day_offset]
            weather_summary = f"{day_weather['temp_max_c']}°C, {day_weather['condition']} {day_weather['emoji']}"
            is_high_weather_risk = day_weather.get("appeal", 1.0) <= 0.4
        else:
            if weather.get("today_temp_max_c") is not None:
                weather_summary = f"{weather['today_temp_max_c']}°C, {weather.get('today_condition', '')} {weather.get('today_emoji', '')}"
            is_high_weather_risk = weather.get("overall_appeal", 1.0) <= 0.4
    except Exception as error:
        logger.warning("Could not retrieve destination weather: %s", error)

    strict = get_driver() is not None
    policy_source = "Neo4j corporate policy" if strict else "Demo policy fallback"
    try:
        policy = get_corporate_policy(policy_id, strict=strict) or {}
    except Exception as error:
        logger.error("Policy lookup failed: %s", error)
        policy = {}
        policy_source = "Neo4j lookup failed"
    decision = dict(policy_decision or resolve_booking_policy(
        f"grade {band or 5}", {"airports": [origin, dest]}))
    decision["policy_id"] = policy_id

    def route_waivers(route_origin):
        try:
            return get_active_waivers(route_origin, dest, travel_date, strict=strict), None
        except Exception as error:
            logger.error("Waiver lookup failed for %s: %s", route_origin, error)
            return [], "Waiver lookup failed; no waiver exception was assumed."

    def evaluate_offer(flight, waivers, waiver_error=None, alternative=False):
        display_class = _display_cabin(flight)
        price = flight["price_inr"]
        live_price = bool(flight.get("is_live_price"))
        surge_applied = None
        market_signal = None
        if surge_info and not alternative:
            market_signal = {**surge_info, "note": "Forecast signal only; live comparison fares are unchanged."}
            if not live_price:
                surge_applied = {"multiplier": surge_info["multiplier"], "pre_surge_price_inr": price,
                                 "reason": f"Demo forecast adjustment ({surge_info['tier']} demand tier)"}
                price = int(price * surge_info["multiplier"])
        original_price = price
        discount_applied = None
        discount_note = None
        if flight["airline"] == "AI" and any(waiver["id"] == "CORP-AI-ANNUAL" for waiver in waivers):
            if live_price:
                discount_note = "Potential 12% corporate Air India discount; verify during booking."
            else:
                price = int(price * 0.88)
                discount_applied = "12% Corporate AI Discount"

        audit_input = {**flight, "price_inr": price, "cabin_class": display_class.upper().replace(" ", "_")}
        audit = evaluate_policy_checks(policy, decision, audit_input, travel_date, waivers, policy_source=policy_source)
        if waiver_error:
            waiver_check = next(check for check in audit["decision_trail"] if check["id"] == "waivers")
            waiver_check.update({"status": "warning", "detail": waiver_error, "observed": "Eligibility could not be verified."})
        context = {**decision, "policy_name": policy.get("name", policy_id), "policy_source": policy_source,
                   "min_advance_days": policy.get("min_advance_days"), "max_fare_inr": policy.get("max_fare_inr"),
                   "requires_approval_above_inr": policy.get("requires_approval_above_inr"),
                   "preferred_airlines": policy.get("preferred_airlines", []),
                   "travel_date": travel_date, "origin": flight["origin"], "destination": dest}
        risk = "MODERATE" if is_high_weather_risk else "LOW"
        warning = "Destination weather advisory; verify conditions before travel." if is_high_weather_risk else ""
        if is_high_weather_risk and any(time in flight["departure_time"] for time in ("08:30", "09:00")):
            risk = "HIGH"
            warning = "Weather-risk advisory for this departure window; delays are not guaranteed."
        if alternative:
            warning = "Alternative departure from BLR; ground transfer is not included and route weather must be verified."
        return {**flight, **audit, "fare_class": display_class, "price_inr": price,
                "original_price_inr": original_price, "discount_applied": discount_applied,
                "discount_note": discount_note, "surge_applied": surge_applied, "market_signal": market_signal,
                "is_live_price": live_price, "disruption_risk": risk, "disruption_warning": warning,
                "weather": weather_summary, "is_alternative": alternative,
                "employee_grade": decision["employee_grade"], "policy_id": policy_id,
                "policy_name": context["policy_name"], "allowed_cabins": decision["allowed_cabins"],
                "cabin_reason": decision.get("cabin_reason"), "policy_context": context}

    waivers, waiver_error = route_waivers(origin)
    evaluated = [evaluate_offer(flight, waivers, waiver_error) for flight in flights]
    if is_high_weather_risk and origin.upper() == "BOM":
        try:
            alternatives = search_flights_api("BLR", dest, travel_date, cabin_class)
            alternate_waivers, alternate_error = route_waivers("BLR")
            evaluated.extend(evaluate_offer(flight, alternate_waivers, alternate_error, True) for flight in alternatives[:2])
        except Exception as error:
            logger.error("Alternative flight evaluation failed: %s", error)
    return evaluated

def evidence_summary(context: dict, max_documents: int = 3) -> str:
    parts = []
    for item in [source for source in context.get("graph_sources", []) if source["kind"] != "document_rule"][:4]:
        parts.append(f"[{item['citation']}] ({item['source']}) {item['text']}")
    for chunk in context.get("semantic_chunks", [])[:max_documents]:
        page = chunk["metadata"].get("page", chunk["metadata"].get("page_index", "n/a"))
        parts.append(f"[{chunk['citation']}] {chunk['source']}, {chunk['id']}, page {page}:\n"
                     f"> {chunk['document'][:600]}")
    if not parts:
        parts.append("No relevant evidence was found. I cannot establish an answer from the indexed sources.")
    warnings = context.get("retrieval", {}).get("warnings", [])
    if warnings:
        parts.append("Retrieval notices: " + " ".join(dict.fromkeys(warnings)))
    parts.append("Document excerpts are supporting evidence; configured grade/compliance rules take precedence. "
                 "Historical incidents and demo fare rules are not current airline terms or active-waiver proof.")
    return "\n\n".join(parts)


def run_booking_agent(query: str, passenger_name: str = None) -> dict:
    # 1. Retrieve GraphRAG context
    context = retrieve_context(query, passenger_name)
    if context.get("request_kind") == "information":
        return {"answer": "**Retrieved evidence**\n\n" + evidence_summary(context),
                "steps": [{"tool_name": "hybrid_retrieval", "tool_input": query,
                           "tool_output": context["combined_context"]}],
                "graph_context": context, "pnr": None, "compliant": None,
                "flight_options": [], "request_context": None, "answer_mode": "grounded_extract"}
    
    # Extract flight parameters for standard structure
    entities = context["entities"]
    passenger = passenger_name if passenger_name else (entities["passengers"][0] if entities["passengers"] else "Aryan Mehta")
    origin = entities["airports"][0] if entities["airports"] else "BOM"
    dest = entities["airports"][1] if len(entities["airports"]) > 1 else "DXB"
    date_str = parse_prompt_date(query)
    
    policy_decision = resolve_booking_policy(query, entities, passenger)
    band = policy_decision["employee_grade"]
    cabin_class = policy_decision["cabin_class"]
    policy_id = policy_decision["policy_id"]
    
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
        prompt_input = context["combined_context"] + f"\n\nUSER REQUEST:\n{query}\nEntities: {entities}"
        
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
            
        flight_options = evaluate_flight_options(
            origin,
            dest,
            date_str,
            cabin_class,
            policy_id,
            band,
            policy_decision,
        )
        if flight_options and not any(f["compliant"] for f in flight_options):
            compliant = False
            
        return {
            "answer": final_answer,
            "steps": steps,
            "graph_context": context,
            "pnr": pnr_code,
            "compliant": compliant,
            "flight_options": flight_options,
            "request_context": flight_options[0]["policy_context"] if flight_options else {
                **policy_decision,
                "origin": origin,
                "destination": dest,
                "travel_date": date_str,
            },
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
        
    policy_decision = resolve_booking_policy(query, entities, passenger)
    band = policy_decision["employee_grade"]
    cabin_class = policy_decision["cabin_class"]
    policy_id = policy_decision["policy_id"]
    
    steps = []
    
    # Step 1: check_active_waivers
    from agent.tools import check_active_waivers_tool, get_weather_risk_tool, search_flights_tool
    
    waiver_input = f"{origin}, {dest}, {date_str}"
    waiver_out = check_active_waivers_tool(waiver_input)
    steps.append({
        "tool_name": "check_active_waivers",
        "tool_input": waiver_input,
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
    flight_options = evaluate_flight_options(
        origin,
        dest,
        date_str,
        cabin_class,
        policy_id,
        band,
        policy_decision,
    )
    
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
    active_w = get_active_waivers(origin, dest, date_str)
    w_details = ""
    if active_w:
        w_details = f" Note that active fee waiver(s) {', '.join([w['id'] for w in active_w])} are in effect for {origin} departures."
    
    # Summarise the demand forecast without presenting it as a fare adjustment.
    from scheduler import get_single_forecast
    surge_summary = ""
    try:
        fc = get_single_forecast(origin.upper(), dest.upper())
        if fc and fc.get("surge_multiplier", 1.0) > 1.0:
            surge_summary = (
                f"\n\n**Illustrative Demand Outlook**: Simulated rank-index outlook on the {origin}→{dest} route "
                f"(Demand Tier: **{fc['tier']}**, Score: **{fc['score']:.0f}**, Trend: **{fc['trend']}**). "
                "This is low-confidence sample-data analytics, not measured booking demand; live observed fares are unchanged."
            )
    except Exception:
        pass

    final_ans = (
        f"I analyzed the trip for {passenger} from {origin} to {dest} on {date_str}.\n\n"
        f"**Grade & Cabin Decision**: Grade {band} maps to {policy_id}. {policy_decision['cabin_reason']}\n\n"
        f"1. **Waiver Check**: Checked active waivers for {origin}.{w_details}\n\n"
        f"2. **Weather Risk**: Checked destination weather for {dest}. Stability score computed.\n\n"
        f"3. **Flight Options**: Checked available flight options on {date_str} and retrieved {len(flight_options)} possible routes (including weather-resilient alternatives).{surge_summary}\n\n"
        f"4. **Compliance Status**: Evaluated flight details against corporate policy {policy_id}.\n\n"
        f"Please select your preferred itinerary option below to save a non-ticketing demo reference."
    )
    final_ans += "\n\n**Retrieved supporting evidence**\n\n" + evidence_summary(context, max_documents=2)
    
    return {
        "answer": final_ans,
        "steps": steps,
        "graph_context": context,
        "pnr": None,
        "compliant": compliant,
        "flight_options": flight_options,
        "request_context": flight_options[0]["policy_context"] if flight_options else {
            **policy_decision,
            "origin": origin,
            "destination": dest,
            "travel_date": date_str,
        },
    }
