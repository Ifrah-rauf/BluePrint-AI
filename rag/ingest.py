from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from rag.core import (
    DEFAULT_COLLECTION,
    ROOT_DIR,
    STATIC_PROFILE_ID,
    STATIC_USER_ID,  # static uid
    USER_UPLOAD_COLLECTION,
    build_document_rows,
    get_embedding_model,
    get_supabase_client,
    iter_knowledge_base_files,
    chunk_text,
)

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None

try:
    from docx import Document
except Exception:  # pragma: no cover - optional dependency
    Document = None


def read_source_file(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding="utf-8").strip()
    title = path.stem.replace("_", " ").replace("-", " ").strip().title()
    return title, content


def _extract_text_from_upload(file_name: str, file_bytes: bytes) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix in {".md", ".txt"}:
        return file_bytes.decode("utf-8", errors="ignore").strip()

    if suffix == ".pdf":
        if PdfReader is None:
            raise RuntimeError("PDF support requires pypdf to be installed.")
        reader = PdfReader(BytesIO(file_bytes))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()

    if suffix == ".docx":
        if Document is None:
            raise RuntimeError("DOCX support requires python-docx to be installed.")
        doc = Document(BytesIO(file_bytes))
        return "\n\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()).strip()

    raise ValueError(f"Unsupported file type: {suffix}")


def ingest_knowledge_base(
    collection: str = DEFAULT_COLLECTION,
    base_dir: Path | None = None,
):
    """
    Load markdown/text documents from rag/knowledge_base, chunk them,
    embed them locally, and insert them into Supabase.
    """
    supabase = get_supabase_client()
    embedding_model = get_embedding_model()
    kb_dir = base_dir or (ROOT_DIR / "rag" / "knowledge_base")

    rows_to_insert: list[dict] = []
    for file_path in iter_knowledge_base_files(kb_dir):
        title, content = read_source_file(file_path)
        document_rows = build_document_rows(
            title=title,
            content=content,
            source=str(file_path.relative_to(ROOT_DIR)),
            collection=collection,
        )

        for row in document_rows:
            embedding_input = f"Title: {row['title']}\nContent: {row['content']}"
            row["embedding"] = embedding_model.encode(embedding_input).tolist()
            rows_to_insert.append(row)

    if not rows_to_insert:
        print(f"No knowledge base files found in {kb_dir}")
        return []

    response = supabase.table("documents").insert(rows_to_insert).execute()
    print(f"Inserted {len(rows_to_insert)} document chunks into Supabase.")
    return response.data


def ingest_uploaded_files(
    uploaded_files,
    collection: str = USER_UPLOAD_COLLECTION,
    user_id: str = STATIC_USER_ID,  # static uid
    profile_id: int = STATIC_PROFILE_ID,
    session_id: str | None = None,
):
    """
    Ingest user-uploaded files into the same documents table for now,
    tagged with temporary static user identity and session metadata.
    """
    if not uploaded_files:
        return []

    supabase = get_supabase_client()
    embedding_model = get_embedding_model()
    chunk_rows_to_insert: list[dict] = []

    for uploaded in uploaded_files:
        file_bytes = uploaded.getvalue()
        content = _extract_text_from_upload(uploaded.name, file_bytes)
        title = Path(uploaded.name).stem.replace("_", " ").replace("-", " ").strip().title()
        chunk_texts = chunk_text(content)
        parent_metadata = {
            "source_type": "upload",
            "file_name": uploaded.name,
            "mime_type": getattr(uploaded, "type", None),
            "user_id": user_id,
            "profile_id": profile_id,
            "session_id": session_id,
            "collection": collection,
            "chunk_count": len(chunk_texts),
        }
        parent_row = {
            "title": title,
            "content": content,
            "source": uploaded.name,
            "collection": collection,
            "chunk_index": 0,
            "metadata": parent_metadata,
            "embedding": embedding_model.encode(
                f"Title: {title}\nContent: {content}"
            ).tolist(),
        }
        parent_response = supabase.table("documents").insert(parent_row).execute()
        inserted_parents = parent_response.data or []
        parent_document_id = inserted_parents[0]["id"] if inserted_parents else None

        for chunk_index, chunk in enumerate(chunk_texts):
            chunk_metadata = {
                "source_type": "upload",
                "file_name": uploaded.name,
                "mime_type": getattr(uploaded, "type", None),
                "user_id": user_id,
                "profile_id": profile_id,
                "session_id": session_id,
                "collection": collection,
                "parent_title": title,
                "chunk_count": len(chunk_texts),
            }
            chunk_row = {
                "document_id": parent_document_id,
                "chunk_number": chunk_index,
                "chunk_text": chunk,
                "metadata": chunk_metadata,
                "embedding": embedding_model.encode(
                    f"Title: {title}\nContent: {chunk}"
                ).tolist(),
            }
            chunk_rows_to_insert.append(chunk_row)

    if not chunk_rows_to_insert:
        return []

    # Best-effort mirror into document_chunks for the dedicated chunk store.
    # We reuse the same chunk payload shape, then attach the parent document ID
    # if Supabase returned it from the parent insert.
    try:
        supabase.table("document_chunks").insert(chunk_rows_to_insert).execute()
        print(
            f"Inserted {len(chunk_rows_to_insert)} chunk rows into document_chunks "
            f"for user_id={user_id} and profile_id={profile_id}."
        )
    except Exception as e:
        print(f"document_chunks insert failed, parent documents were still saved: {e}")

    print(
        f"Inserted {len(uploaded_files)} uploaded parent document row(s) into Supabase "
        f"for user_id={user_id} and profile_id={profile_id}."
    )
    return chunk_rows_to_insert


def insert_document_to_db(
    title: str,
    content: str,
    source: str,
    collection: str = DEFAULT_COLLECTION,
    metadata: dict | None = None,
):
    supabase = get_supabase_client()
    embedding_model = get_embedding_model()
    rows = build_document_rows(
        title=title,
        content=content,
        source=source,
        collection=collection,
        metadata=metadata,
    )
    for row in rows:
        embedding_input = f"Title: {row['title']}\nContent: {row['content']}"
        row["embedding"] = embedding_model.encode(embedding_input).tolist()
    response = supabase.table("documents").insert(rows).execute()
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest knowledge base documents into Supabase.")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--path", default=str(ROOT_DIR / "rag" / "knowledge_base"))
    args = parser.parse_args()

    ingest_knowledge_base(collection=args.collection, base_dir=Path(args.path))


if __name__ == "__main__":
    main()
