import copy
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.policy_audit import evaluate_policy_checks
from agent.policy_resolver import resolve_booking_policy
from graph.seed_data import SEED_DATA


TODAY = date(2026, 7, 1)
POLICIES = {policy["id"]: policy for policy in SEED_DATA["corporate_policies"]}


def make_flight(origin="BOM", destination="LHR", cabin="ECONOMY", price=50000, airline="AI"):
    return {"flight_number": "AI-101", "airline": airline, "origin": origin, "destination": destination,
            "cabin_class": cabin, "fare_class": {"ECONOMY": "Y", "BUSINESS": "J", "FIRST": "F", "PREMIUM_ECONOMY": "W"}[cabin],
            "price_inr": price, "departure_time": "2026-07-15 10:00", "arrival_time": "2026-07-15 20:00",
            "duration": "10h", "stops": 0, "is_live_price": True, "fare_class_estimated": True}


class PolicyAuditTests(unittest.TestCase):
    def evaluate(self, query="grade 1", flight=None, travel_date="2026-07-15", waivers=None, policy=None):
        flight = flight or make_flight()
        decision = resolve_booking_policy(query, {"airports": [flight["origin"], flight["destination"]]}, "Aryan Mehta")
        policy = copy.deepcopy(POLICIES[decision["policy_id"]]) if policy is None else policy
        return evaluate_policy_checks(policy, decision, flight, travel_date, waivers or [], today=TODAY)

    def check(self, result, identifier):
        return next(item for item in result["decision_trail"] if item["id"] == identifier)

    def test_grade_mapping_and_default_cabins(self):
        for grade, destination, cabin, policy in [(1, "LHR", "ECONOMY", "CP-001"), (5, "DXB", "ECONOMY", "CP-001"),
                                                  (6, "DXB", "ECONOMY", "CP-002"), (7, "LHR", "BUSINESS", "CP-002"),
                                                  (8, "DXB", "BUSINESS", "CP-002"), (9, "LHR", "BUSINESS", "CP-003")]:
            with self.subTest(grade=grade, destination=destination):
                decision = resolve_booking_policy(f"grade {grade}", {"airports": ["BOM", destination]})
                self.assertEqual((decision["cabin_class"], decision["policy_id"]), (cabin, policy))
                result = self.evaluate(f"grade {grade}", make_flight(destination=destination, cabin=cabin))
                self.assertEqual(result["policy_status"], "COMPLIANT")
                self.assertIn(policy, self.check(result, "grade")["observed"])

    def test_disallowed_request_adjustment_is_explained(self):
        result = self.evaluate("business class grade 1")
        self.assertEqual(self.check(result, "cabin")["status"], "adjusted")
        self.assertIn("Requested: BUSINESS", self.check(result, "cabin")["observed"])

    def test_returned_disallowed_cabin_is_rejected(self):
        result = self.evaluate(flight=make_flight(cabin="BUSINESS"))
        self.assertFalse(result["compliant"])
        self.assertEqual(self.check(result, "cabin")["status"], "fail")

    def test_grade_seven_short_haul_business_is_rejected(self):
        self.assertFalse(self.evaluate("grade 7", make_flight(destination="DXB", cabin="BUSINESS"))["compliant"])

    def test_grade_eight_first_is_rejected_and_grade_nine_first_allowed(self):
        flight = make_flight(cabin="FIRST")
        self.assertFalse(self.evaluate("first class grade 8", flight)["compliant"])
        self.assertTrue(self.evaluate("first class grade 9", flight)["compliant"])

    def test_estimated_fare_code_is_not_claimed_verified(self):
        result = self.evaluate()
        self.assertEqual(self.check(result, "fare_class")["status"], "warning")
        self.assertIn("not verified", self.check(result, "fare_class")["detail"])

    def test_unknown_fare_code_is_rejected(self):
        flight = make_flight()
        flight["fare_class"] = "Z"
        self.assertFalse(self.evaluate(flight=flight)["compliant"])

    def test_price_threshold_and_cap_are_distinct(self):
        result = self.evaluate(flight=make_flight(price=120000))
        self.assertTrue(result["compliant"])
        self.assertEqual(result["policy_status"], "APPROVAL_REQUIRED")
        self.assertEqual(result["approval_requirements"][0]["role"], "Executive")
        blocked = self.evaluate(flight=make_flight(price=160000))
        self.assertEqual(blocked["policy_status"], "NON_COMPLIANT")
        self.assertEqual(self.check(blocked, "price")["status"], "fail")

    def test_threshold_boundary_does_not_require_approval(self):
        self.assertFalse(self.evaluate(flight=make_flight(price=100000))["requires_approval"])

    def test_nonpreferred_carrier_reason_is_visible(self):
        result = self.evaluate(flight=make_flight(airline="BA"))
        self.assertEqual(result["approval_requirements"][0]["role"], "Line manager")
        self.assertIn("BA", self.check(result, "carrier")["detail"])

    def test_short_notice_requires_vp_approval(self):
        result = self.evaluate(travel_date="2026-07-03")
        self.assertEqual(self.check(result, "advance")["status"], "approval")
        self.assertEqual(result["approval_requirements"][0]["role"], "VP")

    def test_waiver_and_nonpreferred_approval_both_remain_visible(self):
        result = self.evaluate(flight=make_flight(airline="BA"), travel_date="2026-07-03", waivers=[{"id": "WX-2026-INDIA"}])
        self.assertEqual(self.check(result, "advance")["status"], "waiver")
        self.assertEqual(result["policy_status"], "APPROVAL_REQUIRED")
        self.assertTrue(result["waiver_exceptions"])

    def test_cp_two_destination_exception_is_explicit(self):
        result = self.evaluate("grade 7", make_flight(cabin="BUSINESS"), travel_date="2026-07-02")
        self.assertEqual(self.check(result, "advance")["status"], "waiver")
        self.assertIn("LHR/JFK", self.check(result, "advance")["detail"])

    def test_past_and_invalid_dates_are_not_treated_as_seven_days_ahead(self):
        for travel_date in ("2026-06-30", "invalid"):
            with self.subTest(travel_date=travel_date):
                result = self.evaluate(travel_date=travel_date)
                self.assertFalse(result["compliant"])
                self.assertEqual(self.check(result, "date")["status"], "fail")

    def test_missing_policy_fails_closed_without_fabricated_approval(self):
        result = self.evaluate(policy={})
        self.assertFalse(result["compliant"])
        self.assertEqual(self.check(result, "policy")["status"], "fail")
        self.assertEqual(result["approval_requirements"], [])

    def test_every_step_has_rule_observation_source_and_result(self):
        result = self.evaluate()
        self.assertEqual(len({check["id"] for check in result["decision_trail"]}), len(result["decision_trail"]))
        for check in result["decision_trail"]:
            self.assertTrue(all(check[key] for key in ("rule", "observed", "source", "detail", "status")))


