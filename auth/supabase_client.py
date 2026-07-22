import os
from supabase import Client, create_client
from supabase.client import ClientOptions
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_CLIENT_TIMEOUT_SECONDS = int(os.getenv("SUPABASE_CLIENT_TIMEOUT_SECONDS", "15"))

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL or SUPABASE_ANON_KEY is missing from .env")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    options=ClientOptions(
        postgrest_client_timeout=SUPABASE_CLIENT_TIMEOUT_SECONDS,
        storage_client_timeout=SUPABASE_CLIENT_TIMEOUT_SECONDS,
        auto_refresh_token=False,
        persist_session=False,
    ),
)
