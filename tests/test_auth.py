from auth.auth import sign_in, get_user, sign_out, create_profile

email = "test123@example.com"
password = "thisistest"

# Login
session = sign_in(email, password)
print("Logged in:", session.user.email)

# Create/update profile
profile = create_profile(
    user_id=session.user.id,
    full_name="Test User",
    organization="BluePrint-AI",
)

print(profile)

# Current user
user = get_user()
print("Current user:", user.user.email)

# Logout
sign_out()
print("Logged out")