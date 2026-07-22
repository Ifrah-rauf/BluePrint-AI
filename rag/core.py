import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import Client, create_client
from supabase.client import ClientOptions


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=str(ROOT_DIR / ".env"))

SUPPORTED_KB_EXTENSIONS = {".md", ".txt"}
DEFAULT_COLLECTION = "system_design"
USER_UPLOAD_COLLECTION = "user_uploads"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SUPABASE_CLIENT_TIMEOUT_SECONDS = int(os.getenv("SUPABASE_CLIENT_TIMEOUT_SECONDS", "15"))


# 1.SET UP THE SUPABASE ENDPOINT
def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    service_role = os.getenv("SUPABASE_SERVICE_ROLE")

    if not url or not service_role:
        raise ValueError("SUPABASE_URL or SUPABASE_SERVICE_ROLE is missing from .env")

    return create_client(
        url,
        service_role,
        options=ClientOptions(
            postgrest_client_timeout=SUPABASE_CLIENT_TIMEOUT_SECONDS,
            storage_client_timeout=SUPABASE_CLIENT_TIMEOUT_SECONDS,
            auto_refresh_token=False,
            persist_session=False,
        ),
    )

# LOADING EMBEDDING MODEL ONLY ONCE
@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(DEFAULT_EMBEDDING_MODEL)

# CHUNKING DOCUMENTS INTO SMALLER PIECES, RETURNING ARRAY OF KB SUPPORTED FILES
def iter_knowledge_base_files(base_dir: Path | None = None) -> Iterable[Path]:
    kb_dir = base_dir or (ROOT_DIR / "rag" / "knowledge_base")
    if not kb_dir.exists():
        return []

    return sorted(
        path for path in kb_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_KB_EXTENSIONS
    )

# BUILDING DOCUMENT ROWS FOR SUPABASE INSERTION
def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue

        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    if not chunks:
        return [normalized[:max_chars]]

    return chunks

#
def build_document_rows(
    title: str,
    content: str,
    source: str,
    collection: str = DEFAULT_COLLECTION,
    metadata: dict | None = None,
) -> list[dict]:
    chunks = chunk_text(content)
    total_chunks = len(chunks)
    rows: list[dict] = []
    extra_metadata = metadata or {}

    for chunk_index, chunk in enumerate(chunks):
        row_metadata = {
            "source_path": source,
            "chunk_index": chunk_index,
            "chunk_count": total_chunks,
            "title": title,
            "collection": collection,
            **extra_metadata,
        }
        rows.append({
            "title": title,
            "content": chunk,
            "source": source,
            "collection": collection,
            "chunk_index": chunk_index,
            "metadata": row_metadata,
        })

    return rows
