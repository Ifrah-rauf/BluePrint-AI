from auth.supabase_client import supabase


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


def sign_in(email: str, password: str):
    """
    Login an existing user.
    """
    try:
        return supabase.auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )
    except Exception as e:
        raise RuntimeError(f"Sign in failed: {e}") from e


def sign_out():
    """
    Logout the current user.
    """
    try:
        return supabase.auth.sign_out()
    except Exception as e:
        raise RuntimeError(f"Sign out failed: {e}") from e


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