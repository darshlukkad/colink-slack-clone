"""Kafka consumer for processing events and creating notifications."""

import asyncio
import json
import logging
from typing import Dict
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select

from shared.database import Message, User
from shared.database import base as db_base

from ..config import settings
from ..schemas.notifications import NotificationType
from .notification_manager import notification_manager

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    """Kafka consumer service for processing events."""

    def __init__(self):
        """Initialize Kafka consumer."""
        self.consumer = None
        self.bootstrap_servers = settings.kafka_bootstrap_servers
        self.group_id = settings.kafka_group_id
        self.running = False

    async def start(self):
        """Start the Kafka consumer."""
        try:
            self.consumer = AIOKafkaConsumer(
                "messages",  # Subscribe to messages topic
                "reactions",  # Subscribe to reactions topic
                "channels",  # Subscribe to channels topic
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="latest",
            )

            await self.consumer.start()
            logger.info(
                f"Kafka consumer started: {self.bootstrap_servers} (group: {self.group_id})"
            )

            # Start consuming messages
            self.running = True
            asyncio.create_task(self._consume_messages())

        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise

    async def stop(self):
        """Stop the Kafka consumer."""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")

    async def _consume_messages(self):
        """Consume messages from Kafka."""
        try:
            async for message in self.consumer:
                try:
                    event_data = message.value
                    event_type = event_data.get("event_type")
                    data = event_data.get("data", {})

                    logger.debug(f"Received event: {event_type}")

                    # Route to appropriate handler
                    if event_type == "message.created":
                        await self._handle_message_created(data)
                    elif event_type == "reaction.added":
                        await self._handle_reaction_added(data)
                    elif event_type == "channel.member_added":
                        await self._handle_channel_member_added(data)

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)

        except Exception as e:
            if self.running:
                logger.error(f"Consumer loop error: {e}", exc_info=True)

    async def _handle_message_created(self, data: Dict):
        """Handle message.created event.

        Creates notifications for:
        1. @mentions in the message
        2. Replies to threads (notify parent message author)
        """
        try:
            # The message service sends 'id' but we use it as message_id
            message_id = data.get("id") or data.get("message_id")
            author_id = data.get("author_id")
            content = data.get("content", "")
            parent_message_id = data.get("parent_message_id")

            if not message_id or not author_id:
                logger.warning(f"message.created event missing required fields: {data}")
                return

            async with db_base.async_session_factory() as db:
                # Get author info
                stmt = select(User).where(User.id == UUID(author_id))
                result = await db.execute(stmt)
                author = result.scalar_one_or_none()

                if not author:
                    logger.warning(f"Author {author_id} not found")
                    return

                # 1. Check for mentions
                mentions = notification_manager.extract_mentions(content)
                if mentions:
                    # Get mentioned users
                    stmt = select(User).where(User.username.in_(mentions))
                    result = await db.execute(stmt)
                    mentioned_users = result.scalars().all()

                    for mentioned_user in mentioned_users:
                        # Don't notify if user mentions themselves
                        if mentioned_user.id == UUID(author_id):
                            continue

                        # Check if user wants mention notifications
                        should_notify = await notification_manager.should_notify(
                            db, mentioned_user.id, NotificationType.MENTION
                        )

                        if should_notify:
                            await notification_manager.create_notification(
                                db=db,
                                user_id=mentioned_user.id,
                                notification_type=NotificationType.MENTION,
                                title=f"{author.display_name} mentioned you",
                                message=f"@{author.username}: {content[:100]}{'...' if len(content) > 100 else ''}",
                                reference_id=UUID(message_id),
                                reference_type="message",
                                actor_id=UUID(author_id),
                            )

                # 2. Check for thread replies
                if parent_message_id:
                    # Get parent message to find its author
                    stmt = select(Message).where(Message.id == UUID(parent_message_id))
                    result = await db.execute(stmt)
                    parent_message = result.scalar_one_or_none()

                    if parent_message and parent_message.author_id != UUID(author_id):
                        # Check if parent author wants reply notifications
                        should_notify = await notification_manager.should_notify(
                            db, parent_message.author_id, NotificationType.REPLY
                        )

                        if should_notify:
                            await notification_manager.create_notification(
                                db=db,
                                user_id=parent_message.author_id,
                                notification_type=NotificationType.REPLY,
                                title=f"{author.display_name} replied to your message",
                                message=f"{content[:100]}{'...' if len(content) > 100 else ''}",
                                reference_id=UUID(message_id),
                                reference_type="message",
                                actor_id=UUID(author_id),
                            )

        except Exception as e:
            logger.error(f"Error handling message.created event: {e}", exc_info=True)

    async def _handle_reaction_added(self, data: Dict):
        """Handle reaction.added event.

        Creates notification for message author when someone reacts.
        """
        try:
            message_id = data.get("message_id")
            user_id = data.get("user_id")
            emoji = data.get("emoji")

            if not message_id or not user_id or not emoji:
                logger.warning("reaction.added event missing required fields")
                return

            async with db_base.async_session_factory() as db:
                # Get the message
                stmt = select(Message).where(Message.id == UUID(message_id))
                result = await db.execute(stmt)
                message = result.scalar_one_or_none()

                if not message:
                    logger.warning(f"Message {message_id} not found")
                    return

                # Don't notify if user reacts to their own message
                if message.author_id == UUID(user_id):
                    return

                # Get reactor info
                stmt = select(User).where(User.id == UUID(user_id))
                result = await db.execute(stmt)
                reactor = result.scalar_one_or_none()

                if not reactor:
                    logger.warning(f"User {user_id} not found")
                    return

                # Check if message author wants reaction notifications
                should_notify = await notification_manager.should_notify(
                    db, message.author_id, NotificationType.REACTION
                )

                if should_notify:
                    await notification_manager.create_notification(
                        db=db,
                        user_id=message.author_id,
                        notification_type=NotificationType.REACTION,
                        title=f"{reactor.display_name} reacted to your message",
                        message=f"Reacted with {emoji}",
                        reference_id=UUID(message_id),
                        reference_type="message",
                        actor_id=UUID(user_id),
                    )

        except Exception as e:
            logger.error(f"Error handling reaction.added event: {e}", exc_info=True)

    async def _handle_channel_member_added(self, data: Dict):
        """Handle channel.member_added event.

        Creates notification for user when added to a channel.
        """
        try:
            channel_id = data.get("channel_id")
            user_id = data.get("user_id")
            channel_name = data.get("channel_name", "a channel")
            added_by_id = data.get("added_by_id")

            if not channel_id or not user_id:
                logger.warning("channel.member_added event missing required fields")
                return

            async with db_base.async_session_factory() as db:
                # Check if user wants channel update notifications
                should_notify = await notification_manager.should_notify(
                    db, UUID(user_id), NotificationType.CHANNEL_INVITE
                )

                if should_notify:
                    # Get who added them (if available)
                    adder_name = "Someone"
                    if added_by_id:
                        stmt = select(User).where(User.id == UUID(added_by_id))
                        result = await db.execute(stmt)
                        adder = result.scalar_one_or_none()
                        if adder:
                            adder_name = adder.display_name

                    await notification_manager.create_notification(
                        db=db,
                        user_id=UUID(user_id),
                        notification_type=NotificationType.CHANNEL_INVITE,
                        title=f"Added to #{channel_name}",
                        message=f"{adder_name} added you to #{channel_name}",
                        reference_id=UUID(channel_id),
                        reference_type="channel",
                        actor_id=UUID(added_by_id) if added_by_id else None,
                    )

        except Exception as e:
            logger.error(
                f"Error handling channel.member_added event: {e}", exc_info=True
            )


# Global consumer instance
kafka_consumer = KafkaConsumerService()
