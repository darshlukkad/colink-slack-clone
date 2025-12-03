"""Kafka consumer for processing message events."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Message, Thread
from shared.database.base import async_engine

from ..config import settings

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    """Service for consuming message events from Kafka."""

    def __init__(self):
        """Initialize Kafka consumer."""
        self.consumer: AIOKafkaConsumer | None = None
        self.bootstrap_servers = settings.kafka_bootstrap_servers
        self.running = False

    async def start(self):
        """Start Kafka consumer."""
        try:
            self.consumer = AIOKafkaConsumer(
                settings.kafka_message_topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id="threads-service",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="latest",  # Start from latest messages
                enable_auto_commit=True,
            )
            await self.consumer.start()
            self.running = True
            logger.info(f"Kafka consumer started: {self.bootstrap_servers}")

            # Start consuming in background
            asyncio.create_task(self.consume_messages())

        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}", exc_info=True)

    async def stop(self):
        """Stop Kafka consumer."""
        self.running = False
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("Kafka consumer stopped")
            except Exception as e:
                logger.error(f"Error stopping Kafka consumer: {e}", exc_info=True)

    async def consume_messages(self):
        """Consume and process messages from Kafka."""
        if not self.consumer:
            return

        try:
            async for msg in self.consumer:
                if not self.running:
                    break

                try:
                    event = msg.value
                    event_type = event.get("event_type")
                    data = event.get("data", {})

                    logger.debug(f"Received event: {event_type}")

                    # Process different event types
                    if event_type == "message.created":
                        await self.handle_message_created(data)
                    elif event_type == "message.deleted":
                        await self.handle_message_deleted(data)

                except Exception as e:
                    logger.error(f"Error processing Kafka message: {e}", exc_info=True)
                    # Continue processing other messages

        except Exception as e:
            logger.error(f"Error in Kafka consumer loop: {e}", exc_info=True)

    async def handle_message_created(self, data: Dict[str, Any]):
        """Handle message.created event.

        If message has a thread_id, we need to:
        1. Create thread if it doesn't exist
        2. Update thread stats (reply count, participant count, last_reply_at)
        """
        try:
            thread_id = data.get("thread_id")
            message_id = data.get("id")
            parent_message_id = data.get("parent_message_id")

            # If message has parent_message_id but no thread_id, create thread
            if parent_message_id and not thread_id:
                await self.create_thread_from_reply(parent_message_id, message_id)
            # If message has thread_id, update thread stats
            elif thread_id:
                await self.update_thread_stats(UUID(thread_id))

        except Exception as e:
            logger.error(f"Error handling message.created event: {e}", exc_info=True)

    async def handle_message_deleted(self, data: Dict[str, Any]):
        """Handle message.deleted event.

        If the deleted message is:
        1. A thread root message - soft delete entire thread
        2. A thread reply - update thread stats
        """
        try:
            message_id = data.get("id")
            thread_id = data.get("thread_id")

            async with AsyncSession(async_engine) as db:
                # Check if this is a thread root message
                stmt = select(Thread).where(Thread.root_message_id == UUID(message_id))
                result = await db.execute(stmt)
                thread = result.scalar_one_or_none()

                if thread:
                    # This is a root message - mark thread as inactive
                    # (thread replies are already soft-deleted via Message.deleted_at)
                    logger.info(f"Thread root message deleted: {message_id}, thread: {thread.id}")
                    # Thread stats will be updated automatically since replies are soft-deleted
                    await self.update_thread_stats(thread.id)

                elif thread_id:
                    # This is a thread reply - update thread stats
                    await self.update_thread_stats(UUID(thread_id))

        except Exception as e:
            logger.error(f"Error handling message.deleted event: {e}", exc_info=True)

    async def create_thread_from_reply(self, parent_message_id: str, reply_message_id: str):
        """Create a new thread when first reply is made to a message.

        Args:
            parent_message_id: The root message ID
            reply_message_id: The first reply message ID
        """
        try:
            async with AsyncSession(async_engine) as db:
                # Check if thread already exists
                stmt = select(Thread).where(Thread.root_message_id == UUID(parent_message_id))
                result = await db.execute(stmt)
                existing_thread = result.scalar_one_or_none()

                if existing_thread:
                    logger.debug(f"Thread already exists for message {parent_message_id}")
                    # Update the reply message with thread_id
                    stmt = select(Message).where(Message.id == UUID(reply_message_id))
                    result = await db.execute(stmt)
                    reply_message = result.scalar_one_or_none()
                    if reply_message:
                        reply_message.thread_id = existing_thread.id
                        await db.commit()
                    return

                # Create new thread
                thread = Thread(
                    root_message_id=UUID(parent_message_id),
                    reply_count=1,
                    participant_count=1,
                    last_reply_at=datetime.now(timezone.utc),
                )
                db.add(thread)
                await db.flush()

                # Update the reply message with thread_id
                stmt = select(Message).where(Message.id == UUID(reply_message_id))
                result = await db.execute(stmt)
                reply_message = result.scalar_one_or_none()

                if reply_message:
                    reply_message.thread_id = thread.id
                    await db.commit()

                    logger.info(f"Created thread {thread.id} for message {parent_message_id}")
                else:
                    logger.error(f"Reply message {reply_message_id} not found")
                    await db.rollback()

        except Exception as e:
            logger.error(f"Error creating thread from reply: {e}", exc_info=True)

    async def update_thread_stats(self, thread_id: UUID):
        """Update thread statistics (reply count, participant count, last_reply_at).

        Args:
            thread_id: Thread ID to update
        """
        try:
            async with AsyncSession(async_engine) as db:
                # Get thread
                stmt = select(Thread).where(Thread.id == thread_id)
                result = await db.execute(stmt)
                thread = result.scalar_one_or_none()

                if not thread:
                    logger.warning(f"Thread {thread_id} not found")
                    return

                # Get all non-deleted messages in thread
                stmt = select(Message).where(
                    Message.thread_id == thread_id,
                    Message.deleted_at.is_(None),
                )
                result = await db.execute(stmt)
                messages = result.scalars().all()

                # Update stats
                thread.reply_count = len(messages)
                thread.participant_count = len({msg.author_id for msg in messages if msg.author_id})
                thread.last_reply_at = max((msg.created_at for msg in messages), default=None)

                await db.commit()

                logger.debug(
                    f"Updated thread {thread_id} stats: "
                    f"replies={thread.reply_count}, "
                    f"participants={thread.participant_count}"
                )

        except Exception as e:
            logger.error(f"Error updating thread stats: {e}", exc_info=True)


# Global Kafka consumer instance
kafka_consumer = KafkaConsumerService()
