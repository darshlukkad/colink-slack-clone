"""WebSocket service using Socket.IO for real-time communication."""

import asyncio
import logging
from contextlib import asynccontextmanager

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt

from config import settings
from services.kafka_consumer import kafka_consumer
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins_list,
    logger=settings.debug,
    engineio_logger=settings.debug,
)

# Store user sessions: {user_id: set of session_ids}
user_sessions = {}
# Store channel memberships: {channel_id: set of session_ids}
channel_rooms = {}
# Store session metadata: {session_id: {user_id, channels}}
session_metadata = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting WebSocket service...")

    # Start Kafka consumer
    await kafka_consumer.start()

    # Register Kafka handlers
    kafka_consumer.register_handler(settings.kafka_messages_topic, handle_kafka_message)
    kafka_consumer.register_handler(settings.kafka_typing_topic, handle_kafka_typing)
    kafka_consumer.register_handler(
        settings.kafka_user_status_topic, handle_kafka_user_status
    )
    kafka_consumer.register_handler(settings.kafka_reactions_topic, handle_kafka_reaction)

    logger.info("✅ WebSocket service started successfully")

    yield

    # Cleanup
    logger.info("🛑 Shutting down WebSocket service...")
    await kafka_consumer.stop()


# Create FastAPI app
app = FastAPI(title="WebSocket Service", lifespan=lifespan)

# Expose Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)
logger.info("Prometheus metrics exposed at /metrics")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO app
socket_app = socketio.ASGIApp(sio, app)


# Kafka message handlers
async def handle_kafka_message(data: dict):
    """Handle new message from Kafka and broadcast to channel members."""
    try:
        event_type = data.get("event_type")
        message_data = data.get("data", {})
        channel_id = message_data.get("channel_id")

        if event_type == "message.created" and channel_id:
            logger.info(f"📤 Broadcasting new message to channel: {channel_id}")

            # Broadcast to all users in the channel
            await sio.emit(
                "new_message",
                message_data,
                room=f"channel:{channel_id}",
            )

        elif event_type == "message.updated" and channel_id:
            await sio.emit(
                "message_updated",
                message_data,
                room=f"channel:{channel_id}",
            )

        elif event_type == "message.deleted":
            message_id = message_data.get("id")
            channel_id = message_data.get("channel_id")
            if channel_id:
                logger.info(f"📤 Broadcasting message deletion to channel: {channel_id}")
                await sio.emit(
                    "message_deleted",
                    {"message_id": message_id},
                    room=f"channel:{channel_id}",
                )

    except Exception as e:
        logger.error(f"Error handling Kafka message: {e}")


async def handle_kafka_typing(data: dict):
    """Handle typing indicator from Kafka."""
    try:
        channel_id = data.get("channel_id")
        user_id = data.get("user_id")
        is_typing = data.get("is_typing", False)

        if channel_id:
            await sio.emit(
                "user_typing",
                {
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "is_typing": is_typing,
                },
                room=f"channel:{channel_id}",
            )

    except Exception as e:
        logger.error(f"Error handling typing indicator: {e}")


async def handle_kafka_user_status(data: dict):
    """Handle user status change from Kafka."""
    try:
        user_id = data.get("user_id")
        status = data.get("status")

        # Broadcast to all connected users
        await sio.emit(
            "user_status_change",
            {"user_id": user_id, "status": status},
        )

    except Exception as e:
        logger.error(f"Error handling user status: {e}")


async def handle_kafka_reaction(data: dict):
    """Handle reaction events from Kafka and broadcast to channel members."""
    try:
        event_type = data.get("event_type")
        reaction_data = data.get("data", {})
        channel_id = reaction_data.get("channel_id")

        if channel_id:
            if event_type == "reaction.added":
                logger.info(f"📤 Broadcasting reaction added to channel: {channel_id}")
                await sio.emit(
                    "reaction_added",
                    reaction_data,
                    room=f"channel:{channel_id}",
                )
            elif event_type == "reaction.removed":
                logger.info(f"📤 Broadcasting reaction removed from channel: {channel_id}")
                await sio.emit(
                    "reaction_removed",
                    reaction_data,
                    room=f"channel:{channel_id}",
                )

    except Exception as e:
        logger.error(f"Error handling reaction: {e}")


