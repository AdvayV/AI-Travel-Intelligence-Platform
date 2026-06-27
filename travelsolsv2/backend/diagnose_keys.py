import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
key = os.getenv("HUGGINGFACE_API_KEY")

if key:
    client = OpenAI(
        base_url="https://router.huggingface.co/v1",  # ✓ Use the new router endpoint
        api_key=key
    )
    
    # Use any supported model - these work:
    result = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3-8B-Instruct",  # ✓ Works
        messages=[
            {"role": "user", "content": "Hello, who are you?"}
        ],
        max_tokens=100
    )
    print(f"✓ Response: {result.choices[0].message.content}")
else:
    print("❌ API key not found")