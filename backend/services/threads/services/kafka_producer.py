"""Kafka producer for publishing thread events."""

import json
import logging
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaProducer

from ..config import settings

logger = logging.getLogger(__name__)


class KafkaProducerService:
    """Service for publishing events to Kafka."""

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
                key_serializer=lambda v: v.encode("utf-8") if v else None,
            )
            await self.producer.start()
            logger.info(f"Kafka producer started: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}", exc_info=True)
            # Don't raise - service should work without Kafka

    async def stop(self):
        """Stop Kafka producer."""
        if self.producer:
            try:
                await self.producer.stop()
                logger.info("Kafka producer stopped")
            except Exception as e:
                logger.error(f"Error stopping Kafka producer: {e}", exc_info=True)

    async def publish_event(
        self,
        topic: str,
        event_type: str,
        data: Dict[str, Any],
        key: Optional[str] = None,
    ):
        """Publish an event to Kafka.

        Args:
            topic: Kafka topic name
            event_type: Type of event (e.g., 'thread.created', 'thread.reply_added')
            data: Event data to publish
            key: Optional partition key (e.g., thread_id)
        """
        if not self.producer:
            logger.warning("Kafka producer not available, skipping event publish")
            return

        try:
            event = {
                "event_type": event_type,
                "data": data,
            }

            await self.producer.send(
                topic=topic,
                value=event,
                key=key,
            )
            logger.debug(f"Published {event_type} event to Kafka topic {topic}")

        except Exception as e:
            logger.error(f"Failed to publish event to Kafka: {e}", exc_info=True)


# Global Kafka producer instance
kafka_producer = KafkaProducerService()
