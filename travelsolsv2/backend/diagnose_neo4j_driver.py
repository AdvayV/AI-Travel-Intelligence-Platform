import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import logging

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

print("--- Testing bolt+s:// Scheme ---")
try:
    bolt_uri = uri.replace("neo4j+s://", "bolt+s://")
    print(f"Connecting to {bolt_uri}...")
    driver = GraphDatabase.driver(bolt_uri, auth=(user, password))
    driver.verify_connectivity()
    print("SUCCESS with bolt+s://")
    driver.close()
except Exception as e:
    print(f"FAILED with bolt+s://: {e}\n")

print("--- Testing default database parameter config ---")
try:
    print(f"Connecting to {uri}...")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    # Test session configuration explicitly selecting 'neo4j'
    with driver.session(database="neo4j") as session:
        res = session.run("RETURN 1")
        print(f"SUCCESS with session(database='neo4j'): {res.single()}")
    driver.close()
except Exception as e:
    print(f"FAILED with session(database='neo4j'): {e}\n")
