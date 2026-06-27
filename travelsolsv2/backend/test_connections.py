import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("==================================================")
print("              CONNECTION DIAGNOSTICS              ")
print("==================================================")

# 1. Test Hugging Face
hf_key = os.getenv("HUGGINGFACE_API_KEY")
print(f"HF Key configured: {'Yes (starts with ' + hf_key[:6] + ')' if hf_key else 'No'}")
if hf_key:
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=hf_key
        )
        result = client.chat.completions.create(
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            messages=[{"role": "user", "content": "Ping"}],
            max_tokens=10
        )
        print("OK - Hugging Face API: SUCCESS")
    except Exception as e:
        print(f"ERROR - Hugging Face API: FAILED - {str(e)}")
else:
    print("ERROR - Hugging Face API: FAILED - Key is missing")

# 2. Test Neo4j
uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD")
print(f"\nNeo4j URI: {uri}")
print(f"Neo4j Username: {user}")
print(f"Neo4j Password configured: {'Yes' if password else 'No'}")

if uri and password:
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print("OK - Neo4j Database: SUCCESS")
        driver.close()
    except Exception as e:
        print(f"ERROR - Neo4j Database: FAILED - {str(e)}")
        # Try connecting with username 'neo4j' instead
        if user != "neo4j":
            print("Trying with username 'neo4j'...")
            try:
                driver2 = GraphDatabase.driver(uri, auth=("neo4j", password))
                driver2.verify_connectivity()
                print("OK - Neo4j Database (using username 'neo4j'): SUCCESS (Set username in .env to 'neo4j')")
                driver2.close()
            except Exception as e2:
                print(f"ERROR - Neo4j Database (using username 'neo4j'): FAILED - {str(e2)}")
else:
    print("ERROR - Neo4j Database: FAILED - Missing URI or Password")

# 3. Test ChromaDB
print("\nTesting ChromaDB...")
try:
    import chromadb
    from chromadb.utils import embedding_functions
    print("ChromaDB library: Available")
    
    # Test local SentenceTransformers
    print("Loading SentenceTransformer...")
    emb = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    print("OK - SentenceTransformer model: Loaded successfully")
    
    client = chromadb.PersistentClient(path="./chroma_store")
    col = client.get_or_create_collection("test_connection_col", embedding_function=emb)
    print(f"OK - ChromaDB Local Persistent Client: SUCCESS (Docs count: {col.count()})")
except Exception as e:
    print(f"ERROR - ChromaDB: FAILED - {str(e)}")

print("==================================================")
