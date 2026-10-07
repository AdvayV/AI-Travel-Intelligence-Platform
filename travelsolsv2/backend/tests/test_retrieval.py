import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AGENT_MODE", "deterministic")

from agent.hybrid_retrieval import bm25_scores, fuse_rankings, retrieve_documents
from agent import graph_rag
from graph import neo4j_client as graph
from graph import pdf_ingestor as ingestion
from vector.chroma_client import ChromaClient, MockChromaClient


NETWORK_GUARD = patch("httpx.Client.request", side_effect=AssertionError("Unexpected external HTTP request"))
AGENT_ENVIRONMENT = patch.dict(os.environ, {"AGENT_MODE": "deterministic"})


def setUpModule():
    AGENT_ENVIRONMENT.start()
    NETWORK_GUARD.start()


def tearDownModule():
    NETWORK_GUARD.stop()
    AGENT_ENVIRONMENT.stop()


def memory_client():
    client = object.__new__(ChromaClient)
    client._initialized = False
    with patch("vector.chroma_client.CHROMA_AVAILABLE", False):
        client.__init__()
    return client


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.client = MockChromaClient()
        self.client.add_documents("fare_rules", ["Fare class Y refund 75 percent.", "Fare class Q is non-refundable."],
                                  ["Y", "Q"], [{}, {}])
        self.client.add_documents("corporate_policies", ["CP-001 Economy only.", "CP-002 Business allowed."],
                                  ["standard", "senior"], [{}, {}])

    def test_exact_identifier_bm25(self):
        scores = bm25_scores("CP-002", ["CP-001 Economy", "CP-002 Business"])
        self.assertEqual(scores[0], 0)
        self.assertGreater(scores[1], 0)

    def test_fusion_rewards_agreement_and_deduplicates_rank(self):
        result = fuse_rankings({"bm25": ["both", "both", "lexical"], "semantic": ["semantic", "both"]})
        self.assertGreater(result["both"]["score"], result["semantic"]["score"])
        self.assertEqual(result["lexical"]["ranks"]["bm25"], 2)

    def test_exact_fare_code_ranks_correct_document(self):
        chunks, diagnostics = retrieve_documents("Fare class Q refund", self.client)
        self.assertEqual(chunks[0]["id"], "Q")
        self.assertEqual(diagnostics["document_mode"], "lexical_only")
        self.assertIn("bm25", chunks[0]["retrieval"]["ranks"])

    def test_no_evidence_does_not_force_top_k(self):
        chunks, diagnostics = retrieve_documents("quasar telescope astrophysics", self.client)
        self.assertEqual(chunks, [])
        self.assertEqual(diagnostics["selected_count"], 0)

    def test_semantic_synonym_without_keyword_overlap(self):
        self.client.add_documents("policy_documents", ["Cancellations are refundable."], ["refund"], [{"page": 2}])
        result = {"id": "refund", "document": "Cancellations are refundable.", "metadata": {"page": 2},
                  "distance": 0.3, "similarity": 0.7, "retrieval_method": "semantic"}
        with patch.object(self.client, "query", side_effect=lambda name, *args, **kwargs: [result] if name == "policy_documents" else []):
            chunks, diagnostics = retrieve_documents("money back", self.client)
        self.assertEqual(chunks[0]["id"], "refund")
        self.assertEqual(chunks[0]["retrieval"]["bm25_score"], 0)
        self.assertEqual(diagnostics["document_mode"], "hybrid")

    def test_distant_semantic_match_is_rejected(self):
        result = {"id": "Y", "distance": 1.9, "similarity": 0.05, "retrieval_method": "semantic"}
        with patch.object(self.client, "query", return_value=[result]):
            chunks, _ = retrieve_documents("astrophysics", self.client)
        self.assertEqual(chunks, [])

    def test_cross_collection_duplicates_are_removed(self):
        self.client.add_documents("policy_documents", ["CP-002 Business allowed."], ["duplicate"], [{"page": 4}])
        chunks, _ = retrieve_documents("CP-002 Business", self.client)
        contents = [" ".join(chunk["document"].lower().split()) for chunk in chunks]
        self.assertEqual(len(contents), len(set(contents)))
        self.assertTrue(any(chunk["duplicates"] for chunk in chunks))

    def test_context_budget_and_provenance(self):
        chunks, diagnostics = retrieve_documents("fare refund policy Business", self.client, limit=2, max_chars=35)
        self.assertLessEqual(len(chunks), 2)
        self.assertLessEqual(sum(len(chunk["document"]) for chunk in chunks), 35)
        self.assertLessEqual(diagnostics["context_chars"], 35)
        self.assertEqual(chunks[0]["citation"], "D1")
        self.assertIn("collection", chunks[0])

    def test_structured_entity_filters_exclude_other_fare_classes(self):
        self.client.add_documents("fare_rules", ["Fare Q refund", "Fare Y refund"], ["q2", "y2"],
                                  [{"fare_class": "Q"}, {"fare_class": "Y"}])
        chunks, _ = retrieve_documents("refund fare class Q", self.client, {"fare_classes": ["Q"]})
        self.assertFalse(any(chunk["id"] == "y2" for chunk in chunks))

    def test_failed_dense_search_preserves_lexical_results(self):
        with patch.object(self.client, "query", side_effect=RuntimeError("offline")):
            chunks, diagnostics = retrieve_documents("CP-002", self.client)
        self.assertEqual(chunks[0]["id"], "senior")
        self.assertTrue(diagnostics["warnings"])


