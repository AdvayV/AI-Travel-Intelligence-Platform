import re
import httpx


def run():
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=60) as client:
        health = client.get("/api/health").raise_for_status().json()
        assert health["neo4j"] is True
        assert health["rag"]["vector_store"]["storage_mode"] == "persistent"
        assert health["chroma"]["policy_documents"] > 0
        assert health["agent_mode"] == "deterministic", "This smoke test must not call hosted inference."
        queries = [
            "What is the refund for fare class Q?",
            "What are the cabin rules for grade 9?",
            "What are the travel approval requirements?",
            "Find flights from Mumbai to London for grade 7 on 2026-11-01",
        ]
        linked_rules = 0
        for query in queries:
            context = client.post("/api/retrieval", json={"query": query}).raise_for_status().json()
            assert context["retrieval"]["graph_mode"] == "live", context["retrieval"]
            assert context["retrieval"]["document_mode"] == "hybrid", context["retrieval"]
            chunks = context["semantic_chunks"]
            assert 0 < len(chunks) <= 6
            assert sum(len(chunk["document"]) for chunk in chunks) <= 6500
            assert any("semantic" in chunk["retrieval"]["ranks"] for chunk in chunks)
            assert any("bm25" in chunk["retrieval"]["ranks"] for chunk in chunks)
            assert all(chunk["citation"] in context["combined_context"] for chunk in chunks)
            linked_rules += sum(source["kind"] == "document_rule" for source in context["graph_sources"])
            assert not any("WX-2026-INDIA" == source["id"] and source["kind"] == "waiver"
                           for source in context["graph_sources"])
            if "fare class Q" in query:
                assert any(chunk["id"] == "RULE_Q" for chunk in chunks[:3]), [chunk["id"] for chunk in chunks]
            if "grade 9" in query:
                assert context["entities"]["policies"] == ["CP-003"]
            if "grade 7" in query:
                assert context["entities"]["policies"] == ["CP-002"]
            print("Verified:", query, "|", len(chunks), "chunks")
        assert linked_rules > 0, "Selected PDF chunks must link back to graph rules."
        unrelated = client.post("/api/retrieval", json={"query": "quasar telescope astrophysics"}).raise_for_status().json()
        assert unrelated["semantic_chunks"] == [], "Unrelated queries must not force weak top-k hits."
        result = client.post("/api/agent/run", json={"query": queries[1]}).raise_for_status().json()
        assert result["answer_mode"] == "grounded_extract"
        assert result["flight_options"] == [] and result["pnr"] is None
        citations = set(re.findall(r"\[(?:D|G)\d+\]", result["answer"]))
        valid = {f"[{item['citation']}]" for item in result["graph_context"]["semantic_chunks"]
                 + result["graph_context"]["graph_sources"]}
        assert citations and citations <= valid
        for endpoint in ["/api/retrieval", "/api/agent/run"]:
            assert client.post(endpoint, json={"query": " "}).status_code == 400
            assert client.post(endpoint, json={"query": "x" * 4001}).status_code == 422
        assert client.get("/api/policy/search", params={"q": "approval", "n": 0}).status_code == 422
        assert client.get("/api/policy/search", params={"q": "approval", "n": 13}).status_code == 422
        policy = client.get("/api/policy/search", params={"q": "approval", "n": 4}).raise_for_status().json()
        assert policy["results"] and policy["retrieval"]["document_mode"] == "hybrid"
        proxy = httpx.post("http://127.0.0.1:5174/api/retrieval", json={"query": queries[0]}, timeout=60)
        assert proxy.status_code == 200 and proxy.json()["retrieval"]["graph_mode"] == "live"
        print("Live RAG smoke passed: fusion, graph links, citations, policy answer, validation and proxy.")
        print("No bookings, fare scraping or hosted inference submitted.")


if __name__ == "__main__":
    run()
