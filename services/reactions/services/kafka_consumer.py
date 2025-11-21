"""Kafka consumer for processing message events."""

import asyncio
import json
import logging
from typing import Dict

from aiokafka import AIOKafkaConsumer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Reaction
from shared.database.base import async_session_factory

from ..config import settings

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

                    # Handle different event types
                    if event_type == "message.deleted":
                        await self._handle_message_deleted(data)

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)

        except Exception as e:
            if self.running:
                logger.error(f"Consumer loop error: {e}", exc_info=True)

    async def _handle_message_deleted(self, data: Dict):
        """Handle message.deleted event by removing all reactions.

        Args:
            data: Event data containing message_id
        """
        try:
            message_id = data.get("message_id")
            if not message_id:
                logger.warning("message.deleted event missing message_id")
                return

            # Delete all reactions for this message
            async with async_session_factory() as session:
                stmt = delete(Reaction).where(Reaction.message_id == message_id)
                result = await session.execute(stmt)
                await session.commit()

                deleted_count = result.rowcount
                if deleted_count > 0:
                    logger.info(
                        f"Deleted {deleted_count} reactions for message {message_id}"
                    )

        except Exception as e:
            logger.error(f"Error handling message.deleted event: {e}", exc_info=True)


# Global consumer instance
kafka_consumer = KafkaConsumerService()