class EvaluationIntegrationTests(unittest.TestCase):
    def run_evaluation(self, flights, *, weather=None, waivers=None):
        from agent.booking_agent import evaluate_flight_options
        travel_date = (date.today() + timedelta(days=14)).isoformat()
        decision = resolve_booking_policy("grade 1", {"airports": ["BOM", "LHR"]})
        with patch("travel.flight_search.search_flights_api", side_effect=lambda origin, *args: flights.get(origin, [])), \
             patch("graph.neo4j_client.get_driver", return_value=object()), \
             patch("graph.neo4j_client.get_corporate_policy", return_value=POLICIES["CP-001"]), \
             patch("graph.neo4j_client.get_active_waivers", side_effect=waivers or (lambda *args, **kwargs: [])), \
             patch("scheduler.get_single_forecast", return_value=None), \
             patch("weather_client.get_weather_detail", return_value=weather or {"overall_appeal": 1.0}):
            return evaluate_flight_options("BOM", "LHR", travel_date, "ECONOMY", "CP-001", 1, decision)

    def test_primary_and_alternative_use_same_audit_even_without_primary_results(self):
        result = self.run_evaluation({"BLR": [make_flight(origin="BLR", airline="BA")]}, weather={"overall_appeal": 0.2})
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["is_alternative"])
        self.assertEqual(result[0]["policy_status"], "APPROVAL_REQUIRED")
        self.assertEqual(result[0]["policy_context"]["origin"], "BLR")
        self.assertTrue(result[0]["decision_trail"])

    def test_live_price_is_not_discounted_and_input_is_not_mutated(self):
        flight = make_flight(price=120000)
        original = copy.deepcopy(flight)
        result = self.run_evaluation({"BOM": [flight]}, waivers=lambda *args, **kwargs: [{"id": "CORP-AI-ANNUAL"}])
        self.assertEqual(result[0]["price_inr"], 120000)
        self.assertEqual(flight, original)
        self.assertIn("120,000", next(item for item in result[0]["decision_trail"] if item["id"] == "price")["observed"])

    def test_demo_discount_is_evaluated_before_approval_threshold(self):
        flight = make_flight(price=110000)
        flight["is_live_price"] = False
        result = self.run_evaluation({"BOM": [flight]}, waivers=lambda *args, **kwargs: [{"id": "CORP-AI-ANNUAL"}])
        self.assertEqual(result[0]["price_inr"], 96800)
        self.assertFalse(result[0]["requires_approval"])

    def test_waiver_failure_is_disclosed_in_trail(self):
        result = self.run_evaluation({"BOM": [make_flight()]}, waivers=RuntimeError("offline"))
        check = next(item for item in result[0]["decision_trail"] if item["id"] == "waivers")
        self.assertEqual(check["status"], "warning")
        self.assertIn("failed", check["detail"])


if __name__ == "__main__":
    unittest.main()
