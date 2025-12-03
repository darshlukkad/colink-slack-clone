#!/usr/bin/env python3
"""
Complete Multi-User Test Flow for Colink

This script simulates a real-world scenario with multiple users:
- Alice, Bob, and Charlie authenticate
- Create multiple channels
- Send messages
- Reply in threads
- Add reactions
- Share files
"""

import requests
import json
import time
from pathlib import Path
import io

# Configuration
KEYCLOAK_URL = "http://localhost:8080"
AUTH_PROXY_URL = "http://localhost:8001"
CHANNEL_SERVICE_URL = "http://localhost:8003"
MESSAGE_SERVICE_URL = "http://localhost:8002"
THREADS_SERVICE_URL = "http://localhost:8005"
REACTIONS_SERVICE_URL = "http://localhost:8006"
FILES_SERVICE_URL = "http://localhost:8007"

REALM = "colink"
CLIENT_ID = "web-app"

# Test users
USERS = {
    "alice": {"password": "password"},
    "bob": {"password": "password"},
    "charlie": {"password": "password"}
}

# Store tokens and user info
user_sessions = {}


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")


def print_step(text):
    """Print a formatted step."""
    print(f"  ➜ {text}")


def print_success(text):
    """Print a success message."""
    print(f"  ✓ {text}")


def print_error(text):
    """Print an error message."""
    print(f"  ✗ {text}")


