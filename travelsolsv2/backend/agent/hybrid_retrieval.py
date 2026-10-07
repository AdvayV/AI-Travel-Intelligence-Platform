import math
import re
from collections import Counter


COLLECTION_LABELS = {
    "fare_rules": "FARE RULE",
    "corporate_policies": "POLICY",
    "irops_history": "IROPS",
    "policy_documents": "PDF POLICY",
}
STOP_WORDS = set("a an and are as at be by can do does for from how i in is it me my of on or please the this to what when which with would".split())


def tokenize(text: str) -> list[str]:
    return [term for term in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()) if term not in STOP_WORDS]


def bm25_scores(query: str, documents: list[str]) -> list[float]:
    tokens = [tokenize(document) for document in documents]
    if not tokens:
        return []
    frequencies = [Counter(terms) for terms in tokens]
    average_length = sum(map(len, tokens)) / len(tokens) or 1
    scores = [0.0] * len(tokens)
    for term in set(tokenize(query)):
        containing = sum(term in frequency for frequency in frequencies)
        inverse_frequency = math.log(1 + (len(tokens) - containing + 0.5) / (containing + 0.5))
        for index, frequency in enumerate(frequencies):
            count = frequency[term]
            normalization = 1.2 * (0.25 + 0.75 * len(tokens[index]) / average_length)
            scores[index] += inverse_frequency * count * 2.2 / (count + normalization)
    return scores


def fuse_rankings(rankings: dict[str, list[str]], constant: int = 60) -> dict[str, dict]:
    fused = {}
    for method, identifiers in rankings.items():
        for rank, identifier in enumerate(dict.fromkeys(identifiers), 1):
            entry = fused.setdefault(identifier, {"score": 0.0, "ranks": {}})
            entry["score"] += 1 / (constant + rank)
            entry["ranks"][method] = rank
    return fused


def expanded_query(query: str, entities: dict) -> str:
    identifiers = []
    for field in ("airports", "airlines", "policies", "fare_classes", "waivers"):
        identifiers.extend(entities.get(field, []))
    return " ".join([query.strip(), *dict.fromkeys(identifiers)]).strip()


def retrieve_documents(query: str, client, entities: dict | None = None,
                       collections=None, limit: int = 6, max_chars: int = 6500) -> tuple[list[dict], dict]:
    search_query = expanded_query(query, entities or {})
    entities = entities or {}
    corpus = {}
    dense_candidates = {}
    warnings = []
    semantic_collections = []
    for collection in collections or COLLECTION_LABELS:
        try:
            documents = client.get_documents(collection)
        except Exception:
            warnings.append(f"Cannot read collection {collection}.")
            continue
        for item in documents:
            metadata = item.get("metadata", {})
            if collection == "fare_rules" and entities.get("fare_classes") and metadata.get("fare_class"):
                if metadata["fare_class"] not in entities["fare_classes"]:
                    continue
            if collection == "corporate_policies" and entities.get("policies") and metadata.get("type") == "configured_policy":
                if metadata.get("policy_id") not in entities["policies"]:
                    continue
            key = f"{collection}:{item['id']}"
            corpus[key] = {**item, "collection": collection, "source": COLLECTION_LABELS[collection]}
        if not documents:
            continue
        try:
            results = client.query(collection, search_query, n_results=min(8, len(documents)))
            for item in results:
                distance = item.get("distance")
                similarity = item.get("similarity")
                if item.get("retrieval_method") == "semantic" and distance is not None:
                    if similarity is not None and similarity >= 0.25:
                        dense_candidates[f"{collection}:{item['id']}"] = item
            if any(item.get("retrieval_method") == "semantic" for item in results):
                semantic_collections.append(collection)
            else:
                warnings.append(f"Semantic search unavailable for {collection}; using BM25.")
        except Exception:
            warnings.append(f"Semantic search failed for {collection}; using BM25.")

    keys = list(corpus)
    scores = bm25_scores(search_query, [
        corpus[key]["document"] + " " + str(corpus[key].get("metadata", {})) for key in keys
    ])
    lexical_scores = dict(zip(keys, scores))
    lexical = sorted((key for key in keys if lexical_scores[key] > 0),
                     key=lambda key: (-lexical_scores[key], key))[:16]
    dense = sorted((key for key in dense_candidates if key in corpus),
                   key=lambda key: (-dense_candidates[key]["similarity"], key))[:16]
    fused = fuse_rankings({"bm25": lexical, "semantic": dense})
    ordered = sorted(fused, key=lambda key: (-fused[key]["score"], -lexical_scores[key], key))
    chunks = []
    fingerprints = {}
    used_chars = 0
    for key in ordered:
        item = corpus[key]
        fingerprint = " ".join(item["document"].lower().split())
        if fingerprint in fingerprints:
            fingerprints[fingerprint]["duplicates"].append({"collection": item["collection"], "id": item["id"]})
            continue
        if len(chunks) >= limit or used_chars >= max_chars:
            continue
        excerpt = item["document"][:min(1800, max_chars - used_chars)]
        chunk = {
            **item, "document": excerpt, "citation": f"D{len(chunks) + 1}",
            "truncated": len(excerpt) < len(item["document"]), "duplicates": [],
            "retrieval": {
                "rrf_score": round(fused[key]["score"], 6),
                "bm25_score": round(lexical_scores[key], 6),
                "distance": dense_candidates.get(key, {}).get("distance"),
                "ranks": fused[key]["ranks"],
            },
        }
        chunks.append(chunk)
        fingerprints[fingerprint] = chunk
        used_chars += len(excerpt)
    if not chunks:
        warnings.append("No relevant document evidence found within the relevance gate.")
    return chunks, {
        "strategy": "graph + semantic + BM25 (reciprocal rank fusion)",
        "search_query": search_query,
        "document_mode": "hybrid" if semantic_collections else "lexical_only",
        "semantic_collections": semantic_collections, "corpus_size": len(corpus),
        "candidate_count": len(fused), "selected_count": len(chunks),
        "context_chars": used_chars, "warnings": warnings,
    }
