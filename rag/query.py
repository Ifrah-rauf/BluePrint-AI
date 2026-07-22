from __future__ import annotations

from typing import Any

from rag.core import get_embedding_model, get_supabase_client


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    content = row.get("content") or ""
    return {
        "id": row.get("id"),
        "document_id": row.get("document_id"),
        "title": row.get("title") or metadata.get("file_name") or metadata.get("source_path"),
        "content": content,
        "source": row.get("source") or metadata.get("file_name") or metadata.get("source_path"),
        "collection": row.get("collection") or metadata.get("collection"),
        "metadata": metadata,
        "similarity": row.get("similarity", 0.0),
        "chunk_index": row.get("chunk_index"),
    }


def _row_matches_identity(
    row: dict[str, Any],
    user_id: str | None = None,
    profile_id: int | None = None,
    session_id: str | None = None,
) -> bool:
    metadata = row.get("metadata") or {}
    row_profile_id = row.get("user_id") or metadata.get("profile_id")
    row_auth_user_id = metadata.get("auth_user_id") or metadata.get("user_id")
    row_session_id = metadata.get("session_id")

    if user_id and str(row_auth_user_id) != str(user_id):
        return False
    if profile_id is not None and str(row_profile_id) != str(profile_id):
        return False
    if session_id and str(row_session_id) != str(session_id):
        return False
    return True


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
    select_columns = "id, title, content, source, collection, metadata, user_id, chunk_index"

    query = (
        supabase.table(table_name)
        .select(select_columns)
        .order("created_at", desc=True)
        .limit(limit)
    )

    if collection:
        query = query.eq("collection", collection)

    response = query.execute()
    rows = [_normalize_row(row) for row in (response.data or [])]
    return [
        row for row in rows
        if _row_matches_identity(row, user_id=user_id, profile_id=profile_id, session_id=session_id)
    ]


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
                    if collection and normalized.get("collection") != collection:
                        continue
                    if not _row_matches_identity(
                        normalized,
                        user_id=user_id,
                        profile_id=profile_id,
                        session_id=session_id,
                    ):
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
    return search_relevant_docs(
        user_query=user_query,
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


def fetch_recent_blueprints(
    user_id: str | int | None = None,
    profile_id: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Fetch recent generated blueprints directly from the Supabase documents table
    for the current authenticated user/profile.
    """
    supabase = get_supabase_client()
    try:
        response = (
            supabase.table("documents")
            .select("id, title, source, collection, created_at, metadata, user_id")
            .eq("collection", "generated_blueprints")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        rows = response.data or []

        blueprints: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        for row in rows:
            metadata = row.get("metadata") or {}
            row_profile_id = row.get("user_id") or metadata.get("profile_id")
            row_auth_user_id = metadata.get("auth_user_id") or metadata.get("user_id")

            if profile_id is not None and str(row_profile_id) != str(profile_id):
                continue
            if user_id is not None and str(row_auth_user_id) != str(user_id):
                continue

            title = (
                row.get("title")
                or metadata.get("file_name")
                or row.get("source")
                or "Untitled Blueprint"
            ).strip()

            if title and title not in seen_titles:
                seen_titles.add(title)
                blueprints.append({
                    "id": row.get("id"),
                    "title": title,
                    "collection": row.get("collection"),
                    "created_at": row.get("created_at"),
                    "source": row.get("source"),
                    "user_id": row_profile_id,
                    "metadata": metadata,
                })
                if len(blueprints) >= limit:
                    break

        return blueprints
    except Exception as e:
        print(f"Error fetching recent blueprints from Supabase: {e}")
        return []


def ensure_chat_session(
    session_id: str,
    user_id: str,
    title: str = "Architecture Design Session",
):
    """
    Ensure that a chat session record exists in the public.chat_sessions table.
    """
    supabase = get_supabase_client()
    try:
        res = supabase.table("chat_sessions").select("id").eq("id", session_id).execute()
        if not res.data:
            supabase.table("chat_sessions").insert({
                "id": session_id,
                "user_id": user_id,
                "title": title,
            }).execute()
            print(f"Created new chat_session {session_id} in Supabase.")
    except Exception as e:
        print(f"Note on ensure_chat_session: {e}")


def save_chat_message(
    session_id: str,
    user_id: str,
    role: str,
    message: str,
    title: str = "Architecture Design Session",
) -> dict[str, Any] | None:
    """
    Save a chat message (user or assistant) into the public.chat_messages table in Supabase.
    """
    supabase = get_supabase_client()
    try:
        ensure_chat_session(session_id, user_id=user_id, title=title)

        if role == "user":
            session_title = (message or "").strip()
            if session_title:
                session_title = session_title[:80]
                try:
                    current_session = (
                        supabase.table("chat_sessions")
                        .select("title")
                        .eq("id", session_id)
                        .execute()
                    )
                    current_title = None
                    if current_session.data:
                        current_title = current_session.data[0].get("title")
                    if not current_title or current_title == title:
                        supabase.table("chat_sessions").update({
                            "title": session_title,
                        }).eq("id", session_id).execute()
                except Exception as title_error:
                    print(f"Failed to update chat session title: {title_error}")

        res = supabase.table("chat_messages").insert({
            "session_id": session_id,
            "role": role,
            "message": message,
        }).execute()
        print(f"Saved {role} chat message to Supabase chat_messages.")
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Failed to save chat message to Supabase: {e}")
        return None


def fetch_chat_sessions(
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Fetch saved chat sessions for the current authenticated user.
    """
    supabase = get_supabase_client()
    try:
        res = (
            supabase.table("chat_sessions")
            .select("id, user_id, title, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Failed to fetch chat sessions from Supabase: {e}")
        return []


def fetch_chat_messages(session_id: str) -> list[dict[str, Any]]:
    """
    Fetch all chat messages for a specific session_id from public.chat_messages ordered by created_at.
    """
    supabase = get_supabase_client()
    try:
        res = (
            supabase.table("chat_messages")
            .select("id, session_id, role, message, created_at")
            .eq("session_id", session_id)
            .order("created_at", asc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Failed to fetch chat messages from Supabase: {e}")
        return []
