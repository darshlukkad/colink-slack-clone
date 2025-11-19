#!/usr/bin/env python3
"""
Auth Proxy API Testing Script

This script comprehensively tests all auth-proxy endpoints.

Usage:
    python test_auth_apis.py

    # With custom credentials
    TEST_USERNAME=myuser TEST_PASSWORD=mypass python test_auth_apis.py
"""

import os
import sys
import json
import requests
from typing import Dict, Optional

# Configuration
AUTH_PROXY_URL = os.getenv("AUTH_PROXY_URL", "http://localhost:8001")
TEST_USERNAME = os.getenv("TEST_USERNAME", "testuser")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "testpass123")

# ANSI color codes
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


class AuthProxyTester:
    """Test suite for Auth Proxy API."""

    def __init__(self):
        self.base_url = AUTH_PROXY_URL
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.passed = 0
        self.failed = 0

    def print_header(self, text: str):
        """Print test section header."""
        print(f"\n{YELLOW}{'=' * 60}{NC}")
        print(f"{YELLOW}{text}{NC}")
        print(f"{YELLOW}{'=' * 60}{NC}")

    def print_test(self, name: str, passed: bool):
        """Print test result."""
        if passed:
            print(f"{GREEN}✓{NC} {name}")
            self.passed += 1
        else:
            print(f"{RED}✗{NC} {name}")
            self.failed += 1

    def print_request(self, method: str, endpoint: str, data: Optional[Dict] = None):
        """Print request details."""
        print(f"\n{BLUE}Request:{NC} {method} {endpoint}")
        if data:
            print(f"{BLUE}Data:{NC} {json.dumps(data, indent=2)}")

    def print_response(self, response: requests.Response):
        """Print response details."""
        print(f"{BLUE}Status:{NC} {response.status_code}")
        try:
            print(f"{BLUE}Response:{NC}")
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)

    def test_health(self):
        """Test health check endpoint."""
        self.print_header("TEST 1: Health Check")
        self.print_request("GET", "/health")

        response = requests.get(f"{self.base_url}/health")
        self.print_response(response)

        passed = response.status_code == 200 and "healthy" in response.text
        self.print_test("Health check endpoint", passed)
        return passed

    def test_readiness(self):
        """Test readiness check endpoint."""
        self.print_header("TEST 2: Readiness Check")
        self.print_request("GET", "/health/ready")

        response = requests.get(f"{self.base_url}/health/ready")
        self.print_response(response)

        passed = (
            response.status_code == 200
            and response.json().get("status") == "ready"
            and response.json().get("database") == "connected"
        )
        self.print_test("Readiness check with database", passed)
        return passed

    def test_login(self):
        """Test login endpoint."""
        self.print_header("TEST 3: Login")
        print(f"{YELLOW}Note:{NC} This requires a test user in Keycloak")
        print(f"{YELLOW}Username:{NC} {TEST_USERNAME}")
        print(f"{YELLOW}Password:{NC} {TEST_PASSWORD}")

        data = {"username": TEST_USERNAME, "password": TEST_PASSWORD}
        self.print_request("POST", "/auth/login", data)

        response = requests.post(
            f"{self.base_url}/auth/login",
            json=data,
            headers={"Content-Type": "application/json"},
        )
        self.print_response(response)

        if response.status_code == 200:
            result = response.json()
            if "access_token" in result and "refresh_token" in result:
                self.access_token = result["access_token"]
                self.refresh_token = result["refresh_token"]
                print(f"{GREEN}✓ Access token saved{NC}")
                print(f"{GREEN}✓ Refresh token saved{NC}")
                self.print_test("Login successful", True)
                return True

        self.print_test("Login failed", False)
        print(f"\n{RED}Cannot continue with authenticated tests{NC}")
        print(f"{YELLOW}Please create a test user in Keycloak:{NC}")
        print("1. Visit http://localhost:8080")
        print("2. Login with admin/admin")
        print("3. Go to 'colink' realm")
        print(f"4. Create user: {TEST_USERNAME} with password: {TEST_PASSWORD}")
        return False

    def test_get_user_info(self):
        """Test get current user info endpoint."""
        self.print_header("TEST 4: Get Current User Info")

        if not self.access_token:
            print(f"{RED}Skipping: No access token available{NC}")
            return False

        self.print_request("GET", "/auth/me")

        response = requests.get(
            f"{self.base_url}/auth/me",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        self.print_response(response)

        if response.status_code == 200:
            result = response.json()
            passed = "username" in result and "email" in result and "role" in result
            self.print_test("Get user info", passed)
            return passed

        self.print_test("Get user info", False)
        return False

    def test_refresh_token(self):
        """Test token refresh endpoint."""
        self.print_header("TEST 5: Refresh Token")

        if not self.refresh_token:
            print(f"{RED}Skipping: No refresh token available{NC}")
            return False

        data = {"refresh_token": self.refresh_token}
        self.print_request("POST", "/auth/refresh", data)

        response = requests.post(
            f"{self.base_url}/auth/refresh",
            json=data,
            headers={"Content-Type": "application/json"},
        )
        self.print_response(response)

        if response.status_code == 200:
            result = response.json()
            if "access_token" in result:
                # Update access token
                self.access_token = result["access_token"]
                print(f"{GREEN}✓ New access token obtained{NC}")
                self.print_test("Token refresh", True)
                return True

        self.print_test("Token refresh", False)
        return False

    def test_logout(self):
        """Test logout endpoint."""
        self.print_header("TEST 6: Logout")

        if not self.refresh_token:
            print(f"{RED}Skipping: No refresh token available{NC}")
            return False

        data = {"refresh_token": self.refresh_token}
        self.print_request("POST", "/auth/logout", data)

        response = requests.post(
            f"{self.base_url}/auth/logout",
            json=data,
            headers={"Content-Type": "application/json"},
        )
        self.print_response(response)

        passed = response.status_code == 200 and "Logged out" in response.text
        self.print_test("Logout", passed)
        return passed

    def test_token_revocation(self):
        """Test that revoked token cannot be used."""
        self.print_header("TEST 7: Verify Token Revocation")

        if not self.refresh_token:
            print(f"{RED}Skipping: No refresh token available{NC}")
            return False

        data = {"refresh_token": self.refresh_token}
        self.print_request("POST", "/auth/refresh", {"refresh_token": "***"})

        response = requests.post(
            f"{self.base_url}/auth/refresh",
            json=data,
            headers={"Content-Type": "application/json"},
        )
        self.print_response(response)

        # Should fail with 401 or 500
        passed = response.status_code != 200
        self.print_test("Token properly revoked", passed)

        if not passed:
            print(f"{RED}Warning: Token was not revoked!{NC}")

        return passed

    def test_openapi(self):
        """Test OpenAPI documentation."""
        self.print_header("TEST 8: OpenAPI Documentation")
        self.print_request("GET", "/openapi.json")

        response = requests.get(f"{self.base_url}/openapi.json")
        print(f"{BLUE}Status:{NC} {response.status_code}")

        try:
            data = response.json()
            print(f"{BLUE}Response:{NC} OpenAPI spec with {len(data.get('paths', {}))} paths")
            passed = "openapi" in data and "paths" in data
        except:
            passed = False

        self.print_test("OpenAPI docs available", passed)
        return passed

    def test_swagger_ui(self):
        """Test Swagger UI availability."""
        self.print_header("TEST 9: Swagger UI")
        self.print_request("GET", "/docs")

        response = requests.get(f"{self.base_url}/docs")
        print(f"{BLUE}Status:{NC} {response.status_code}")

        passed = response.status_code == 200 and "swagger-ui" in response.text
        self.print_test("Swagger UI available", passed)
        return passed

    def run_all_tests(self):
        """Run all tests."""
        self.print_header("Auth Proxy API Test Suite")
        print(f"{BLUE}Testing:{NC} {self.base_url}")
        print()

        # Run tests in order
        self.test_health()
        self.test_readiness()

        # Login is required for subsequent tests
        if not self.test_login():
            print(f"\n{YELLOW}Skipping authenticated tests{NC}")
        else:
            self.test_get_user_info()
            self.test_refresh_token()
            self.test_logout()
            self.test_token_revocation()

        self.test_openapi()
        self.test_swagger_ui()

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed

        self.print_header("Test Suite Complete")
        print(f"\n{GREEN}Passed:{NC} {self.passed}/{total}")
        print(f"{RED}Failed:{NC} {self.failed}/{total}")

        if self.failed == 0:
            print(f"\n{GREEN}All tests passed! ✓{NC}")
        else:
            print(f"\n{YELLOW}Some tests failed{NC}")

        print(f"\n{GREEN}Interactive API Documentation:{NC}")
        print(f"  Swagger UI: {self.base_url}/docs")
        print(f"  ReDoc:      {self.base_url}/redoc")

        print(f"\n{GREEN}Available Endpoints:{NC}")
        print("  GET  /health         - Health check")
        print("  GET  /health/ready   - Readiness check")
        print("  POST /auth/login     - Login with credentials")
        print("  POST /auth/refresh   - Refresh access token")
        print("  POST /auth/logout    - Logout and revoke token")
        print("  GET  /auth/me        - Get current user info")
        print()


def main():
    """Main entry point."""
    try:
        tester = AuthProxyTester()
        tester.run_all_tests()
        sys.exit(0 if tester.failed == 0 else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted{NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Error: {e}{NC}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
