from auth.supabase_client import supabase
from auth.session import clear_refresh_token_cookie, set_refresh_token_cookie


def _extract_session(response):
    session = getattr(response, "session", None)
    if session is not None:
        return session

    if getattr(response, "access_token", None) and getattr(response, "refresh_token", None):
        return response

    return None


def _apply_session(response) -> None:
    session = _extract_session(response)
    if session is None:
        return

    access_token = getattr(session, "access_token", None)
    refresh_token = getattr(session, "refresh_token", None)
    if not access_token or not refresh_token:
        return

    try:
        supabase.auth.set_session(access_token, refresh_token)
    except Exception:
        # PostgREST auth is the important part for table access if the auth
        # client does not expose session state in the current runtime.
        try:
            supabase.postgrest.auth(access_token)
        except Exception:
            pass


def sign_up(
    email: str,
    password: str,
    full_name: str = "",
    organization: str = "",
):
    """
    Register a new user with Supabase Authentication.
    """
    try:
        return supabase.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name,
                        "organization": organization,
                    }
                },
            }
        )

    except Exception as e:
        raise RuntimeError(f"Sign up failed: {e}") from e
    

# def create_profile(
#     user_id: str,
#     full_name: str = "",
#     organization: str = "",
#     role: str = "user",
# ):
#     """
#     Create a profile entry for a newly registered user.
#     """
#     try:
#         return (
#             supabase.table("profiles")
#             .insert(
#                 {
#                     "id": user_id,
#                     "full_name": full_name,
#                     "organization": organization,
#                     "role": role,
#                 }
#             )
#             .execute()
#         )
#     except Exception as e:
#         raise RuntimeError(f"Profile creation failed: {e}") from e


def sign_in(email: str, password: str, remember_me: bool = True):
    """
    Login an existing user.
    """
    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )

        _apply_session(response)
        session = _extract_session(response)
        if remember_me and session and getattr(session, "refresh_token", None):
            set_refresh_token_cookie(session.refresh_token)
        elif not remember_me:
            clear_refresh_token_cookie()

        return response
    except Exception as e:
        raise RuntimeError(f"Sign in failed: {e}") from e


def sign_out():
    """
    Logout the current user.
    """
    try:
        response = supabase.auth.sign_out()
        return response
    except Exception as e:
        raise RuntimeError(f"Sign out failed: {e}") from e
    finally:
        clear_refresh_token_cookie()


def get_profile(user_id: str):
    """
    Fetch profile information for authenticated user.
    """
    try:
        return (
            supabase
            .table("profiles")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception as e:
        raise RuntimeError(f"Profile fetch failed: {e}") from e


def get_user():
    """
    Return the currently authenticated user.
    """
    try:
        response = supabase.auth.get_user()

        if response.user is None:
            return None

        return response.user

    except Exception as e:
        raise RuntimeError(f"Get user failed: {e}") from e
