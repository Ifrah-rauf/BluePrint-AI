create table if not exists public.chat_sessions (
  id uuid not null default gen_random_uuid (),
  user_id text null,
  title text null default 'New Chat Session',
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  constraint chat_sessions_pkey primary key (id)
) TABLESPACE pg_default;

create table if not exists public.chat_messages (
  id uuid not null default gen_random_uuid (),
  session_id uuid not null,
  role text not null,
  message text not null,
  created_at timestamp with time zone null default now(),
  constraint chat_messages_pkey primary key (id),
  constraint chat_messages_session_id_fkey foreign KEY (session_id) references chat_sessions (id) on delete CASCADE
) TABLESPACE pg_default;

create index if not exists idx_chat_messages_session_id on public.chat_messages using btree (session_id) TABLESPACE pg_default;
