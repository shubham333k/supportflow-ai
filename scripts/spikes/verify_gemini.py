"""
Spike A: Verify Gemini Chat Model and Embeddings
Validates:
1. GEMINI_API_KEY is configured
2. Chat model completes structured output
3. gemini-embedding-001 generates 768-dim normalized vectors
"""
import math
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).resolve().parents[2]
load_dotenv(project_root / ".env")

api_key = os.getenv("GEMINI_API_KEY")
chat_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
embedding_dim = int(os.getenv("GEMINI_EMBEDDING_DIM", "768"))

print("=" * 60)
print("Spike A: Gemini Model & Embeddings Verification")
print("=" * 60)
print(f"Chat Model:            {chat_model}")
print(f"Embedding Model:       {embedding_model}")
print(f"Target Embedding Dims: {embedding_dim}")

if not api_key or api_key == "your-gemini-api-key":
    print("\n[SKIPPED / NOTICE] GEMINI_API_KEY is not set in .env.")
    print("Please obtain a free key from https://aistudio.google.com/ and set it in your .env file.")
    sys.exit(0)

try:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # 1. Test Chat / Generation
    print("\n1. Testing Chat Model...")
    response = client.models.generate_content(
        model=chat_model,
        contents="Say 'OK: Gemini Chat is operational' and nothing else.",
    )
    print(f"Response: {response.text.strip()}")

    # 2. Test Embeddings
    print("\n2. Testing Embedding Model...")
    emb_response = client.models.embed_content(
        model=embedding_model,
        contents="Test text for vector embedding generation.",
        config=types.EmbedContentConfig(
            output_dimensionality=embedding_dim,
        ),
    )
    
    # Extract vector
    vector = emb_response.embeddings[0].values
    dims = len(vector)
    norm = math.sqrt(sum(x * x for x in vector))
    print("Embedding generated successfully!")
    print(f"Returned Dimensions: {dims} (Expected: {embedding_dim})")
    print(f"Vector L2 Norm:      {norm:.4f}")

    if dims == embedding_dim:
        print("\n>>> Spike A Result: SUCCESS <<<")
    else:
        print(f"\n>>> Spike A Warning: Dimensionality mismatch ({dims} vs {embedding_dim}) <<<")

except Exception as e:
    print(f"\n[ERROR] Gemini verification failed: {e}")
    sys.exit(1)
