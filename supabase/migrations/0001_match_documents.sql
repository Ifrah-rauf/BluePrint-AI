create or replace function public.match_documents(
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
  title text,
  content text,
  source text,
  collection text,
  similarity float
)
language plpgsql
stable
as $$
begin
  return query
  select
    documents.id,
    documents.title,
    documents.content,
    documents.source,
    documents.collection,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where documents.embedding is not null
    and (1 - (documents.embedding <=> query_embedding)) > match_threshold
    and (
      collection_filter is null
      or documents.collection = collection_filter
    )
    and (
      user_id_filter is null
      or coalesce(documents.metadata ->> 'user_id', '') = user_id_filter
    )
    and (
      profile_id_filter is null
      or coalesce(documents.metadata ->> 'profile_id', '')::int = profile_id_filter
    )
    and (
      session_id_filter is null
      or coalesce(documents.metadata ->> 'session_id', '') = session_id_filter
    )
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;
