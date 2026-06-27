"""
pdf_ingestor.py
---------------
Ingests a corporate travel policy PDF into:
  1. ChromaDB  — semantic RAG retrieval
  2. Neo4j     — structured knowledge graph (PolicyDocument, PolicySection,
                  PolicyRule, Approval, Employee, FareClass, Airline nodes +
                  their relationships)

Run manually:
    python -m graph.pdf_ingestor
or import and call:
    from graph.pdf_ingestor import ingest_pdf
    ingest_pdf("path/to/policy.pdf")
"""

import re
import os
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. PDF TEXT EXTRACTION
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append(f"[PAGE {i+1}]\n{text}")
        full_text = "\n\n".join(pages)
        logger.info(f"Extracted {len(full_text)} chars from {len(reader.pages)} pages in {pdf_path}")
        return full_text
    except Exception as e:
        logger.error(f"Failed to extract PDF text: {e}")
        raise


# ---------------------------------------------------------------------------
# 2. CHUNKING
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[dict]:
    """
    Split text into overlapping chunks.
    Respects paragraph / section boundaries where possible.
    Returns list of dicts: {id, text, page_hint, chunk_index}
    """
    # Split into paragraphs first
    paragraphs = re.split(r"\n{2,}", text)

    chunks = []
    current = ""
    chunk_idx = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                # Extract page hint
                page_match = re.search(r"\[PAGE (\d+)\]", current)
                page_hint = int(page_match.group(1)) if page_match else 0
                chunks.append({
                    "id": f"chunk-{chunk_idx:04d}",
                    "text": current,
                    "page_hint": page_hint,
                    "chunk_index": chunk_idx
                })
                chunk_idx += 1
                # overlap: keep last <overlap> chars from current
                current = current[-overlap:] + "\n\n" + para if overlap else para
            else:
                current = para

    # Last chunk
    if current.strip():
        page_match = re.search(r"\[PAGE (\d+)\]", current)
        page_hint = int(page_match.group(1)) if page_match else 0
        chunks.append({
            "id": f"chunk-{chunk_idx:04d}",
            "text": current,
            "page_hint": page_hint,
            "chunk_index": chunk_idx
        })

    logger.info(f"Created {len(chunks)} text chunks")
    return chunks


# ---------------------------------------------------------------------------
# 3. ENTITY EXTRACTION (rule-based, no LLM needed)
# ---------------------------------------------------------------------------

# Patterns for structured policy content
_POLICY_ID_RE    = re.compile(r"\bCP[-\s]?\d{3}\b", re.IGNORECASE)
_SECTION_RE      = re.compile(r"(?:^|\n)((?:\b\d+(?:\.\d+)*\b|Appendix\s+[A-Z]:?)\s+[A-Z][^\n]{3,70})", re.MULTILINE)
_FARE_CLASS_RE   = re.compile(r"\b([YMKQJCDG])\s*(?:class|fare)\b", re.IGNORECASE)
_AIRLINE_RE      = re.compile(r"\b(Air India|Emirates|Qatar Airways|Singapore Airlines|British Airways|IndiGo|AI|EK|QR|SQ|BA|6E)\b")
_AMOUNT_RE       = re.compile(r"INR\s*([\d,]+)", re.IGNORECASE)
_DAYS_RE         = re.compile(r"(\d+)\s*(?:business\s*)?days?\s+(?:in\s+)?advance", re.IGNORECASE)
_APPROVAL_RE     = re.compile(r"(?:requires?|needs?|must\s+have)\s+(?:manager(?:\'s)?|executive|director|HOD)?\s*approval", re.IGNORECASE)
_EMPLOYEE_TIER_RE = re.compile(r"\b(Executive|Senior\s+Management|Management|Staff|Standard|Gold|Silver|Platinum|Junior)\b", re.IGNORECASE)
_CABIN_RE        = re.compile(r"\b(Business\s+Class|Economy\s+Class|First\s+Class|Economy|Business|First)\b", re.IGNORECASE)


def extract_entities(text: str) -> dict:
    """Extract structured entities from a text chunk."""
    return {
        "policy_ids":     list(set(re.findall(_POLICY_ID_RE, text))),
        "sections":       [s.strip() for s in re.findall(_SECTION_RE, text)],
        "fare_classes":   list(set(re.findall(_FARE_CLASS_RE, text))),
        "airlines":       list(set(re.findall(_AIRLINE_RE, text))),
        "amounts_inr":    [int(a.replace(",", "")) for a in re.findall(_AMOUNT_RE, text)],
        "advance_days":   [int(d) for d in re.findall(_DAYS_RE, text)],
        "requires_approval": bool(re.search(_APPROVAL_RE, text)),
        "employee_tiers": list(set(re.findall(_EMPLOYEE_TIER_RE, text))),
        "cabins":         list(set(re.findall(_CABIN_RE, text))),
    }


