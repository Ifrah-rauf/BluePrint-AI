import os
from pathlib import Path
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# 1. Load environment variables
root_dir = Path(__file__).resolve().parents[1]
env_path = root_dir / ".env"
load_dotenv(dotenv_path=str(env_path))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)

# 2. Load the exact same local model we used for ingestion
print("🔄 Loading local embedding model for querying...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def search_relevant_docs(user_query: str, limit: int = 3):
    """
    Converts the user's natural language question into a local embedding vector
    and executes an RPC similarity search against the Supabase document store.
    """
    print(f"🧠 Vectorizing user query: '{user_query}'...")
    query_vector = embedding_model.encode(user_query).tolist()
    
    try:
        # Match using the RPC function we just declared in Supabase
        response = supabase.rpc(
            "match_documents",
            {
                "query_embedding": query_vector,
                "match_threshold": 0.4,  # Adjust similarity floor if needed
                "match_count": limit
            }
        ).execute()
        
        return response.data
    except Exception as e:
        print(f"❌ Similarity search query execution failed: {str(e)}")
        return []

if __name__ == "__main__":
    # Test our query engine against the sample data we ingested earlier
    test_query = "How do I scale a link shortener database using a cache?"
    results = search_relevant_docs(test_query)
    
    print("\n🎯 --- TOP RELEVANT CONTEXT MATCHES ---")
    for idx, match in enumerate(results, start=1):
        print(f"\n[{idx}] Match (Score: {match['similarity']:.4f})")
        print(f"Title: {match['title']}")
        print(f"Snippet: {match['content'][:150]}...")
