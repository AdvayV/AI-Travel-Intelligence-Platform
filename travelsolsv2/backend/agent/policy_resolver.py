import re


PASSENGER_GRADES = {
    "Aryan Mehta": 7,
    "Priya Sharma": 4,
    "Rajesh Kumar": 8,
    "Anita Singh": 3,
    "Vikram Nair": 9,
}

LONG_HAUL_DESTINATIONS = {"LHR", "JFK", "SYD", "CDG", "NRT", "LAX", "SFO", "YYZ"}
GRADE_PATTERN = re.compile(r"\b(?:grade|band|level)\s*[-:]?\s*([1-9])\b", re.IGNORECASE)


def extract_employee_grade(query: str) -> int | None:
    match = GRADE_PATTERN.search(query)
    return int(match.group(1)) if match else None


def policy_id_for_grade(grade: int) -> str:
    if grade <= 5:
        return "CP-001"
    if grade <= 8:
        return "CP-002"
    return "CP-003"


def _requested_cabin(query: str) -> str | None:
    query_lower = query.lower()
    if re.search(r"\bfirst(?:\s+class)?\b", query_lower):
        return "FIRST"
    if re.search(r"\bbusiness(?:\s+class)?\b", query_lower):
        return "BUSINESS"
    if re.search(r"\bpremium\s+economy\b", query_lower):
        return "PREMIUM_ECONOMY"
    if re.search(r"\beconomy(?:\s+class)?\b", query_lower):
        return "ECONOMY"
    return None


def resolve_booking_policy(query: str, entities: dict, passenger: str | None = None) -> dict:
    explicit_grade = extract_employee_grade(query)
    grade = explicit_grade or PASSENGER_GRADES.get((passenger or "").strip(), 5)
    destination = (
        entities.get("airports", [None, "DXB"])[1]
        if len(entities.get("airports", [])) > 1
        else "DXB"
    )
    is_long_haul = destination.upper() in LONG_HAUL_DESTINATIONS

    if grade <= 5:
        allowed_cabins = ["ECONOMY"]
        default_cabin = "ECONOMY"
        cabin_reason = f"Grade {grade} follows CP-001 and is restricted to Economy on every route."
    elif grade <= 7:
        allowed_cabins = ["ECONOMY", "BUSINESS"] if is_long_haul else ["ECONOMY"]
        default_cabin = "BUSINESS" if is_long_haul else "ECONOMY"
        cabin_reason = (
            f"Grade {grade} may use Business because {destination} is a long-haul destination."
            if is_long_haul
            else f"Grade {grade} uses Economy because Business is reserved for long-haul travel."
        )
    elif grade == 8:
        allowed_cabins = ["ECONOMY", "BUSINESS"]
        default_cabin = "BUSINESS"
        cabin_reason = "Grade 8 follows CP-002 and may use Business on all routes."
    else:
        allowed_cabins = ["ECONOMY", "BUSINESS", "FIRST"]
        default_cabin = "BUSINESS"
        cabin_reason = "Grade 9 follows CP-003; Business is the default and First is available when requested."

    requested_cabin = _requested_cabin(query)
    cabin_class = requested_cabin if requested_cabin in allowed_cabins else default_cabin
    if requested_cabin and requested_cabin in allowed_cabins:
        cabin_reason = (
            f"The requested {requested_cabin.replace('_', ' ').title()} cabin is permitted "
            f"under Grade {grade} policy."
        )
    elif requested_cabin:
        cabin_reason = (
            f"The {requested_cabin.replace('_', ' ').title()} request was adjusted to "
            f"{default_cabin.replace('_', ' ').title()} under Grade {grade} policy."
        )

    explicit_policy = bool(explicit_grade)
    existing_policies = entities.get("policies", [])
    policy_id = (
        policy_id_for_grade(grade)
        if explicit_policy or not existing_policies
        else existing_policies[0]
    )

    return {
        "employee_grade": grade,
        "grade_was_explicit": explicit_policy,
        "policy_id": policy_id,
        "cabin_class": cabin_class,
        "requested_cabin": requested_cabin,
        "allowed_cabins": allowed_cabins,
        "cabin_reason": cabin_reason,
        "is_long_haul": is_long_haul,
        "destination": destination.upper(),
    }
