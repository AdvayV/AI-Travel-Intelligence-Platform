from datetime import date, datetime, timezone

from agent.policy_resolver import policy_id_for_grade


def evaluate_policy_checks(policy, decision, flight, travel_date, waivers, *, today=None, policy_source="Configured policy"):
    today = today or date.today()
    trail = []
    violations = []
    exceptions = []
    approvals = []
    grade = decision["employee_grade"]
    policy_id = decision["policy_id"]
    cabin = flight["cabin_class"].upper().replace(" ", "_")
    price = flight["price_inr"]
    fare_class = flight["fare_class"]
    destination = flight["destination"].upper()
    waiver_ids = {waiver["id"] for waiver in waivers}

    def record(identifier, title, status, rule, observed, detail, source=policy_source):
        trail.append({"id": identifier, "title": title, "status": status, "rule": rule,
                      "observed": observed, "detail": detail, "source": source})

    mapped_policy = policy_id_for_grade(grade)
    mapping_ok = policy_id == mapped_policy
    if not mapping_ok:
        violations.append(f"Grade {grade} requires {mapped_policy}, not {policy_id}")
    record("grade", "Grade to policy mapping", "pass" if mapping_ok else "fail",
           f"Grade {grade} maps to {mapped_policy}", f"Selected policy: {policy_id}",
           "Explicit grade overrides saved traveler defaults." if decision.get("grade_was_explicit")
           else "Grade resolved from the configured traveler mapping or default Grade 5.", "Local grade rules")

    policy_ok = bool(policy)
    if not policy_ok:
        violations.append(f"Corporate policy {policy_id} could not be verified")
    record("policy", "Policy lookup", "pass" if policy_ok else "fail",
           "A corporate policy must be available before compliance can be established.",
           policy.get("name", "Policy unavailable"), f"Policy record: {policy_id}.")

    allowed = [value for value in decision["allowed_cabins"] if value in policy.get("allowed_cabins", [])]
    cabin_ok = cabin in allowed
    if not cabin_ok:
        violations.append(f"Cabin {cabin} is restricted for Grade {grade} under {policy_id}")
    requested = decision.get("requested_cabin")
    record("cabin", "Cabin selection", "fail" if not cabin_ok else
           "adjusted" if requested and requested != decision["cabin_class"] else "pass",
           f"Permitted cabins: {', '.join(allowed) or 'none verified'}.",
           f"Requested: {requested or 'policy default'}; searched: {decision['cabin_class']}; returned: {cabin}.",
           decision.get("cabin_reason", "Cabin follows the grade and route rules.") +
           " Long-haul eligibility uses the configured destination list, not measured flight duration.", "Local grade rules + " + policy_source)

    record("waivers", "Applicable waiver lookup", "pass",
           "Only date-, route- and authorization-eligible waivers returned for this route may apply.",
           f"Eligible IDs: {', '.join(sorted(waiver_ids)) or 'none'}.",
           "Eligibility alone does not apply every exception; the affected checks below explain what was used.")

    allowed_fares = policy.get("allowed_fare_classes", [])
    fare_ok = fare_class in allowed_fares
    fare_waived = not fare_ok and policy_id == "CP-001" and "WX-2026-INDIA" in waiver_ids and fare_class == "Y"
    if fare_waived:
        exceptions.append("Economy fare class Y allowed under WX-2026-INDIA")
    elif not fare_ok:
        violations.append(f"Fare class {fare_class} is restricted under {policy_id}")
    estimated = bool(flight.get("fare_class_estimated"))
    record("fare_class", "Fare-class check", "waiver" if fare_waived else
           "fail" if not fare_ok else "warning" if estimated else "pass",
           f"Allowed booking codes: {', '.join(allowed_fares) or 'none verified'}.", f"Returned code: {fare_class}.",
           "Code is inferred from the cabin; airline booking-code eligibility is not verified." if estimated
           else "Booking code checked against the configured policy.")

    cap = policy.get("max_fare_inr")
    within_cap = cap is not None and 0 < price <= cap
    if not within_cap:
        violations.append(f"Price INR {price:,} exceeds or cannot satisfy the verified fare cap")
    record("price", "Maximum fare cap", "pass" if within_cap else "fail",
           f"Maximum fare: INR {cap:,}." if cap is not None else "No verified fare cap.",
           f"Evaluated fare: INR {price:,}.",
           "Observed comparison fare is unchanged." if flight.get("is_live_price")
           else "Demo estimate after any displayed forecast multiplier and applicable discount.")

    try:
        advance_days = (date.fromisoformat(travel_date) - today).days
    except (ValueError, TypeError):
        advance_days = None
    date_ok = advance_days is not None and advance_days >= 0
    if not date_ok:
        violations.append("Travel date is invalid or in the past")
    record("date", "Travel-date validation", "pass" if date_ok else "fail",
           "Travel date must be valid and not in the past.", f"Travel: {travel_date}; evaluated on: {today.isoformat()}.",
           "Dates are compared using the backend calendar date.", "Local date validation")

    minimum = policy.get("min_advance_days", 0)
    advance_status = "pass" if date_ok and advance_days >= minimum else "fail"
    advance_detail = "Advance-booking target met." if advance_status == "pass" else "Travel date cannot be evaluated."
    if date_ok and advance_days < minimum:
        if policy_id == "CP-001" and "WX-2026-INDIA" in waiver_ids and advance_days >= 2:
            advance_status = "waiver"
            advance_detail = "WX-2026-INDIA reduces the advance window to 2 days."
            exceptions.append(advance_detail)
        elif policy_id == "CP-002" and destination in {"LHR", "JFK"}:
            advance_status = "waiver"
            advance_detail = "Configured CP-002 LHR/JFK advance-window exception applies."
            exceptions.append(advance_detail)
        else:
            advance_status = "approval"
            advance_detail = f"Booked {advance_days} days ahead; VP approval required for the {minimum}-day target exception."
            approvals.append({"role": "VP", "reason": advance_detail})
    record("advance", "Advance-booking window", advance_status, f"Policy target: at least {minimum} days ahead.",
           f"Actual lead time: {advance_days} days." if advance_days is not None else "Actual lead time: unknown.", advance_detail)

    preferred = policy.get("preferred_airlines", [])
    carrier_ok = flight["airline"] in preferred
    carrier_detail = "Preferred carrier selected." if carrier_ok else f"Non-preferred airline '{flight['airline']}'; line-manager review/notification required."
    if policy_ok and not carrier_ok:
        approvals.append({"role": "Line manager", "reason": carrier_detail})
    record("carrier", "Preferred airline", "warning" if not policy_ok else "pass" if carrier_ok else "approval",
           f"Preferred carriers: {', '.join(preferred) or 'none configured'}.", f"Selected carrier: {flight['airline']}.", carrier_detail)

    threshold = policy.get("requires_approval_above_inr")
    above_threshold = threshold is not None and price > threshold
    if above_threshold:
        approvals.append({"role": "Executive", "reason": f"INR {price:,} exceeds the INR {threshold:,} approval threshold."})
    record("approval_threshold", "Fare approval threshold", "approval" if above_threshold else "pass" if threshold is not None else "warning",
           f"Executive approval when fare > INR {threshold:,}." if threshold is not None else "Approval threshold unavailable.",
           f"Evaluated fare: INR {price:,}.", "Approval does not override a hard cabin or fare-cap violation.")

    compliant = not violations
    status = "NON_COMPLIANT" if violations else "APPROVAL_REQUIRED" if approvals else "COMPLIANT"
    details = ("NON-COMPLIANT: " + "; ".join(violations) if violations else
               "CONDITIONALLY COMPLIANT: Approval required." if approvals else
               "COMPLIANT via Waiver Exception." if exceptions else "COMPLIANT: All configured checks passed.")
    if exceptions:
        details += " Waiver Exception: " + "; ".join(exceptions)
    if approvals:
        details += " " + "; ".join(item["reason"] for item in approvals)
    record("decision", "Final decision", "fail" if violations else "approval" if approvals else "pass",
           "Hard violations block compliance; approval exceptions are conditional.", status.replace("_", " "), details,
           "Deterministic policy engine")
    return {"compliant": compliant, "requires_approval": bool(approvals), "policy_status": status,
            "compliance_details": details, "decision_trail": trail, "approval_requirements": approvals,
            "waiver_exceptions": exceptions, "violations": violations,
            "evaluated_at": datetime.now(timezone.utc).isoformat()}
