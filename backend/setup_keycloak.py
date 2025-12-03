#!/usr/bin/env python3
"""
Keycloak Setup Script
Creates the 'colink' realm and test users for integration testing
"""

import requests
import json
import time
from typing import Optional

KEYCLOAK_URL = "http://localhost:8080"
ADMIN_USER = "admin"
ADMIN_PASS = "admin"

class KeycloakSetup:
    def __init__(self):
        self.base_url = KEYCLOAK_URL
        self.admin_token = None
    
    def get_admin_token(self) -> str:
        """Get admin access token"""
        print("🔑 Getting admin access token...")
        url = f"{self.base_url}/realms/master/protocol/openid-connect/token"
        data = {
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASS,
            "grant_type": "password"
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        token = response.json()["access_token"]
        print("✅ Admin token obtained")
        return token
    
    def create_realm(self, realm_name: str) -> bool:
        """Create a new realm"""
        print(f"\n🏰 Creating realm '{realm_name}'...")
        
        url = f"{self.base_url}/admin/realms"
        headers = {
            "Authorization": f"Bearer {self.admin_token}",
            "Content-Type": "application/json"
        }
        
        realm_config = {
            "realm": realm_name,
            "enabled": True,
            "displayName": "Colink",
            "displayNameHtml": "<b>Colink</b> Slack Clone",
            "accessTokenLifespan": 3600,  # 1 hour
            "ssoSessionIdleTimeout": 1800,  # 30 minutes
            "ssoSessionMaxLifespan": 36000,  # 10 hours
            "loginTheme": "keycloak",
            "smtpServer": {},
            "registrationAllowed": False,
            "resetPasswordAllowed": True,
            "editUsernameAllowed": False,
            "bruteForceProtected": True
        }
        
        try:
            response = requests.post(url, headers=headers, json=realm_config)
            if response.status_code == 201:
                print(f"✅ Realm '{realm_name}' created successfully")
                return True
            elif response.status_code == 409:
                print(f"⚠️  Realm '{realm_name}' already exists")
                return True
            else:
                print(f"❌ Failed to create realm: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error creating realm: {e}")
            return False
    
    def create_client(self, realm_name: str, client_id: str) -> bool:
        """Create a client in the realm"""
        print(f"\n📱 Creating client '{client_id}' in realm '{realm_name}'...")
        
        url = f"{self.base_url}/admin/realms/{realm_name}/clients"
        headers = {
            "Authorization": f"Bearer {self.admin_token}",
            "Content-Type": "application/json"
        }
        
        client_config = {
            "clientId": client_id,
            "name": "Web Application",
            "description": "Colink Web Application",
            "enabled": True,
            "publicClient": True,
            "directAccessGrantsEnabled": True,
            "standardFlowEnabled": True,
            "implicitFlowEnabled": False,
            "serviceAccountsEnabled": False,
            "authorizationServicesEnabled": False,
            "redirectUris": [
                "http://localhost:3000/*",
                "http://localhost:8000/*"
            ],
            "webOrigins": [
                "http://localhost:3000",
                "http://localhost:8000"
            ],
            "protocol": "openid-connect",
            "attributes": {
                "access.token.lifespan": "3600"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=client_config)
            if response.status_code == 201:
                print(f"✅ Client '{client_id}' created successfully")
                return True
            elif response.status_code == 409:
                print(f"⚠️  Client '{client_id}' already exists")
                return True
            else:
                print(f"❌ Failed to create client: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error creating client: {e}")
            return False
    
    def create_user(self, realm_name: str, username: str, email: str, password: str) -> bool:
        """Create a user in the realm"""
        print(f"\n👤 Creating user '{username}'...")
        
        # Create user
        url = f"{self.base_url}/admin/realms/{realm_name}/users"
        headers = {
            "Authorization": f"Bearer {self.admin_token}",
            "Content-Type": "application/json"
        }
        
        user_config = {
            "username": username,
            "email": email,
            "emailVerified": True,
            "enabled": True,
            "firstName": username.capitalize(),
            "lastName": "User",
            "credentials": [{
                "type": "password",
                "value": password,
                "temporary": False
            }]
        }
        
        try:
            response = requests.post(url, headers=headers, json=user_config)
            if response.status_code == 201:
                print(f"✅ User '{username}' created successfully")
                
                # Get user ID from location header
                location = response.headers.get('Location')
                if location:
                    user_id = location.split('/')[-1]
                    print(f"   User ID: {user_id}")
                
                return True
            elif response.status_code == 409:
                print(f"⚠️  User '{username}' already exists")
                return True
            else:
                print(f"❌ Failed to create user: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return False
    
    def setup_colink_realm(self):
        """Complete setup of Colink realm"""
        print("="*70)
        print("  KEYCLOAK SETUP FOR COLINK")
        print("="*70)
        
        # Get admin token
        try:
            self.admin_token = self.get_admin_token()
        except Exception as e:
            print(f"❌ Failed to get admin token: {e}")
            return False
        
        # Create realm
        if not self.create_realm("colink"):
            return False
        
        time.sleep(1)  # Give Keycloak a moment
        
        # Create client
        if not self.create_client("colink", "web-app"):
            return False
        
        time.sleep(1)
        
        # Create test users
        users = [
            ("alice", "alice@colink.dev", "password123"),
            ("bob", "bob@colink.dev", "password123"),
            ("charlie", "charlie@colink.dev", "password123"),
        ]
        
        for username, email, password in users:
            if not self.create_user("colink", username, email, password):
                print(f"⚠️  Continuing despite user creation issue...")
            time.sleep(0.5)
        
        print("\n" + "="*70)
        print("  ✅ KEYCLOAK SETUP COMPLETE")
        print("="*70)
        print("\nRealm: colink")
        print("Client: web-app (public client with direct access grants)")
        print("\nTest Users:")
        print("  - alice@colink.dev / password123")
        print("  - bob@colink.dev / password123")
        print("  - charlie@colink.dev / password123")
        print("\nAccess Keycloak Admin:")
        print(f"  URL: {KEYCLOAK_URL}/admin")
        print(f"  User: {ADMIN_USER}")
        print(f"  Pass: {ADMIN_PASS}")
        print("="*70)
        
        return True

def main():
    setup = KeycloakSetup()
    success = setup.setup_colink_realm()
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
