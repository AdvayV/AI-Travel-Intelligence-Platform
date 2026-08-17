import os
from dotenv import load_dotenv
from tls_config import enable_system_trust_store
from openai import OpenAI

load_dotenv()
enable_system_trust_store()
key = os.getenv("HUGGINGFACE_API_KEY")

if key:
    client = OpenAI(
        base_url="https://router.huggingface.co/v1",  # ✓ Use the new router endpoint
        api_key=key
    )
    
    # Use any supported model - these work:
    result = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        messages=[
            {"role": "user", "content": "Hello, who are you?"}
        ],
        max_tokens=100
    )
    print(f"Response: {result.choices[0].message.content}")
else:
    print("API key not found")
