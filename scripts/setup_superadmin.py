#!/usr/bin/env python3
"""
Superadmin Setup Script

This script creates a superadmin user with admin privileges in both
Keycloak and the PostgreSQL database.

Usage:
    python scripts/setup_superadmin.py

Or inside Docker:
    docker exec colink-auth-proxy python /app/scripts/setup_superadmin.py
"""

import asyncio
import os
import sys
from uuid import UUID
import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the backend directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from shared.database.models import User, UserRole, UserStatus

# Configuration
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "colink")
KEYCLOAK_ADMIN_USER = os.getenv("KEYCLOAK_ADMIN_USER", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")

SUPERADMIN_USERNAME = "superadmin"
SUPERADMIN_EMAIL = "superadmin@colink.dev"
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "SuperAdmin@123")
SUPERADMIN_DISPLAY_NAME = "Super Admin"

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://colink:colink_password@postgres:5432/colink"
)

# If running on host, use localhost instead of postgres
if not os.path.exists("/.dockerenv"):
    DATABASE_URL = DATABASE_URL.replace("@postgres:", "@localhost:")


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def print_header():
    """Print script header."""
    print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}")
    print(f"{Colors.BLUE}   Colink Superadmin Setup Script (Python){Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}")
    print()


def print_config():
    """Print configuration."""
    print(f"{Colors.YELLOW}Configuration:{Colors.NC}")
    print(f"  Keycloak URL: {KEYCLOAK_URL}")
    print(f"  Realm: {KEYCLOAK_REALM}")
    print(f"  Username: {SUPERADMIN_USERNAME}")
    print(f"  Email: {SUPERADMIN_EMAIL}")
    print(f"  Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'configured'}")
    print()


async def get_admin_token() -> str:
    """Get Keycloak admin access token."""
    print(f"{Colors.BLUE}[1/5]{Colors.NC} Getting Keycloak admin access token...")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
            data={
                "username": KEYCLOAK_ADMIN_USER,
                "password": KEYCLOAK_ADMIN_PASSWORD,
                "grant_type": "password",
                "client_id": "admin-cli"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get admin token: {response.status_code}")

        token = response.json().get("access_token")
        if not token:
            raise Exception("No access token in response")

        print(f"{Colors.GREEN}✓ Admin token acquired{Colors.NC}")
        return token


async def check_user_exists(token: str) -> str | None:
    """Check if superadmin user exists in Keycloak."""
    print(f"{Colors.BLUE}[2/5]{Colors.NC} Checking if superadmin user exists in Keycloak...")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/users",
            params={"username": SUPERADMIN_USERNAME, "exact": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 200:
            users = response.json()
            if users and len(users) > 0:
                user_id = users[0]["id"]
                print(f"{Colors.YELLOW}⚠ User already exists in Keycloak (ID: {user_id}){Colors.NC}")
                return user_id

        return None


async def create_keycloak_user(token: str) -> str:
    """Create superadmin user in Keycloak."""
    print(f"{Colors.BLUE}[3/5]{Colors.NC} Creating superadmin user in Keycloak...")

    user_data = {
        "username": SUPERADMIN_USERNAME,
        "email": SUPERADMIN_EMAIL,
        "enabled": True,
        "emailVerified": True,
        "firstName": "Super",
        "lastName": "Admin",
        "credentials": [{
            "type": "password",
            "value": SUPERADMIN_PASSWORD,
            "temporary": False
        }]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/users",
            json=user_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code != 201:
            raise Exception(f"Failed to create user: {response.status_code} - {response.text}")

        print(f"{Colors.GREEN}✓ Superadmin user created in Keycloak{Colors.NC}")

        # Get the created user's ID
        user_id = await check_user_exists(token)
        if not user_id:
            raise Exception("Failed to get created user ID")

        return user_id


async def update_database(keycloak_user_id: str):
    """Create or update superadmin user in PostgreSQL database."""
    print(f"{Colors.BLUE}[4/5]{Colors.NC} Creating/updating superadmin user in PostgreSQL...")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Check if user exists
            stmt = select(User).where(User.keycloak_id == keycloak_user_id)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                # Update existing user
                existing_user.username = SUPERADMIN_USERNAME
                existing_user.email = SUPERADMIN_EMAIL
                existing_user.display_name = SUPERADMIN_DISPLAY_NAME
                existing_user.role = UserRole.ADMIN
                existing_user.status = UserStatus.ACTIVE
                print(f"{Colors.YELLOW}⚠ Updated existing user in database{Colors.NC}")
            else:
                # Create new user
                new_user = User(
                    keycloak_id=keycloak_user_id,
                    username=SUPERADMIN_USERNAME,
                    email=SUPERADMIN_EMAIL,
                    display_name=SUPERADMIN_DISPLAY_NAME,
                    role=UserRole.ADMIN,
                    status=UserStatus.ACTIVE
                )
                session.add(new_user)
                print(f"{Colors.GREEN}✓ Superadmin user created in database{Colors.NC}")

            await session.commit()

        except Exception as e:
            await session.rollback()
            raise Exception(f"Database error: {str(e)}")
        finally:
            await engine.dispose()


async def verify_setup(keycloak_user_id: str):
    """Verify the superadmin setup."""
    print(f"{Colors.BLUE}[5/5]{Colors.NC} Verifying superadmin setup...")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            stmt = select(User).where(User.keycloak_id == keycloak_user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                print(f"{Colors.GREEN}✓ Verification successful{Colors.NC}")
                print()
                print(f"{Colors.GREEN}Database record:{Colors.NC}")
                print(f"  ID: {user.id}")
                print(f"  Username: {user.username}")
                print(f"  Email: {user.email}")
                print(f"  Role: {user.role.value}")
                print(f"  Status: {user.status.value}")
                return True
            else:
                print(f"{Colors.YELLOW}⚠ Could not verify database record{Colors.NC}")
                return False

        finally:
            await engine.dispose()


def print_success():
    """Print success message."""
    print()
    print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
    print(f"{Colors.GREEN}   ✓ Superadmin Setup Complete!{Colors.NC}")
    print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
    print()
    print(f"{Colors.YELLOW}Superadmin Credentials:{Colors.NC}")
    print(f"  Username: {SUPERADMIN_USERNAME}")
    print(f"  Email:    {SUPERADMIN_EMAIL}")
    print(f"  Password: {SUPERADMIN_PASSWORD}")
    print()
    print(f"{Colors.YELLOW}Access:{Colors.NC}")
    print(f"  1. Log in at: http://localhost:3000/login")
    print(f"  2. Admin Dashboard: http://localhost:3000/admin")
    print(f"  3. Analytics Dashboard: http://localhost:3000/analytics")
    print()
    print(f"{Colors.BLUE}Note: The superadmin user will be hidden from regular users' DM lists{Colors.NC}")
    print()


async def main():
    """Main execution function."""
    try:
        print_header()
        print_config()

        # Step 1: Get admin token
        admin_token = await get_admin_token()

        # Step 2 & 3: Check if user exists, create if not
        keycloak_user_id = await check_user_exists(admin_token)
        if not keycloak_user_id:
            keycloak_user_id = await create_keycloak_user(admin_token)

        print(f"  Keycloak User ID: {keycloak_user_id}")

        # Step 4: Update database
        await update_database(keycloak_user_id)

        # Step 5: Verify setup
        await verify_setup(keycloak_user_id)

        # Print success message
        print_success()

    except Exception as e:
        print()
        print(f"{Colors.RED}❌ Error: {str(e)}{Colors.NC}")
        print()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
