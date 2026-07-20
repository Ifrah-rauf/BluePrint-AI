from __future__ import annotations

from typing import Any

from rag.core import get_embedding_model, get_supabase_client


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    content = row.get("content") or row.get("chunk_text") or ""
    chunk_number = row.get("chunk_number")
    return {
        "id": row.get("id"),
        "document_id": row.get("document_id"),
        "title": row.get("title") or metadata.get("parent_title") or metadata.get("file_name"),
        "content": content,
        "chunk_text": row.get("chunk_text"),
        "source": row.get("source") or metadata.get("file_name") or metadata.get("source_path"),
        "collection": row.get("collection") or metadata.get("collection"),
        "metadata": metadata,
        "similarity": row.get("similarity", 0.0),
        "chunk_number": chunk_number if chunk_number is not None else row.get("chunk_index"),
        "chunk_index": row.get("chunk_index", chunk_number),
    }


def _keyword_fallback(user_query: str, limit: int) -> list[dict[str, Any]]:
    supabase = get_supabase_client()
    response = (
        supabase.table("documents")
        .select("id, title, content, source, collection, metadata, chunk_index")
        .limit(200)
        .execute()
    )

    words = [word.lower() for word in user_query.split() if len(word) > 2]
    ranked: list[dict[str, Any]] = []

    for row in response.data or []:
        content = (row.get("content") or "").lower()
        score = sum(1 for word in words if word in content)
        if score:
            ranked.append(_normalize_row({**row, "similarity": float(score)}))

    ranked.sort(key=lambda item: item["similarity"], reverse=True)
    return ranked[:limit]


