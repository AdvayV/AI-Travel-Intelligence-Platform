import os
from neo4j import GraphDatabase

uri = "neo4j+s://cb3423c6.databases.neo4j.io"
password = "_ryOszORh6m_YN0N-pmERAVsNe-GhQ2K9NdrCjcuYXU"

print("--- Test 1: Username 'cb3423c6' ---")
try:
    driver1 = GraphDatabase.driver(uri, auth=("cb3423c6", password))
    driver1.verify_connectivity()
    print("SUCCESS with Username 'cb3423c6'!")
    driver1.close()
except Exception as e:
    print(f"FAILED with 'cb3423c6': {e}")

print("\n--- Test 2: Username 'neo4j' ---")
try:
    driver2 = GraphDatabase.driver(uri, auth=("neo4j", password))
    driver2.verify_connectivity()
    print("SUCCESS with Username 'neo4j'!")
    driver2.close()
except Exception as e:
    print(f"FAILED with 'neo4j': {e}")
