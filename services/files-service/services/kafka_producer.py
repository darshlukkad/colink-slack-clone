"""Kafka producer for publishing file events."""

import json
import logging
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaProducer

from config import settings

logger = logging.getLogger(__name__)


class KafkaProducerService:
    """Kafka producer service for publishing events."""

    def __init__(self):
        """Initialize Kafka producer."""
        self.producer: Optional[AIOKafkaProducer] = None
        self.bootstrap_servers = settings.kafka_bootstrap_servers

    async def start(self):
        """Start the Kafka producer."""
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
        """Stop the Kafka producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

    async def publish_event(
        self,
        topic: str,
        key: str,
        event_type: str,
        data: Dict[str, Any],
    ):
        """Publish an event to Kafka.

        Args:
            topic: Kafka topic name
            key: Message key (for partitioning)
            event_type: Type of event (e.g., 'file.uploaded')
            data: Event payload
        """
        if not self.producer:
            logger.error("Kafka producer not initialized")
            return

        try:
            message = {
                "event_type": event_type,
                "data": data,
            }

            await self.producer.send(
                topic=topic,
                value=message,
                key=key.encode("utf-8"),
            )

            logger.info(f"Published event: {event_type} to topic: {topic}")

        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")


# Global producer instance
kafka_producer = KafkaProducerService()
