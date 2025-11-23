"""Kafka producer for publishing notification events."""

import json
import logging
from typing import Any, Dict
from uuid import UUID

from aiokafka import AIOKafkaProducer

from ..config import settings

logger = logging.getLogger(__name__)


class KafkaProducerService:
    """Kafka producer service for notifications."""

    def __init__(self):
        """Initialize Kafka producer."""
        self.producer = None
        self.bootstrap_servers = settings.kafka_bootstrap_servers

    async def start(self):
        """Start the Kafka producer."""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            await self.producer.start()
            logger.info(f"Kafka producer started: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            raise

    async def stop(self):
        """Stop the Kafka producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

    async def publish_event(self, topic: str, event_type: str, data: Dict[str, Any]):
        """Publish an event to Kafka."""
        if not self.producer:
            logger.warning("Producer not initialized, skipping event publish")
            return

        try:
            event = {"event_type": event_type, "data": data}

            await self.producer.send_and_wait(topic, value=event)
            logger.debug(f"Published {event_type} to {topic}")

        except Exception as e:
            logger.error(f"Failed to publish event {event_type} to {topic}: {e}")


# Global producer instance
kafka_producer = KafkaProducerService()