class VectorStoreTests(unittest.TestCase):
    def test_upsert_updates_existing_document(self):
        client = memory_client()
        client.add_documents("policy_documents", ["old"], ["same"], [{"source": "policy"}])
        client.add_documents("policy_documents", ["new"], ["same"], [{"source": "policy"}])
        self.assertEqual(client.get_documents("policy_documents")[0]["document"], "new")
        self.assertEqual(client.get_or_create_collection("policy_documents").count(), 1)

    def test_replace_removes_stale_chunks_only_for_source(self):
        client = memory_client()
        client.add_documents("policy_documents", ["old", "other"], ["old", "other"],
                             [{"source": "policy"}, {"source": "other"}])
        result = client.replace_documents("policy_documents", "policy", ["new"], ["new"], [{"source": "policy"}])
        self.assertFalse(result["persisted"])
        self.assertEqual({item["id"] for item in client.get_documents("policy_documents")}, {"other", "new"})

    def test_empty_collection_is_safe(self):
        self.assertEqual(memory_client().query("empty", "policy", 10), [])

    def test_semantic_distances_and_clamped_result_count(self):
        client = memory_client()
        client.use_mock = False
        collection = MagicMock()
        collection.count.return_value = 1
        collection.metadata = {"hnsw:space": "cosine"}
        collection.query.return_value = {"ids": [["one"]], "documents": [["policy"]],
                                         "metadatas": [[{}]], "distances": [[0.2]]}
        with patch.object(client, "get_or_create_collection", return_value=collection):
            result = client.query("policy_documents", "policy", 10)
        self.assertAlmostEqual(result[0]["similarity"], 0.8)
        self.assertEqual(collection.query.call_args.kwargs["n_results"], 1)
        self.assertIn("distances", collection.query.call_args.kwargs["include"])

    def test_metric_comes_from_configuration_when_metadata_is_absent(self):
        client = memory_client()
        client.use_mock = False
        collection = MagicMock()
        collection.count.return_value = 1
        collection.metadata = None
        collection.configuration_json = {"hnsw": {"space": "cosine"}}
        collection.query.return_value = {"ids": [["one"]], "documents": [["policy"]],
                                         "metadatas": [[{}]], "distances": [[0.85]]}
        with patch.object(client, "get_or_create_collection", return_value=collection):
            result = client.query("policy_documents", "unrelated query")
        self.assertAlmostEqual(result[0]["similarity"], 0.15)

    def test_mismatched_document_arrays_are_rejected(self):
        with self.assertRaises(ValueError):
            memory_client().add_documents("policy_documents", ["one"], [], [])

    def test_query_failure_does_not_destroy_other_collections(self):
        client = memory_client()
        client.add_documents("policy_documents", ["refund"], ["one"], [{}])
        client.use_mock = False
        with patch.object(client, "get_or_create_collection", side_effect=RuntimeError("locked")):
            results = client.query("policy_documents", "refund")
        self.assertEqual(results[0]["retrieval_method"], "keyword")
        self.assertFalse(client.use_mock)


