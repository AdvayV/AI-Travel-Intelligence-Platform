import os
import re
import logging

logger = logging.getLogger(__name__)

# Try to import chromadb, fallback to a local python-only mock if unavailable
try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("chromadb or sentence-transformers is not installed. Falling back to in-memory Keyword-Overlap Vector Store.")

# --- MOCK IN-MEMORY KEYWORD-OVERLAP CLIENT ---
class MockCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []
        self.ids = []
        self.metadatas = []

    def count(self):
        return len(self.docs)

    def add(self, documents, ids, metadatas):
        for doc, idx, meta in zip(documents, ids, metadatas):
            if idx not in self.ids:
                self.docs.append(doc)
                self.ids.append(idx)
                self.metadatas.append(meta)

    def query(self, query_texts, n_results=3):
        q = query_texts[0].lower()
        q_words = set(re.findall(r"\w+", q))
        
        scored_docs = []
        for doc, idx, meta in zip(self.docs, self.ids, self.metadatas):
            doc_words = set(re.findall(r"\w+", doc.lower()))
            # Calculate word overlap score
            overlap = len(q_words.intersection(doc_words))
            scored_docs.append((overlap, doc, idx, meta))
            
        # Sort by overlap count descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        results = {
            "documents": [[]],
            "metadatas": [[]],
            "ids": [[]]
        }
        for score, doc, idx, meta in scored_docs[:n_results]:
            results["documents"][0].append(doc)
            results["metadatas"][0].append(meta)
            results["ids"][0].append(idx)
        return results

class MockChromaClient:
    def __init__(self):
        self._collections = {}

    def get_or_create_collection(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]

    def add_documents(self, collection_name, docs, ids, metadatas):
        collection = self.get_or_create_collection(collection_name)
        collection.add(docs, ids, metadatas)

    def query(self, collection_name, query_text, n_results=3) -> list[dict]:
        collection = self.get_or_create_collection(collection_name)
        results = collection.query([query_text], n_results)
        
        formatted = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        ids = results["ids"][0]
        for i in range(len(docs)):
            formatted.append({
                "id": ids[i],
                "document": docs[i],
                "metadata": metas[i]
            })
        return formatted


class ChromaClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ChromaClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, path="./chroma_store"):
        if self._initialized:
            return
        
        self.use_mock = not CHROMA_AVAILABLE
        self.mock_client = None
        self.client = None
        self.embedding_fn = None
        
        if not self.use_mock:
            try:
                logger.info(f"Initializing ChromaDB PersistentClient at {path}")
                self.client = chromadb.PersistentClient(path=path)
                
                # Load local SentenceTransformers embedding model
                try:
                    logger.info("Loading local sentence-transformers/all-MiniLM-L6-v2 embedding model...")
                    self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name="all-MiniLM-L6-v2"
                    )
                except Exception as model_err:
                    logger.error(f"Failed to load sentence-transformers model: {model_err}. Falling back to keyword mock embedding/query mode.")
                    self.use_mock = True
            except Exception as client_err:
                logger.error(f"Failed to initialize ChromaDB PersistentClient: {client_err}. Falling back to in-memory Keyword-Overlap store.")
                self.use_mock = True
                
        if self.use_mock:
            self.mock_client = MockChromaClient()
            
        self._initialized = True
        logger.info("ChromaDB Client initialization complete (Mock Mode = %s)", self.use_mock)

    def get_or_create_collection(self, name):
        if self.use_mock:
            return self.mock_client.get_or_create_collection(name)
        try:
            return self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_fn
            )
        except Exception as e:
            logger.error(f"Error in get_or_create_collection for {name}: {e}. Falling back to mock collection.")
            self.use_mock = True
            if not self.mock_client:
                self.mock_client = MockChromaClient()
            return self.mock_client.get_or_create_collection(name)

    def add_documents(self, collection_name, docs, ids, metadatas):
        if self.use_mock:
            self.mock_client.add_documents(collection_name, docs, ids, metadatas)
            return
        try:
            collection = self.get_or_create_collection(collection_name)
            logger.info(f"Adding {len(docs)} documents to Chroma collection: {collection_name}")
            collection.add(
                documents=docs,
                ids=ids,
                metadatas=metadatas
            )
        except Exception as e:
            logger.error(f"Failed to add documents to Chroma collection {collection_name}: {e}. Retrying with mock client.")
            self.use_mock = True
            if not self.mock_client:
                self.mock_client = MockChromaClient()
            self.mock_client.add_documents(collection_name, docs, ids, metadatas)

    def query(self, collection_name, query_text, n_results=3) -> list[dict]:
        if self.use_mock:
            return self.mock_client.query(collection_name, query_text, n_results)
        try:
            collection = self.get_or_create_collection(collection_name)
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            formatted = []
            if results and "documents" in results and results["documents"] and len(results["documents"]) > 0:
                docs = results["documents"][0]
                metas = results["metadatas"][0] if results["metadatas"] else [None] * len(docs)
                ids = results["ids"][0] if results["ids"] else [None] * len(docs)
                for i in range(len(docs)):
                    formatted.append({
                        "id": ids[i],
                        "document": docs[i],
                        "metadata": metas[i] or {}
                    })
            return formatted
        except Exception as e:
            logger.error(f"Error querying Chroma collection '{collection_name}': {e}. Falling back to mock query.")
            self.use_mock = True
            if not self.mock_client:
                self.mock_client = MockChromaClient()
            return self.mock_client.query(collection_name, query_text, n_results)

    def delete_collection(self, name):
        if self.use_mock:
            if self.mock_client and name in self.mock_client._collections:
                del self.mock_client._collections[name]
            return
        try:
            self.client.delete_collection(name)
        except Exception as e:
            logger.warning(f"Failed to delete collection {name}: {e}")

