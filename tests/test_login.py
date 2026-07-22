# from auth.auth import sign_in

# response = sign_in(
#     "test123@example.com",
#     "thisistest"
# )

# print(response)
# print(response.user)
# print(response.session)

# tests/test_profile.py

from auth.auth import get_profile

user_id = "6ec0f965-6c2c-4122-8bd8-339b2de46bbd"

print(get_profile(user_id))