"""Script to sync Keycloak users to application database by logging them in."""

import asyncio
import httpx

# Configuration
AUTH_PROXY_URL = "http://localhost:8001"
TEST_USERS = [
    {"username": "david", "password": "password123"},
    {"username": "emma", "password": "password123"},
    {"username": "frank", "password": "password123"},
    {"username": "grace", "password": "password123"},
]


async def login_user(username: str, password: str):
    """Login a user to create their database record."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{AUTH_PROXY_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=10.0,
            )
            if response.status_code == 200:
                print(f"✓ Successfully logged in {username}")
                return True
            else:
                print(f"✗ Failed to login {username}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"✗ Error logging in {username}: {e}")
            return False


async def sync_all_users():
    """Sync all test users by logging them in."""
    print("Starting user sync...\n")

    results = []
    for user in TEST_USERS:
        result = await login_user(user["username"], user["password"])
        results.append(result)
        await asyncio.sleep(1)  # Small delay between requests

    print(f"\nSync complete: {sum(results)}/{len(results)} users synced successfully")


if __name__ == "__main__":
    asyncio.run(sync_all_users())
