import os
from pathlib import Path
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# 1. Dynamically locate and load the .env file from the project root folder
root_dir = Path(__file__).resolve().parents[1]
env_path = root_dir / ".env"
load_dotenv(dotenv_path=str(env_path))

# 2. Extract your exact environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Using your exact key name here!

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Error: SUPABASE_URL or SUPABASE_KEY is missing from your .env file.")

# 3. Initialize the Supabase Client connection
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 4. Load the Hugging Face Model locally on your machine
print("🔄 Loading local Hugging Face all-MiniLM-L6-v2 model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Local embedding model loaded successfully!")

def insert_document_to_db(title: str, content: str, source: str):
    """
    Generates real 384-dimensional dense vectors using sentence-transformers
    and pushes the text chunk along with the vector payload straight into Supabase.
    """
    # 5. Format text chunk and compute the vector embedding array
    combined_text = f"Title: {title}\nContent: {content}"
    print(f"🧠 Generating vector array for: '{title}'...")
    real_embedding = embedding_model.encode(combined_text).tolist() 
    
    # 6. Map the dictionary keys to match your Supabase table schema
    data = {
        "title": title,
        "content": content,
        "source": source,
        "collection": "system_design",  # Added this to satisfy the NOT NULL constraint!
        "chunk_index": 0,
        "embedding": real_embedding  
    }
    
    try:
        response = supabase.table("documents").insert(data).execute()
        print(f"🚀 Successfully ingested: '{title}' into the database grid!")
        return response
    except Exception as e:
        print(f"❌ Ingestion database transaction failed: {str(e)}")
        return None

# Execution runner block
if __name__ == "__main__":
    sample_title = "Scaling a Distributed URL Shortener"
    sample_content = (
        "A scalable URL shortener like Bitly requires a highly available infrastructure. "
        "The application layer handles incoming shorten requests by generating a unique base62 hash identifier. "
        "To handle 10M active users, a caching layer using Redis must be placed in front of the primary relational database "
        "to intercept frequent read requests for popular links. The database should use unique constraints on the short-code column "
        "to prevent mapping collisions under heavy concurrent write loads."
    )
    sample_source = "System Design Primer Blogs"
    
    insert_document_to_db(sample_title, sample_content, sample_source)