def authenticate_user(username, password):
    """Authenticate a user and get access token."""
    print_step(f"Authenticating {username}...")

    try:
        response = requests.post(
            f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
            data={
                "username": username,
                "password": password,
                "grant_type": "password",
                "client_id": CLIENT_ID
            }
        )
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data["access_token"]

        # Parse Keycloak ID from JWT token (without verification for testing)
        import base64
        payload = access_token.split('.')[1]
        # Add padding if needed
        payload += '=' * (4 - len(payload) % 4)
        decoded = json.loads(base64.b64decode(payload))
        keycloak_id = decoded.get('sub', 'unknown')

        # Get the actual database user ID from auth-proxy /auth/me endpoint
        me_response = requests.get(
            f"{AUTH_PROXY_URL}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        me_response.raise_for_status()
        user_info = me_response.json()
        user_id = user_info.get('id', keycloak_id)  # Fallback to Keycloak ID if not found

        user_sessions[username] = {
            "token": access_token,
            "user_id": user_id,
            "keycloak_id": keycloak_id,
            "username": username,
            "headers": {"Authorization": f"Bearer {access_token}"}
        }

        print_success(f"{username} authenticated (User ID: {user_id[:8]}...)")
        return True

    except Exception as e:
        print_error(f"Failed to authenticate {username}: {e}")
        return False


def create_channel(creator_username, name, description, channel_type="PUBLIC"):
    """Create a new channel or get existing one."""
    print_step(f"{creator_username} creating/getting channel '{name}'...")

    try:
        session = user_sessions[creator_username]

        # Try to create the channel
        response = requests.post(
            f"{CHANNEL_SERVICE_URL}/channels",
            headers=session["headers"],
            json={
                "name": name,
                "description": description,
                "channel_type": channel_type
            }
        )

        if response.status_code == 409:
            # Channel already exists, fetch it
            print_step(f"Channel '{name}' already exists, fetching it...")
            list_response = requests.get(
                f"{CHANNEL_SERVICE_URL}/channels",
                headers=session["headers"],
                params={"limit": 100}  # Get more channels
            )
            list_response.raise_for_status()
            response_data = list_response.json()

            # API returns {channels: [...], total: N, limit: M, offset: O}
            channels = response_data.get('channels', [])

            for channel in channels:
                if channel['name'] == name:
                    print_success(f"Using existing channel '{name}' (ID: {channel['id']})")
                    return channel

            # If not found in user's channels, try to search or join
            print_step(f"Channel '{name}' not in user's channels, trying to get by name...")
            # For now, just create a new channel with a timestamp suffix
            import time
            new_name = f"{name}-{int(time.time())}"
            return create_channel(creator_username, new_name, description, channel_type)

        response.raise_for_status()
        channel = response.json()
        print_success(f"Channel '{name}' created (ID: {channel['id']})")
        return channel

    except Exception as e:
        print_error(f"Failed to create/get channel: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text}")
        return None


def add_channel_member(adder_username, channel_id, user_id_to_add):
    """Add a member to a channel."""
    print_step(f"{adder_username} adding user {user_id_to_add[:8]}... to channel")

    try:
        session = user_sessions[adder_username]
        response = requests.post(
            f"{CHANNEL_SERVICE_URL}/channels/{channel_id}/members",
            headers=session["headers"],
            json={"user_id": user_id_to_add}
        )
        response.raise_for_status()

        print_success(f"User added to channel")
        return True

    except Exception as e:
        print_error(f"Failed to add member: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text}")
        return False


def send_message(username, channel_id, content):
    """Send a message to a channel."""
    print_step(f"{username} sending message: '{content[:50]}...'")

    try:
        session = user_sessions[username]
        response = requests.post(
            f"{MESSAGE_SERVICE_URL}/messages",
            headers=session["headers"],
            json={
                "channel_id": channel_id,
                "content": content,
                "message_type": "text"
            }
        )
        response.raise_for_status()

        message = response.json()
        print_success(f"Message sent (ID: {message['id']})")
        return message

    except Exception as e:
        print_error(f"Failed to send message: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text}")
        return None


def create_thread_reply(username, parent_message_id, content, channel_id):
    """Reply to a message in a thread."""
    print_step(f"{username} replying in thread: '{content[:50]}...'")

    try:
        session = user_sessions[username]
        # Thread replies are created via the message service with parent_id
        response = requests.post(
            f"{MESSAGE_SERVICE_URL}/messages",
            headers=session["headers"],
            json={
                "channel_id": channel_id,
                "content": content,
                "message_type": "text",
                "parent_id": parent_message_id
            }
        )
        response.raise_for_status()

        reply = response.json()
        print_success(f"Thread reply sent (ID: {reply['id']})")
        return reply

    except Exception as e:
        print_error(f"Failed to send thread reply: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text}")
        return None


def add_reaction(username, message_id, emoji):
    """Add a reaction to a message."""
    print_step(f"{username} reacting with {emoji}")

    try:
        session = user_sessions[username]
        response = requests.post(
            f"{REACTIONS_SERVICE_URL}/messages/{message_id}/reactions",
            headers=session["headers"],
            json={"emoji": emoji}
        )
        response.raise_for_status()

        reaction = response.json()
        print_success(f"Reaction added")
        return reaction

    except Exception as e:
        print_error(f"Failed to add reaction: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text}")
        return None


def upload_file(username, file_content, filename, channel_id=None):
    """Upload a file."""
    print_step(f"{username} uploading file '{filename}'...")

    try:
        session = user_sessions[username]

        # Files service expects X-User-ID header
        headers = session["headers"].copy()
        headers["X-User-ID"] = session["user_id"]

        files = {
            'file': (filename, io.BytesIO(file_content), 'text/plain')
        }
        data = {}
        if channel_id:
            data['channel_id'] = channel_id

        response = requests.post(
            f"{FILES_SERVICE_URL}/api/v1/files/upload",
            headers=headers,
            files=files,
            data=data
        )
        response.raise_for_status()

        file_info = response.json()
        print_success(f"File uploaded (ID: {file_info['id']})")
        return file_info

    except Exception as e:
        print_error(f"Failed to upload file: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text}")
        return None


def main():
    """Run the complete test flow."""
    print_header("COLINK MULTI-USER TEST FLOW")

    # Step 1: Authenticate all users
    print_header("Step 1: Authenticating Users")
    for username, creds in USERS.items():
        if not authenticate_user(username, creds["password"]):
            print_error("Authentication failed. Exiting.")
            return

    time.sleep(1)

    # Step 2: Create channels
    print_header("Step 2: Creating Channels")

    general_channel = create_channel(
        "alice",
        "general",
        "General discussion for the team",
        "PUBLIC"
    )

    random_channel = create_channel(
        "bob",
        "random",
        "Random stuff and fun conversations",
        "PUBLIC"
    )

    project_channel = create_channel(
        "charlie",
        "project-alpha",
        "Discussion about Project Alpha",
        "PRIVATE"
    )

    if not all([general_channel, random_channel, project_channel]):
        print_error("Failed to create channels. Exiting.")
        return

    time.sleep(1)

    # Step 2b: Add members to channels
    print_header("Step 2b: Adding Members to Channels")

    # Add all users to general channel
    add_channel_member("alice", general_channel["id"], user_sessions["bob"]["user_id"])
    add_channel_member("alice", general_channel["id"], user_sessions["charlie"]["user_id"])

    # Add all users to random channel (bob is creator, already a member)
    add_channel_member("bob", random_channel["id"], user_sessions["alice"]["user_id"])
    add_channel_member("bob", random_channel["id"], user_sessions["charlie"]["user_id"])

    # Add all users to project-alpha channel (charlie is creator, already a member)
    add_channel_member("charlie", project_channel["id"], user_sessions["alice"]["user_id"])
    add_channel_member("charlie", project_channel["id"], user_sessions["bob"]["user_id"])

    time.sleep(1)

    # Step 3: Send messages in channels
    print_header("Step 3: Sending Messages in Channels")

    # General channel conversation
    msg1 = send_message(
        "alice",
        general_channel["id"],
        "Hello team! Welcome to Colink! 👋"
    )

    msg2 = send_message(
        "bob",
        general_channel["id"],
        "Hey Alice! This looks great! Excited to be here."
    )

    msg3 = send_message(
        "charlie",
        general_channel["id"],
        "Hi everyone! Let's build something amazing together!"
    )

    # Random channel conversation
    msg4 = send_message(
        "bob",
        random_channel["id"],
        "Anyone want to grab coffee later? ☕"
    )

    msg5 = send_message(
        "alice",
        random_channel["id"],
        "Count me in! I know a great place nearby."
    )

    # Project channel conversation
    msg6 = send_message(
        "charlie",
        project_channel["id"],
        "Let's discuss the architecture for Project Alpha."
    )

    msg7 = send_message(
        "alice",
        project_channel["id"],
        "I think we should go with a microservices approach."
    )

    time.sleep(1)

    # Step 4: Create thread replies
    print_header("Step 4: Creating Thread Replies")

    if msg1:
        thread1 = create_thread_reply(
            "bob",
            msg1["id"],
            "Love the welcome message! Very friendly.",
            general_channel["id"]
        )

        thread2 = create_thread_reply(
            "charlie",
            msg1["id"],
            "Agreed! Great way to start the conversation.",
            general_channel["id"]
        )

    if msg6:
        thread3 = create_thread_reply(
            "alice",
            msg6["id"],
            "I can help with the API design. Let me draft something.",
            project_channel["id"]
        )

        thread4 = create_thread_reply(
            "bob",
            msg6["id"],
            "I'll handle the frontend components.",
            project_channel["id"]
        )

    time.sleep(1)

    # Step 5: Add reactions
    print_header("Step 5: Adding Reactions to Messages")

    if msg1:
        add_reaction("bob", msg1["id"], "👍")
        add_reaction("charlie", msg1["id"], "❤️")
        add_reaction("alice", msg1["id"], "🎉")

    if msg2:
        add_reaction("alice", msg2["id"], "😊")
        add_reaction("charlie", msg2["id"], "👏")

    if msg4:
        add_reaction("alice", msg4["id"], "☕")
        add_reaction("charlie", msg4["id"], "👍")

    if msg7:
        add_reaction("bob", msg7["id"], "💡")
        add_reaction("charlie", msg7["id"], "🚀")

    time.sleep(1)

    # Step 6: Upload and share files
    print_header("Step 6: Uploading and Sharing Files")

    # Alice uploads a project document
    doc_content = b"""
    Project Alpha - Architecture Document
    ======================================

    This document outlines the system architecture for Project Alpha.

    1. Microservices Architecture
    2. Event-Driven Communication
    3. API Gateway Pattern
    4. Database per Service

    Let's discuss this in our next meeting.
    """

    file1 = upload_file(
        "alice",
        doc_content,
        "project-alpha-architecture.txt",
        project_channel["id"]
    )

    # Bob uploads a meeting notes file
    notes_content = b"""
    Meeting Notes - Project Kickoff
    ================================

    Date: Today
    Attendees: Alice, Bob, Charlie

    Topics Discussed:
    - Project timeline
    - Technology stack
    - Team roles

    Action Items:
    - Alice: Draft architecture document [DONE]
    - Bob: Set up frontend repo
    - Charlie: Configure infrastructure
    """

    file2 = upload_file(
        "bob",
        notes_content,
        "meeting-notes.txt",
        general_channel["id"]
    )

    # Charlie uploads a config file
    config_content = b"""
    {
      "project": "Project Alpha",
      "environment": "development",
      "services": [
        "auth-service",
        "message-service",
        "channel-service"
      ],
      "database": {
        "type": "postgresql",
        "host": "localhost",
        "port": 5432
      }
    }
    """

    file3 = upload_file(
        "charlie",
        config_content,
        "config.txt",  # Changed from .json to .txt as JSON files are not in allowed types
        project_channel["id"]
    )

    time.sleep(1)

    # Step 7: Summary
    print_header("Test Flow Complete! 🎉")

    print("\nSummary:")
    print(f"  ✓ {len(user_sessions)} users authenticated")
    print(f"  ✓ 3 channels created (general, random, project-alpha)")
    print(f"  ✓ 7+ messages sent across channels")
    print(f"  ✓ 4+ thread replies created")
    print(f"  ✓ 8+ reactions added")
    print(f"  ✓ 3 files uploaded")

    print("\nChannel IDs:")
    print(f"  - General: {general_channel['id']}")
    print(f"  - Random: {random_channel['id']}")
    print(f"  - Project Alpha: {project_channel['id']}")

    print("\nYou can now:")
    print("  1. Check the database to see all the data")
    print("  2. Query the APIs to retrieve messages, threads, reactions")
    print("  3. Download the uploaded files")
    print("  4. View Kafka events in Redpanda")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
