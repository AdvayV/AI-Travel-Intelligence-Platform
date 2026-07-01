import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def generate_cypher(question: str, schema: str) -> str:
    """
    Generates a Cypher query from a natural language question using the Gemma text-to-cypher model.
    """
    api_key = os.getenv('HUGGINGFACE_API_KEY')
    if not api_key:
        raise ValueError("HUGGINGFACE_API_KEY is not set in the environment.")
        
    client = OpenAI(
        base_url='https://router.huggingface.co/v1',
        api_key=api_key
    )
    
    try:
        completion = client.chat.completions.create(
            model='Qwen/Qwen2.5-Coder-7B-Instruct',
            messages=[
                {'role': 'system', 'content': 'You are a Neo4j Cypher expert. Convert the user question to Cypher based on the schema. Output ONLY the Cypher statement. Do not write markdown, explanations, or intro text.'},
                {'role': 'user', 'content': f'Schema: {schema}\nQuestion: {question}\nCypher:'}
            ],
            max_tokens=150,
            temperature=0.0
        )
        raw = completion.choices[0].message.content
        # Clean formatting
        clean = raw.strip().replace('```cypher', '').replace('```', '').strip()
        return clean
    except Exception as e:
        raise RuntimeError(f"HuggingFace model error: {e}")
