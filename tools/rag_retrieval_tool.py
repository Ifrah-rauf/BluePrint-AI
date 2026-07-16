import os
from dotenv import load_dotenv
from supabase import create_client

# 1. Load configuration secrets from your .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")

# Create connection instance if variables exist
if SUPABASE_URL and SUPABASE_SERVICE_ROLE:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)
else:
    supabase = None

def retrieve_context_from_db(user_query: str, match_count: int = 2):
    """
    Queries the Supabase documents table to find relevant architectural context.
    """
    print(f"🔍 Retrieval tool triggered for query: '{user_query}'")
    
    if not supabase:
        return ["❌ Error: Supabase database connection keys are not initialized."]

    try:
        # Since we are building out the matching pipeline step-by-step, 
        # we will fetch the rows directly by searching for keywords inside the content text column.
        # This keeps it fast and stable without requiring complex embedding calculations for now!
        
        print("📡 Querying cloud database table fields...")
        response = supabase.table("documents").select("title, source, content").execute()
        
        all_documents = response.data
        matched_sources = []
        
        # Simple text matching logic to filter down relevant database rows
        for doc in all_documents:
            # Look for context overlaps (lowercase matching for flexibility)
            if any(word in doc["content"].lower() for word in user_query.lower().split()):
                formatted_source = f"**Title:** {doc['title']} | **Source:** {doc['source']}\n\n{doc['content']}"
                matched_sources.append(formatted_source)
                
            if len(matched_sources) >= match_count:
                break
                
        # Fallback if no specific word matches are found, return the latest scaling asset row
        if not matched_sources and all_documents:
            doc = all_documents[0]
            fallback_source = f"**Title:** {doc['title']} | **Source:** {doc['source']}\n\n{doc['content']}"
            return [fallback_source]
            
        return matched_sources if matched_sources else ["📑 No matching system design patterns found in the current knowledge base."]
        
    except Exception as e:
        print(f"❌ Database selection fetch failed: {str(e)}")
        return [f"❌ Retrieval error: {str(e)}"]