def _fetch_session_rows(
    table_name: str,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
    collection: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    supabase = get_supabase_client()
    select_columns = "id, title, content, source, collection, metadata, chunk_index"
    if table_name == "document_chunks":
        select_columns = "id, document_id, chunk_number, chunk_text, metadata, created_at"

    query = (
        supabase.table(table_name)
        .select(select_columns)
        .order("created_at", desc=True)
        .limit(limit)
    )

    if collection and table_name != "document_chunks":
        query = query.eq("collection", collection)
    if user_id:
        query = query.contains("metadata", {"user_id": user_id})
    if profile_id is not None:
        query = query.contains("metadata", {"profile_id": profile_id})
    if session_id:
        query = query.contains("metadata", {"session_id": session_id})

    response = query.execute()
    return [_normalize_row(row) for row in (response.data or [])]


def fetch_attached_documents(
    user_id: str,
    profile_id: int,
    collection: str = "user_uploads",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Return the persistent uploaded documents that belong to this user/profile.

    These rows are used by the sidebar to show what is already attached and by
    the agents to build reusable user-level RAG context.
    """
    rows = _fetch_session_rows(
        table_name="documents",
        user_id=user_id,
        profile_id=profile_id,
        collection=collection,
        limit=limit,
    )

    seen_file_names: set[str] = set()
    attached_docs: list[dict[str, Any]] = []

    for row in rows:
        metadata = row.get("metadata") or {}
        file_name = (
            metadata.get("file_name")
            or row.get("source")
            or row.get("title")
            or "unknown"
        )
        if file_name in seen_file_names:
            continue
        seen_file_names.add(file_name)
        row["file_name"] = file_name
        attached_docs.append(row)

    return attached_docs


def _build_rpc_payload(
    query_vector: list[float],
    limit: int,
    match_threshold: float,
    collection: str | None = None,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
):
    payload: dict[str, Any] = {
        "query_embedding": query_vector,
        "match_threshold": match_threshold,
        "match_count": limit,
    }

    if collection:
        payload["collection_filter"] = collection
    if user_id:
        payload["user_id_filter"] = user_id
    if profile_id is not None:
        payload["profile_id_filter"] = profile_id
    if session_id:
        payload["session_id_filter"] = session_id

    return payload


def _search_by_rpc_and_table(
    user_query: str,
    table_name: str,
    rpc_name: str,
    limit: int,
    match_threshold: float,
    collection: str | None = None,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
):
    supabase = get_supabase_client()
    embedding_model = get_embedding_model()
    print(f"Searching {table_name} for: {user_query!r}")
    query_vector = embedding_model.encode(user_query).tolist()
    select_columns = "id, title, content, source, collection, metadata, chunk_index"
    if table_name == "document_chunks":
        select_columns = "id, document_id, chunk_number, chunk_text, metadata, created_at"

    try:
        rpc_payload = _build_rpc_payload(
            query_vector=query_vector,
            limit=limit,
            match_threshold=match_threshold,
            collection=collection,
            user_id=user_id,
            profile_id=profile_id,
            session_id=session_id,
        )
        response = supabase.rpc(rpc_name, rpc_payload).execute()
        rows = [_normalize_row(row) for row in (response.data or [])]
        return rows[:limit]
    except Exception as e:
        print(f"{rpc_name} search failed, using keyword fallback: {e}")
        try:
            response = (
                supabase.table(table_name)
                .select(select_columns)
                .limit(200)
                .execute()
            )
            words = [word.lower() for word in user_query.split() if len(word) > 2]
            ranked: list[dict[str, Any]] = []

            for row in response.data or []:
                content = (row.get("content") or row.get("chunk_text") or "").lower()
                score = sum(1 for word in words if word in content)
                if score:
                    normalized = _normalize_row({**row, "similarity": float(score)})
                    metadata = normalized.get("metadata") or {}
                    if collection and normalized.get("collection") != collection:
                        continue
                    if user_id and str(metadata.get("user_id")) != str(user_id):
                        continue
                    if profile_id is not None and str(metadata.get("profile_id")) != str(profile_id):
                        continue
                    if session_id and str(metadata.get("session_id")) != str(session_id):
                        continue
                    ranked.append(normalized)

            ranked.sort(key=lambda item: item["similarity"], reverse=True)
            return ranked[:limit]
        except Exception as fallback_error:
            print(f"Keyword fallback search for {table_name} failed: {fallback_error}")
            return []


def search_relevant_docs(
    user_query: str,
    limit: int = 3,
    match_threshold: float = 0.4,
    collection: str | None = None,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
):
    """
    Search the documents table using the Supabase match_documents RPC.
    Falls back to a simple keyword search if the RPC is unavailable.
    """
    return _search_by_rpc_and_table(
        user_query=user_query,
        table_name="documents",
        rpc_name="match_documents",
        limit=limit,
        match_threshold=match_threshold,
        collection=collection,
        user_id=user_id,
        profile_id=profile_id,
        session_id=session_id,
    )


def search_relevant_chunks(
    user_query: str,
    limit: int = 3,
    match_threshold: float = 0.4,
    collection: str | None = None,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
):
    return _search_by_rpc_and_table(
        user_query=user_query,
        table_name="document_chunks",
        rpc_name="match_document_chunks",
        limit=limit,
        match_threshold=match_threshold,
        collection=collection,
        user_id=user_id,
        profile_id=profile_id,
        session_id=session_id,
    )


def format_retrieved_docs(docs: list[dict[str, Any]]) -> str:
    if not docs:
        return "No relevant retrieved documents."

    blocks = []
    for idx, doc in enumerate(docs, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[Doc {idx}]",
                    f"Title: {doc.get('title') or 'Untitled'}",
                    f"Source: {doc.get('source') or 'unknown'}",
                    f"Collection: {doc.get('collection') or 'unknown'}",
                    f"Similarity: {doc.get('similarity', 0.0):.4f}",
                    f"Content: {doc.get('content') or ''}",
                ]
            )
        )

    return "\n\n".join(blocks)


def build_rag_context(
    user_query: str,
    limit: int = 3,
    match_threshold: float = 0.4,
    collection: str | None = None,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
) -> str:
    docs = search_relevant_docs(
        user_query=user_query,
        limit=limit,
        match_threshold=match_threshold,
        collection=collection,
        user_id=user_id,
        profile_id=profile_id,
        session_id=session_id,
    )
    return format_retrieved_docs(docs)


def build_combined_rag_context(
    user_query: str,
    limit: int = 3,
    match_threshold: float = 0.4,
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
) -> str:
    user_documents = _fetch_session_rows(
        table_name="documents",
        user_id=user_id,
        profile_id=profile_id,
        collection="user_uploads",
        limit=20,
    )

    user_chunks = _fetch_session_rows(
        table_name="document_chunks",
        user_id=user_id,
        profile_id=profile_id,
        limit=20,
    )

    global_context = build_rag_context(
        user_query=user_query,
        limit=limit,
        match_threshold=match_threshold,
        collection="system_design",
    )

    blocks = []
    if global_context and global_context != "No relevant retrieved documents.":
        blocks.append("Global Context:\n" + global_context)
    if user_documents:
        blocks.append("User Uploaded Files:\n" + format_retrieved_docs(user_documents))
    if user_chunks:
        blocks.append("User Uploaded Chunks:\n" + format_retrieved_docs(user_chunks))

    semantic_upload_context = build_rag_context(
        user_query=user_query,
        limit=limit,
        match_threshold=match_threshold,
        collection="user_uploads",
        user_id=user_id,
        profile_id=profile_id,
    )
    if semantic_upload_context and semantic_upload_context != "No relevant retrieved documents.":
        blocks.append("Relevant Upload Matches:\n" + semantic_upload_context)

    if not blocks:
        return "No relevant retrieved documents."

    return "\n\n".join(blocks)
