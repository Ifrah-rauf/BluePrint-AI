from auth.auth import sign_up

response = sign_up(
    email="test123@example.com",
    password="thisistest",
    full_name="Test User",
    organization="OpenAI"
)

print(response)