# ---------------------------------------------------------------------------
# 4. NEO4J GRAPH WRITER
# ---------------------------------------------------------------------------

def _write_to_neo4j(doc_name: str, chunks: list[dict], doc_entities: dict):
    """Write PolicyDocument, PolicySection, PolicyRule nodes + relationships."""
    from graph.neo4j_client import run_query, get_driver

    driver = get_driver()
    if driver is None:
        logger.warning("Neo4j not connected — skipping graph write for PDF.")
        return

    # ── Constraint (idempotent) ──────────────────────────────────────────────
    safe_constraints = [
        "CREATE CONSTRAINT pdf_doc_name IF NOT EXISTS FOR (d:PolicyDocument) REQUIRE d.name IS UNIQUE",
        "CREATE CONSTRAINT pdf_section_id IF NOT EXISTS FOR (s:PolicySection) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT pdf_rule_id IF NOT EXISTS FOR (r:PolicyRule) REQUIRE r.id IS UNIQUE",
    ]
    for c in safe_constraints:
        try:
            run_query(c)
        except Exception:
            pass

    # ── Root: PolicyDocument node ────────────────────────────────────────────
    run_query(
        """
        MERGE (d:PolicyDocument {name: $name})
        SET d.source = $source,
            d.ingested_at = timestamp(),
            d.chunk_count = $chunks
        """,
        {"name": doc_name, "source": "PDF Upload", "chunks": len(chunks)}
    )
    logger.info(f"Created/updated PolicyDocument node: {doc_name}")

    # ── Sections and Rules from chunks ──────────────────────────────────────
    seen_sections = {}
    current_section_id = None

    for chunk in chunks:
        ents = extract_entities(chunk["text"])

        # Create PolicySection nodes for detected headings
        for section_title in ents["sections"]:
            sec_id = f"SEC-{re.sub(r'[^A-Z0-9]', '', section_title.upper())[:30]}"
            current_section_id = sec_id
            if sec_id not in seen_sections:
                seen_sections[sec_id] = section_title
                run_query(
                    """
                    MERGE (s:PolicySection {id: $id})
                    SET s.title = $title, s.document = $doc
                    WITH s
                    MATCH (d:PolicyDocument {name: $doc})
                    MERGE (d)-[:HAS_SECTION]->(s)
                    """,
                    {"id": sec_id, "title": section_title, "doc": doc_name}
                )

        # Create a PolicyRule node for each chunk that has substantive content
        if len(chunk["text"]) > 80:
            rule_id = f"RULE-{chunk['id']}"
            snippet = chunk["text"][:300].replace("\n", " ").strip()

            # Compute max fare cap from the chunk
            max_fare = max(ents["amounts_inr"]) if ents["amounts_inr"] else None
            min_advance = min(ents["advance_days"]) if ents["advance_days"] else None
            allowed_cabins = ents["cabins"][:3] if ents["cabins"] else []
            fare_classes = ents["fare_classes"][:6] if ents["fare_classes"] else []

            run_query(
                """
                MERGE (r:PolicyRule {id: $id})
                SET r.snippet      = $snippet,
                    r.page         = $page,
                    r.chunk_index  = $chunk_index,
                    r.max_fare_inr = $max_fare,
                    r.min_advance_days = $min_advance,
                    r.requires_approval = $req_approval,
                    r.allowed_cabins    = $cabins,
                    r.allowed_fare_classes = $fare_classes,
                    r.document     = $doc
                WITH r
                MATCH (d:PolicyDocument {name: $doc})
                MERGE (d)-[:CONTAINS_RULE]->(r)
                """,
                {
                    "id": rule_id,
                    "snippet": snippet,
                    "page": chunk["page_hint"],
                    "chunk_index": chunk["chunk_index"],
                    "max_fare": max_fare,
                    "min_advance": min_advance,
                    "req_approval": ents["requires_approval"],
                    "cabins": allowed_cabins,
                    "fare_classes": fare_classes,
                    "doc": doc_name
                }
            )

            # Link rule → PolicySection if there's an active section context
            if current_section_id:
                run_query(
                    """
                    MATCH (s:PolicySection {id: $sec_id})
                    MATCH (r:PolicyRule {id: $rule_id})
                    MERGE (s)-[:HAS_RULE]->(r)
                    """,
                    {"sec_id": current_section_id, "rule_id": rule_id}
                )

            # Link rule → CorporatePolicy nodes (if IDs found in chunk)
            for pid in ents["policy_ids"]:
                pid_norm = re.sub(r"\s+", "-", pid.upper())
                run_query(
                    """
                    MERGE (p:CorporatePolicy {id: $pid})
                    WITH p
                    MATCH (r:PolicyRule {id: $rule_id})
                    MERGE (r)-[:GOVERNS_POLICY]->(p)
                    """,
                    {"pid": pid_norm, "rule_id": rule_id}
                )

            # Link rule → FareClass nodes
            for fc_code in fare_classes:
                run_query(
                    """
                    MERGE (f:FareClass {code: $code})
                    WITH f
                    MATCH (r:PolicyRule {id: $rule_id})
                    MERGE (r)-[:PERMITS_FARE_CLASS]->(f)
                    """,
                    {"code": fc_code.upper(), "rule_id": rule_id}
                )

            # Link rule → Airline nodes
            airline_code_map = {
                "Air India": "AI", "Emirates": "EK", "Qatar Airways": "QR",
                "Singapore Airlines": "SQ", "British Airways": "BA", "IndiGo": "6E"
            }
            for airline_raw in ents["airlines"]:
                code = airline_code_map.get(airline_raw, airline_raw)
                run_query(
                    """
                    MERGE (a:Airline {code: $code})
                    WITH a
                    MATCH (r:PolicyRule {id: $rule_id})
                    MERGE (r)-[:PREFERRED_AIRLINE]->(a)
                    """,
                    {"code": code, "rule_id": rule_id}
                )

            # Link rule → EmployeeTier nodes
            for tier in ents["employee_tiers"]:
                tier_id = f"TIER-{tier.upper().replace(' ', '_')}"
                run_query(
                    """
                    MERGE (t:EmployeeTier {id: $tid})
                    SET t.name = $name
                    WITH t
                    MATCH (r:PolicyRule {id: $rule_id})
                    MERGE (t)-[:GOVERNED_BY]->(r)
                    """,
                    {"tid": tier_id, "name": tier.title(), "rule_id": rule_id}
                )

    logger.info(f"Graph write complete: {len(chunks)} rules, {len(seen_sections)} sections")


