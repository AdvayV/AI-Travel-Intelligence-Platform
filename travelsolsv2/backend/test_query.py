import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

print(f"Connecting to {uri} with user {user}...")

try:
    # Try with neo4j+s://
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 1 as val")
        record = result.single()
        print(f"Connection Successful! Return value: {record['val']}")
    driver.close()
except Exception as e:
    print(f"Error with neo4j+s:// scheme: {e}")

try:
    # Try changing scheme to neo4j:// just in case
    alternative_uri = uri.replace("neo4j+s://", "neo4j://")
    print(f"Trying alternative URI: {alternative_uri}")
    driver = GraphDatabase.driver(alternative_uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 1 as val")
        record = result.single()
        print(f"Alternative Connection Successful! Return value: {record['val']}")
    driver.close()
except Exception as e:
    print(f"Error with alternative scheme: {e}")
