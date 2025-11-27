"""Kafka consumer service for WebSocket events."""

import asyncio
import json
import logging
from typing import Callable

from aiokafka import AIOKafkaConsumer

from config import settings

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    """Service for consuming Kafka messages and broadcasting to WebSocket clients."""

    def __init__(self):
        """Initialize the Kafka consumer service."""
        self.consumer = None
        self.running = False
        self.handlers = {}

    async def start(self):
        """Start the Kafka consumer."""
        try:
            self.consumer = AIOKafkaConsumer(
                settings.kafka_messages_topic,
                settings.kafka_typing_topic,
                settings.kafka_user_status_topic,
                settings.kafka_reactions_topic,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id="websocket-service",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
            )

            await self.consumer.start()
            logger.info("✅ Kafka consumer started successfully")
            self.running = True

            # Start consuming messages
            asyncio.create_task(self._consume_messages())

        except Exception as e:
            logger.error(f"❌ Failed to start Kafka consumer: {e}")
            raise

    async def stop(self):
        """Stop the Kafka consumer."""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")

    def register_handler(self, topic: str, handler: Callable):
        """Register a handler for a specific topic."""
        self.handlers[topic] = handler
        logger.info(f"Registered handler for topic: {topic}")

    async def _consume_messages(self):
        """Consume messages from Kafka and call registered handlers."""
        try:
            async for message in self.consumer:
                topic = message.topic
                data = message.value

                logger.debug(f"📨 Received message from topic {topic}: {data}")

                # Call the registered handler for this topic
                if topic in self.handlers:
                    try:
                        await self.handlers[topic](data)
                    except Exception as e:
                        logger.error(f"Error handling message from {topic}: {e}")

        except asyncio.CancelledError:
            logger.info("Kafka consumer task cancelled")
        except Exception as e:
            logger.error(f"Error consuming Kafka messages: {e}")


# Global instance
kafka_consumer = KafkaConsumerService()