# Socket.IO event handlers
@sio.event
async def connect(sid, environ, auth):
    """Handle client connection."""
    try:
        # Extract token from auth
        token = auth.get("token") if auth else None

        if not token:
            logger.warning(f"Connection rejected for {sid}: No token provided")
            return False

        # Decode JWT token (without verification for now, just to get user_id)
        # In production, you should verify the token signature
        try:
            # Decode without verification to extract claims
            unverified_claims = jwt.get_unverified_claims(token)
            user_id = unverified_claims.get("sub")

            if not user_id:
                logger.warning(f"Connection rejected for {sid}: No user_id in token")
                return False

            # Extract username and display name from token
            username = unverified_claims.get("preferred_username")
            display_name = unverified_claims.get("name")

            # Store session metadata
            session_metadata[sid] = {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "channels": set(),
            }

            # Add to user sessions
            if user_id not in user_sessions:
                user_sessions[user_id] = set()
            user_sessions[user_id].add(sid)

            logger.info(f"✅ User {user_id} connected with session {sid}")

            # Broadcast that user is now online
            await sio.emit(
                "user_online",
                {"user_id": user_id, "status": "online"},
            )

            return True

        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            return False

    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    try:
        metadata = session_metadata.get(sid)
        if metadata:
            user_id = metadata["user_id"]
            channels = metadata["channels"]

            # Remove from user sessions
            if user_id in user_sessions:
                user_sessions[user_id].discard(sid)
                # Check if user has no more active sessions
                if not user_sessions[user_id]:
                    del user_sessions[user_id]
                    # Broadcast that user is now offline
                    await sio.emit(
                        "user_offline",
                        {"user_id": user_id, "status": "offline"},
                    )

            # Remove from channel rooms
            for channel_id in channels:
                room_key = f"channel:{channel_id}"
                if room_key in channel_rooms:
                    channel_rooms[room_key].discard(sid)
                    if not channel_rooms[room_key]:
                        del channel_rooms[room_key]

            # Clean up session metadata
            del session_metadata[sid]

            logger.info(f"👋 User {user_id} disconnected (session {sid})")

    except Exception as e:
        logger.error(f"Disconnect error: {e}")


@sio.event
async def join_channel(sid, data):
    """Handle user joining a channel."""
    try:
        channel_id = data.get("channel_id")
        if not channel_id:
            return {"error": "channel_id required"}

        metadata = session_metadata.get(sid)
        if not metadata:
            return {"error": "Session not found"}

        room_key = f"channel:{channel_id}"

        # Add to Socket.IO room
        await sio.enter_room(sid, room_key)

        # Track in our data structures
        metadata["channels"].add(channel_id)
        if room_key not in channel_rooms:
            channel_rooms[room_key] = set()
        channel_rooms[room_key].add(sid)

        logger.info(
            f"User {metadata['user_id']} joined channel {channel_id} (session {sid})"
        )

        return {"status": "joined", "channel_id": channel_id}

    except Exception as e:
        logger.error(f"Error joining channel: {e}")
        return {"error": str(e)}


@sio.event
async def leave_channel(sid, data):
    """Handle user leaving a channel."""
    try:
        channel_id = data.get("channel_id")
        if not channel_id:
            return {"error": "channel_id required"}

        metadata = session_metadata.get(sid)
        if not metadata:
            return {"error": "Session not found"}

        room_key = f"channel:{channel_id}"

        # Remove from Socket.IO room
        await sio.leave_room(sid, room_key)

        # Remove from tracking
        metadata["channels"].discard(channel_id)
        if room_key in channel_rooms:
            channel_rooms[room_key].discard(sid)
            if not channel_rooms[room_key]:
                del channel_rooms[room_key]

        logger.info(
            f"User {metadata['user_id']} left channel {channel_id} (session {sid})"
        )

        return {"status": "left", "channel_id": channel_id}

    except Exception as e:
        logger.error(f"Error leaving channel: {e}")
        return {"error": str(e)}


@sio.event
async def typing(sid, data):
    """Handle typing indicator."""
    try:
        channel_id = data.get("channel_id")
        is_typing = data.get("is_typing", False)

        metadata = session_metadata.get(sid)
        if not metadata:
            return {"error": "Session not found"}

        user_id = metadata["user_id"]
        username = metadata.get("username")
        display_name = metadata.get("display_name")
        room_key = f"channel:{channel_id}"

        # Broadcast to others in the channel
        await sio.emit(
            "user_typing",
            {
                "channel_id": channel_id,
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "is_typing": is_typing,
            },
            room=room_key,
            skip_sid=sid,  # Don't send back to sender
        )

    except Exception as e:
        logger.error(f"Error handling typing: {e}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "websocket",
        "connected_users": len(user_sessions),
        "active_channels": len(channel_rooms),
    }


@app.get("/online-users")
async def get_online_users():
    """Get list of currently online user IDs."""
    return {
        "online_users": list(user_sessions.keys()),
        "count": len(user_sessions),
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "WebSocket Service",
        "version": "1.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:socket_app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
