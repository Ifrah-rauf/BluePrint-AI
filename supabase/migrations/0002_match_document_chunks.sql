create or replace function public.match_document_chunks(
  query_embedding vector,
  match_threshold float,
  match_count int,
  collection_filter text default null,
  user_id_filter text default null,
  profile_id_filter int default null,
  session_id_filter text default null
)
returns table (
  id uuid,
  document_id uuid,
  chunk_number int,
  chunk_text text,
  metadata jsonb,
  similarity float
)
language plpgsql
stable
as $$
begin
  return query
  select
    document_chunks.id,
    document_chunks.document_id,
    document_chunks.chunk_number,
    document_chunks.chunk_text,
    document_chunks.metadata,
    1 - (document_chunks.embedding <=> query_embedding) as similarity
  from document_chunks
  where document_chunks.embedding is not null
    and (1 - (document_chunks.embedding <=> query_embedding)) > match_threshold
    and (
      collection_filter is null
      or coalesce(document_chunks.metadata ->> 'collection', '') = collection_filter
    )
    and (
      user_id_filter is null
      or coalesce(document_chunks.metadata ->> 'user_id', '') = user_id_filter
    )
    and (
      profile_id_filter is null
      or coalesce(document_chunks.metadata ->> 'profile_id', '')::int = profile_id_filter
    )
    and (
      session_id_filter is null
      or coalesce(document_chunks.metadata ->> 'session_id', '') = session_id_filter
    )
  order by document_chunks.embedding <=> query_embedding
  limit match_count;
end;
$$;
