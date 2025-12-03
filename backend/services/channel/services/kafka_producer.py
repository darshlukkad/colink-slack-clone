"""Kafka producer for Channel Service events."""

import json
import logging
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaProducer

from config import settings

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka producer for publishing channel events."""

    def __init__(self):
        """Initialize Kafka producer."""
        self.producer: Optional[AIOKafkaProducer] = None
        self.bootstrap_servers = settings.kafka_bootstrap_servers

    async def start(self):
        """Start Kafka producer."""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self.producer.start()
            logger.info(f"Kafka producer started: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            raise

    async def stop(self):
        """Stop Kafka producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

    async def publish_channel_event(
        self,
        event_type: str,
        channel_data: Dict[str, Any],
        key: Optional[str] = None,
    ):
        """Publish a channel event to Kafka.

        Args:
            event_type: Type of event (e.g., 'channel.created', 'member.added')
            channel_data: Event data
            key: Partition key (typically channel_id)
        """
        if not self.producer:
            logger.warning("Kafka producer not initialized, skipping event publish")
            return

        try:
            event = {
                "event_type": event_type,
                "data": channel_data,
            }

            # Publish to 'channels' topic
            await self.producer.send(
                topic="channels",
                value=event,
                key=key.encode("utf-8") if key else None,
            )

            logger.debug(f"Published {event_type} event to Kafka: {channel_data}")

        except Exception as e:
            logger.error(f"Failed to publish event to Kafka: {e}")
            # Don't raise - we don't want to fail the request if Kafka is down


# Global instance
kafka_producer = KafkaProducer()