class GraphTests(unittest.TestCase):
    def test_waiver_validity_and_scope(self):
        waiver = {"valid_from": "2026-06-01", "valid_until": "2026-07-31", "applies_to": ["BOM-DXB"]}
        self.assertTrue(graph._waiver_applies(waiver, "BOM", "DXB", "2026-07-01"))
        self.assertFalse(graph._waiver_applies(waiver, "BOM", "DXB", "2026-10-07"))
        self.assertFalse(graph._waiver_applies(waiver, "BOM", "DXB", "2026-05-01"))
        self.assertFalse(graph._waiver_applies(waiver, "BOM", "SIN", "2026-07-01"))
        self.assertFalse(graph._waiver_applies({**waiver, "requires_code": True}, "BOM", "DXB", "2026-07-01"))

    def test_live_empty_waivers_do_not_reintroduce_mocks(self):
        with patch.object(graph, "get_driver", return_value=object()), patch.object(graph, "run_query", return_value=[]), \
             patch.object(graph, "_get_mock_waivers", side_effect=AssertionError("Must not use mocks")):
            self.assertEqual(graph.get_active_waivers("BOM"), [])

    def test_live_missing_route_is_not_invented(self):
        with patch.object(graph, "get_driver", return_value=object()), patch.object(graph, "run_query", return_value=[]):
            self.assertEqual(graph.get_route_info("BOM", "XXX", strict=True), {})

    def test_strict_query_propagates_database_failure(self):
        driver = MagicMock()
        driver.session.return_value.__enter__.return_value.run.side_effect = RuntimeError("offline")
        with patch.object(graph, "get_driver", return_value=driver):
            with self.assertRaises(RuntimeError):
                graph.run_query("RETURN 1", strict=True)

    def test_strict_query_rejects_mock_mode(self):
        with patch.object(graph, "get_driver", return_value=None):
            with self.assertRaises(ConnectionError):
                graph.run_query("RETURN 1", strict=True)


