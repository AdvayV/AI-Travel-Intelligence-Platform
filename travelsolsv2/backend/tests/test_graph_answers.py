import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.answer_formatter import format_graph_answer, paragraph_answer


POLICY_RECORDS = [{"policy": {"_labels": ["CorporatePolicy"], "_id": "internal-id", "id": "CP-001",
                              "name": "Standard Travel Policy", "allowed_cabins": ["ECONOMY"],
                              "allowed_fare_classes": ["Y", "M"], "max_fare_inr": 150000,
                              "min_advance_days": 7, "preferred_airlines": ["AI", "6E"],
                              "requires_approval_above_inr": 100000}}]


class GraphAnswerTests(unittest.TestCase):
    def test_policy_facts_become_readable_prose(self):
        answer = format_graph_answer("What is the standard policy?", POLICY_RECORDS)
        for fact in ("Standard Travel Policy", "CP-001", "Economy", "150,000", "7 days", "AI, 6E", "100,000"):
            self.assertIn(fact, answer)
        for raw in ("_labels", "_id", "internal-id", "allowed_cabins", "{", "}"):
            self.assertNotIn(raw, answer)

    def test_pdf_excerpts_keep_section_and_page(self):
        answer = format_graph_answer("Explain section 4.1", [{"SectionTitle": "4.1 Cabin eligibility",
                                     "PolicySnippet": "Standard employees\n must travel Economy.", "PageNumber": 3}])
        self.assertIn("4.1 Cabin eligibility: Standard employees must travel Economy.", answer)
        self.assertIn("page 3", answer)

    def test_passenger_and_linked_policy_are_both_described(self):
        answer = format_graph_answer("Who is Priya?", [{"p": {"name": "Priya Sharma", "tier": "Silver"},
                                     "r": {"_type": "HAS_POLICY", "_start": "1", "_end": "2"},
                                     "pol": POLICY_RECORDS[0]["policy"]}])
        self.assertIn("Priya Sharma", answer)
        self.assertIn("Silver", answer)
        self.assertIn("CP-001", answer)
        self.assertNotIn("HAS_POLICY", answer)

    def test_zero_and_false_are_not_omitted(self):
        answer = format_graph_answer("Count", [{"count": 0, "requires_approval": False}])
        self.assertIn("count is 0", answer)
        self.assertIn("approval is no", answer)

    def test_empty_results_do_not_invent_facts(self):
        self.assertEqual(format_graph_answer("Policy?", []), "No matching records were found in the graph for this question.")

    def test_null_rows_do_not_appear_as_json(self):
        answer = format_graph_answer("Policy?", [{"rule": None}])
        self.assertIn("no readable properties", answer)

    def test_multiple_records_and_duplicate_excerpts(self):
        rows = [{"PolicySnippet": "Economy is permitted."}, {"PolicySnippet": "Business requires eligibility."}, {"PolicySnippet": "Economy is permitted."}]
        answer = format_graph_answer("Cabin rules", rows)
        self.assertEqual(answer.count("Economy is permitted."), 1)
        self.assertIn("\n\n", answer)

    def test_truncated_summary_is_disclosed(self):
        answer = format_graph_answer("All counts", [{"count": number} for number in range(16)])
        self.assertIn("first 15 of 16", answer)

    def test_long_excerpts_are_bounded_and_marked(self):
        answer = format_graph_answer("Excerpt", [{"PolicySnippet": "Policy detail " * 1000}])
        self.assertLess(len(answer), 1300)
        self.assertIn("excerpt shortened", answer)

    def test_json_code_or_empty_generated_answer_uses_retrieved_facts(self):
        for answer in ('{"answer":"Unsupported policy"}', '[{"id":"CP-003"}]', '```json\n{}\n```',
                       'MATCH (n) RETURN n', 'Here is the response: {"policy": "CP-003"}', None, "", "42"):
            with self.subTest(answer=answer):
                result = paragraph_answer(answer, "Policy", POLICY_RECORDS)
                self.assertIn("CP-001", result)
                self.assertNotIn("Unsupported policy", result)

    def test_generated_bullets_are_normalized_to_paragraphs(self):
        answer = paragraph_answer("**Policy**\n- Economy only.\n- Book seven days ahead.", "Policy", POLICY_RECORDS)
        self.assertEqual(answer, "Policy Economy only. Book seven days ahead.")

    def test_record_count_only_answer_is_replaced_with_actual_facts(self):
        for answer in ("Found 3 records matching your query.", "Found 3 records.", "The query returned 3 rows.",
                       "Successfully executed Cypher query. Found 3 rows."):
            with self.subTest(answer=answer):
                result = paragraph_answer(answer, "Policy", POLICY_RECORDS)
                self.assertIn("Economy", result)
                self.assertIn("150,000", result)
                self.assertIn("100,000", result)
                self.assertNotIn("Found 3", result)


class NLQueryEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import main
        cls.client = TestClient(main.app)

    def request(self, results):
        def execute(query, *args, **kwargs):
            return [{"relationshipType": "HAS_POLICY"}] if query.startswith("CALL") else results
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "HUGGINGFACE_API_KEY": ""}), \
             patch("cypher_generator.generate_cypher", return_value="MATCH (p:CorporatePolicy) RETURN p"), \
             patch("graph.neo4j_client.run_query", side_effect=execute), \
             patch("agent.booking_agent._llm", None), \
             patch("httpx.HTTPTransport.handle_request", side_effect=AssertionError("Unexpected external request")):
            return self.client.post("/api/graph/query/nl", json={"question": "Explain standard travel policy"})

    def test_no_model_key_still_returns_a_fact_based_paragraph(self):
        response = self.request(POLICY_RECORDS)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Permitted cabins are Economy", response.json()["answer"])
        self.assertEqual(response.json()["results"], POLICY_RECORDS)

    def test_no_results_return_readable_empty_answer(self):
        response = self.request([])
        self.assertEqual(response.status_code, 200)
        self.assertIn("No matching records", response.json()["answer"])

    def test_blank_question_is_rejected(self):
        response = self.client.post("/api/graph/query/nl", json={"question": "  "})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
