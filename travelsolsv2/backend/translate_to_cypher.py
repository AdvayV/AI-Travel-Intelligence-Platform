import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

def translate_to_cypher(natural_query: str) -> str:
    """
    Translates a natural language question into a Cypher query using the Hugging Face Router API.
    """
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        return "Error: HUGGINGFACE_API_KEY environment variable is not configured."

    # Define the graph schema context for the LLM
    schema_context = """
    You are an expert Neo4j database administrator. Translate the user's natural language question into a valid Neo4j Cypher query.
    
    Database Schema Elements:
    Nodes:
      - (a:Airport {code: "BOM", name: "Mumbai", city: "Mumbai"})
      - (p:Passenger {id: "PASS-001", name: "Aryan Mehta", tier: "Gold", policy_id: "CP-001"})
      - (cp:CorporatePolicy {id: "CP-001", name: "Standard Travel Policy", allowed_cabins: ["ECONOMY"], allowed_fare_classes: ["Y", "M", "K", "Q"], max_fare_inr: 150000, min_advance_days: 7})
      - (w:Waiver {id: "WX-2026", type: "monsoon", description: "Waiver", valid_until: "2026-12-31", origin_codes: ["BOM"]})
      - (b:Booking {pnr: "PNR123", passenger_name: "Aryan Mehta", flight_number: "AI-101", origin: "BOM", destination: "DEL", date: "2026-07-01", fare_class: "Y", price_inr: 32000})

    Relationships:
      - (p)-[:HAS_POLICY]->(cp)
      - (p)-[:HAS_BOOKING]->(b)
      - (a)-[:HAS_WAIVER]->(w)
      - (o:Airport)-[r:ROUTE {distance_km: 1400, airlines: ["AI", "6E"]}]->(d:Airport)
      
    Instructions:
      - Answer the user's question in a friendly, natural paragraph format as a chatbot (similar to ChatGPT or Gemini).
      - Include the translated Cypher query inside the text, formatted in inline code blocks (e.g. `MATCH (n) RETURN n`).
      - Briefly explain what the Cypher query does in 1 or 2 sentences.
      - Do not use markdown bolding (e.g. do not use double asterisks "**"). Keep the response conversational and clean.
    """

    try:
        # Connect to the Hugging Face Serverless OpenAI-compatible endpoint
        client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=api_key,
            timeout=10.0
        )
        
        # Meta-Llama-3-8B-Instruct is excellent at structured queries
        completion = client.chat.completions.create(
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            messages=[
                {"role": "system", "content": schema_context},
                {"role": "user", "content": f"Translate: {natural_query}"}
            ],
            temperature=0.1,
            max_tokens=200
        )
        
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"API Translation Failed: {e}"

if __name__ == "__main__":
    test_queries = [
        "Find all bookings made by passenger Aryan Mehta",
        "Who is assigned to the policy CP-002?",
        "Get all operational flights from BOM to LHR"
    ]
    
    print("=== Natural Language to Cypher Translation Demo ===")
    for q in test_queries:
        print(f"\nQuestion: {q}")
        cypher = translate_to_cypher(q)
        print(f"Cypher:   {cypher}")
    print("\n==================================================")