class IngestionTests(unittest.TestCase):
    def test_seeded_document_loading_is_idempotent(self):
        from vector import document_loader
        client = memory_client()
        with patch.object(document_loader, "ChromaClient", return_value=client):
            document_loader.load_documents()
            first = {name: client.get_or_create_collection(name).count()
                     for name in ("fare_rules", "corporate_policies", "irops_history")}
            document_loader.load_documents()
        self.assertEqual(first, {"fare_rules": 9, "corporate_policies": 4, "irops_history": 10})
        self.assertEqual(first, {name: client.get_or_create_collection(name).count() for name in first})

    def test_configured_policy_documents_match_graph_seed_definitions(self):
        from graph.seed_data import SEED_DATA
        from vector import document_loader
        client = memory_client()
        with patch.object(document_loader, "ChromaClient", return_value=client):
            document_loader.load_documents()
        documents = {item["id"]: item["document"] for item in client.get_documents("corporate_policies")}
        for policy in SEED_DATA["corporate_policies"]:
            document = documents[f"CONFIGURED_{policy['id']}"]
            self.assertIn(str(policy["max_fare_inr"]), document)
            self.assertIn(f"{policy['min_advance_days']} days", document)

    def test_chunking_is_bounded_and_preserves_pages(self):
        chunks = ingestion.chunk_text("[PAGE 1]\n" + "word " * 400 + "\n[PAGE 2]\nGrade 9 First class.", 200, 40)
        self.assertTrue(all(0 < len(chunk["text"]) <= 200 for chunk in chunks))
        self.assertEqual(chunks[-1]["page_hint"], 2)
        self.assertTrue(all(chunk["page_hint"] == 1 for chunk in chunks[:-1]))
        self.assertEqual(len({chunk["id"] for chunk in chunks}), len(chunks))

    def test_invalid_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            ingestion.chunk_text("policy", 100, 100)

    def test_disconnected_graph_ingestion_reports_false(self):
        with patch.object(graph, "get_driver", return_value=None):
            self.assertFalse(ingestion._write_to_neo4j("policy", [], {}))

    def test_graph_rules_are_document_scoped_and_strict(self):
        chunks = [{"id": "chunk-0000", "text": "Corporate policy information. " * 5, "page_hint": 1, "chunk_index": 0}]
        with patch.object(graph, "get_driver", return_value=object()), patch.object(graph, "run_query", return_value=[]) as execute:
            self.assertTrue(ingestion._write_to_neo4j("first", chunks, {}))
        self.assertTrue(all(call.kwargs.get("strict") is True for call in execute.call_args_list))
        self.assertTrue(any(len(call.args) > 1 and (call.args[1] or {}).get("id") == "RULE-first-chunk-0000" for call in execute.call_args_list))


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.client = memory_client()
        self.client.add_documents("policy_documents", ["Grade 9 may use First Class."], ["policy-chunk-0000"],
                                  [{"source": "policy", "chunk_index": 0, "page": 3}])

    def test_entity_parser_handles_lowercase_fare_class(self):
        self.assertIn("Q", graph_rag.detect_entities("What is the refund for fare class q?")["fare_classes"])

    def test_explicit_grade_and_passenger_are_consistent(self):
        with patch.object(graph_rag, "get_driver", return_value=None), patch.object(graph_rag, "ChromaClient", return_value=self.client), \
             patch.object(graph_rag, "get_corporate_policy", return_value={}):
            context = graph_rag.retrieve_context("What is the policy for grade 9?", "Aryan Mehta")
        self.assertEqual(context["entities"]["policies"], ["CP-003"])
        self.assertEqual(context["retrieval"]["graph_mode"], "mock")
        self.assertTrue(any("Grade 9" in fact for fact in context["graph_facts"]))
        self.assertIn("[D1]", context["combined_context"])

    def test_graph_failure_is_disclosed_without_mock_substitution(self):
        with patch.object(graph_rag, "get_driver", return_value=object()), patch.object(graph_rag, "ChromaClient", return_value=self.client), \
             patch.object(graph_rag, "get_corporate_policy", side_effect=RuntimeError("offline")), \
             patch.object(graph_rag, "run_query", side_effect=RuntimeError("offline")):
            context = graph_rag.retrieve_context("What is CP-003 policy?")
        self.assertEqual(context["retrieval"]["graph_mode"], "degraded")
        self.assertFalse(any(source["source"] == "mock_graph" for source in context["graph_sources"]))
        self.assertTrue(context["retrieval"]["warnings"])

    def test_information_answer_uses_evidence_without_flight_search(self):
        from agent import booking_agent
        context = {"request_kind": "information", "entities": {}, "combined_context": "evidence",
                   "graph_sources": [], "retrieval": {"warnings": []},
                   "semantic_chunks": [{"citation": "D1", "source": "PDF POLICY", "id": "one",
                                        "document": "Grade 9 may use First Class.", "metadata": {"page": 3}}]}
        with patch.object(booking_agent, "retrieve_context", return_value=context), \
             patch.object(booking_agent, "evaluate_flight_options", side_effect=AssertionError("No flight search")):
            result = booking_agent.run_booking_agent("What can grade 9 use?")
        self.assertIn("[D1]", result["answer"])
        self.assertIn("Grade 9 may use First Class.", result["answer"])
        self.assertEqual(result["flight_options"], [])
        self.assertIsNone(result["pnr"])


if __name__ == "__main__":
    unittest.main()