# ---------------------------------------------------------------------------
# 5. CHROMADB VECTOR INDEXER
# ---------------------------------------------------------------------------

def _index_to_chroma(doc_name: str, chunks: list[dict], collection_name: str = "policy_documents"):
    """Add all chunks to the ChromaDB collection for semantic RAG."""
    from vector.chroma_client import ChromaClient

    client = ChromaClient()
    docs, ids, metadatas = [], [], []

    for chunk in chunks:
        ents = extract_entities(chunk["text"])
        docs.append(chunk["text"])
        ids.append(f"{doc_name}-{chunk['id']}")
        metadatas.append({
            "source": doc_name,
            "page": chunk["page_hint"],
            "chunk_index": chunk["chunk_index"],
            "policy_ids": ", ".join(ents["policy_ids"]),
            "requires_approval": str(ents["requires_approval"]),
            "max_fare_inr": str(max(ents["amounts_inr"])) if ents["amounts_inr"] else "N/A",
        })

    client.add_documents(collection_name, docs, ids, metadatas)
    logger.info(f"Indexed {len(docs)} chunks into ChromaDB collection '{collection_name}'")


# ---------------------------------------------------------------------------
# 6. MAIN ENTRYPOINT
# ---------------------------------------------------------------------------

def ingest_pdf(pdf_path: str, collection_name: str = "policy_documents") -> dict:
    """
    Full pipeline: PDF → text → chunks → ChromaDB + Neo4j.
    Returns a summary dict.
    """
    pdf_path = str(Path(pdf_path).resolve())
    doc_name = Path(pdf_path).stem  # e.g. "corporate_travel_policy"

    logger.info(f"=== Starting PDF ingestion: {doc_name} ===")

    # Step 1: Extract text
    text = extract_text_from_pdf(pdf_path)

    # Step 2: Chunk
    chunks = chunk_text(text, chunk_size=600, overlap=100)

    # Step 3: Overall doc-level entity summary (for logging)
    doc_entities = extract_entities(text[:5000])

    # Step 4: Index into ChromaDB
    try:
        _index_to_chroma(doc_name, chunks, collection_name)
        chroma_ok = True
    except Exception as e:
        logger.error(f"ChromaDB indexing failed: {e}")
        chroma_ok = False

    # Step 5: Write to Neo4j
    try:
        _write_to_neo4j(doc_name, chunks, doc_entities)
        neo4j_ok = True
    except Exception as e:
        logger.error(f"Neo4j write failed: {e}")
        neo4j_ok = False

    summary = {
        "document": doc_name,
        "pages": text.count("[PAGE "),
        "chunks": len(chunks),
        "chroma_indexed": chroma_ok,
        "neo4j_written": neo4j_ok,
        "sample_entities": doc_entities
    }
    logger.info(f"=== Ingestion complete: {summary} ===")
    return summary


# ---------------------------------------------------------------------------
# CLI usage
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(name)s - %(message)s")

    pdf = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parent.parent.parent.parent / "corporate_travel_policy.pdf"
    )
    result = ingest_pdf(pdf)
    print("\n=== Ingestion Summary ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
