import logging
import re
from pathlib import Path


logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class MockCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []
        self.ids = []
        self.metadatas = []

    def count(self):
        return len(self.docs)

    def add(self, documents, ids, metadatas):
        self.upsert(documents, ids, metadatas)

    def upsert(self, documents, ids, metadatas):
        for document, identifier, metadata in zip(documents, ids, metadatas):
            if identifier in self.ids:
                index = self.ids.index(identifier)
                self.docs[index] = document
                self.metadatas[index] = metadata
            else:
                self.docs.append(document)
                self.ids.append(identifier)
                self.metadatas.append(metadata)

    def get(self, include=None):
        return {"documents": list(self.docs), "ids": list(self.ids), "metadatas": list(self.metadatas)}

    def delete(self, ids):
        retained = [(identifier, document, metadata) for identifier, document, metadata
                    in zip(self.ids, self.docs, self.metadatas) if identifier not in ids]
        self.ids = [item[0] for item in retained]
        self.docs = [item[1] for item in retained]
        self.metadatas = [item[2] for item in retained]

    def query(self, query_texts, n_results=3):
        terms = set(re.findall(r"\w+", query_texts[0].lower()))
        ranked = sorted(range(len(self.docs)), key=lambda index: (
            -len(terms.intersection(re.findall(r"\w+", self.docs[index].lower()))), self.ids[index]
        ))[:n_results]
        return {"documents": [[self.docs[index] for index in ranked]],
                "ids": [[self.ids[index] for index in ranked]],
                "metadatas": [[self.metadatas[index] for index in ranked]]}


class MockChromaClient:
    def __init__(self):
        self._collections = {}

    def get_or_create_collection(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]

    def add_documents(self, collection_name, docs, ids, metadatas):
        self.get_or_create_collection(collection_name).upsert(docs, ids, metadatas)

    def get_documents(self, collection_name):
        result = self.get_or_create_collection(collection_name).get()
        return [{"id": identifier, "document": document, "metadata": metadata or {}}
                for identifier, document, metadata in zip(result["ids"], result["documents"], result["metadatas"])]

    def query(self, collection_name, query_text, n_results=3):
        result = self.get_or_create_collection(collection_name).query([query_text], n_results)
        return [{"id": identifier, "document": document, "metadata": metadata or {},
                 "retrieval_method": "keyword", "distance": None, "similarity": None}
                for identifier, document, metadata in zip(result["ids"][0], result["documents"][0], result["metadatas"][0])]


class ChromaClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, path=None):
        if self._initialized:
            return
        self.use_mock = not CHROMA_AVAILABLE
        self.mock_client = MockChromaClient()
        self.client = None
        self.embedding_fn = None
        self.last_error = None
        path = str(path or Path(__file__).resolve().parents[1] / "chroma_store")
        if not self.use_mock:
            try:
                self.client = chromadb.PersistentClient(path=path)
                self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            except Exception as error:
                logger.warning("Chroma initialization failed; using in-memory lexical retrieval: %s", error)
                self.last_error = "Chroma or embedding initialization failed."
                self.use_mock = True
        self._initialized = True
        logger.info("Chroma initialized (lexical fallback = %s)", self.use_mock)

    def get_or_create_collection(self, name):
        if self.use_mock:
            return self.mock_client.get_or_create_collection(name)
        try:
            return self.client.get_collection(name=name, embedding_function=self.embedding_fn)
        except chromadb.errors.NotFoundError:
            return self.client.get_or_create_collection(name=name, embedding_function=self.embedding_fn,
                                                        configuration={"hnsw": {"space": "cosine"}})

    def get_documents(self, collection_name):
        if self.use_mock:
            return self.mock_client.get_documents(collection_name)
        try:
            result = self.get_or_create_collection(collection_name).get(include=["documents", "metadatas"])
            documents = result.get("documents") or []
            metadata = result.get("metadatas") or [{} for _ in documents]
            self.mock_client.add_documents(collection_name, documents, result["ids"], metadata)
            return [{"id": identifier, "document": document, "metadata": meta or {}}
                    for identifier, document, meta in zip(result["ids"], documents, metadata)]
        except Exception as error:
            logger.warning("Cannot read Chroma collection %s: %s", collection_name, error)
            self.last_error = f"Cannot read persistent collection {collection_name}; using memory mirror."
            return self.mock_client.get_documents(collection_name)

    def add_documents(self, collection_name, docs, ids, metadatas):
        if not len(docs) == len(ids) == len(metadatas):
            raise ValueError("Documents, IDs and metadata must have equal lengths.")
        if not docs:
            return {"persisted": not self.use_mock, "count": 0}
        self.mock_client.add_documents(collection_name, docs, ids, metadatas)
        if self.use_mock:
            return {"persisted": False, "count": len(docs)}
        try:
            self.get_or_create_collection(collection_name).upsert(documents=docs, ids=ids, metadatas=metadatas)
            return {"persisted": True, "count": len(docs)}
        except Exception as error:
            logger.warning("Chroma upsert failed for %s: %s", collection_name, error)
            self.last_error = f"Upsert failed for {collection_name}; documents retained only in memory."
            return {"persisted": False, "count": len(docs)}

    def query(self, collection_name, query_text, n_results=3):
        if not query_text.strip() or n_results < 1:
            return []
        if self.use_mock:
            return self.mock_client.query(collection_name, query_text, n_results)

        try:
            collection = self.get_or_create_collection(collection_name)
            count = collection.count()
            if not count:
                return []
            results = collection.query(query_texts=[query_text], n_results=min(n_results, count),
                                       include=["documents", "metadatas", "distances"])
            configuration = getattr(collection, "configuration_json", {})
            configuration = configuration if isinstance(configuration, dict) else {}
            space = (collection.metadata or {}).get("hnsw:space") or (configuration.get("hnsw") or {}).get("space", "l2")
            formatted = []
            for identifier, document, metadata, distance in zip(results["ids"][0], results["documents"][0],
                                                               results["metadatas"][0], results["distances"][0]):
                similarity = 1 - distance if space == "cosine" else 1 - distance / 2 if space == "l2" else None
                formatted.append({"id": identifier, "document": document, "metadata": metadata or {},
                                  "distance": float(distance), "similarity": similarity,
                                  "retrieval_method": "semantic"})
            return formatted
        except Exception as error:
            logger.warning("Semantic query failed for %s: %s", collection_name, error)
            self.last_error = f"Semantic query failed for {collection_name}; using lexical retrieval."
            self.get_documents(collection_name)
            return self.mock_client.query(collection_name, query_text, n_results)

    def replace_documents(self, collection_name, source, docs, ids, metadatas):
        existing = self.get_documents(collection_name)
        result = self.add_documents(collection_name, docs, ids, metadatas)
        stale = [item["id"] for item in existing if item["metadata"].get("source") == source and item["id"] not in ids]
        if stale:
            if not self.use_mock and result["persisted"]:
                self.get_or_create_collection(collection_name).delete(ids=stale)
            self.mock_client.get_or_create_collection(collection_name).delete(stale)
        return result

    def delete_documents(self, collection_name, ids):
        if not ids:
            return
        if not self.use_mock:
            self.get_or_create_collection(collection_name).delete(ids=ids)
        self.mock_client.get_or_create_collection(collection_name).delete(ids)

    def delete_collection(self, name):
        if not self.use_mock:
            self.client.delete_collection(name)
        self.mock_client._collections.pop(name, None)

    def status(self):
        return {"storage_mode": "memory" if self.use_mock else "persistent",
                "embedding_model": None if self.use_mock else "all-MiniLM-L6-v2",
                "last_error": self.last_error}
