from rag.query import search_relevant_docs

def retrieve_context_from_db(
    user_query: str,
    match_count: int = 2,
    collection: str | None = None,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
):
    """
    Retrieves relevant documents from the Supabase-backed RAG index.
    """
    results = search_relevant_docs(
        user_query,
        limit=match_count,
        collection=collection,
        user_id=user_id,
        profile_id=profile_id,
        session_id=session_id,
    )
    if not results:
        return ["No matching system design documents found."]

    formatted_sources = []
    for doc in results:
        formatted_sources.append(
            f"Title: {doc.get('title') or 'Untitled'} | "
            f"Source: {doc.get('source') or 'unknown'} | "
            f"Similarity: {doc.get('similarity', 0.0):.4f}\n\n{doc.get('content') or ''}"
        )
    return formatted_sources
