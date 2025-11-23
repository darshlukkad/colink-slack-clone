"""Notification manager - business logic for notifications."""

import logging
import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

import redis.asyncio as redis
from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Notification, NotificationPreference, User

from ..config import settings
from ..schemas.notifications import NotificationType

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notification operations."""

    def __init__(self):
        """Initialize notification manager."""
        self.redis_client: Optional[redis.Redis] = None

    async def init_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connected for notifications cache")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self.redis_client = None

    async def close_redis(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()

    async def create_notification(
        self,
        db: AsyncSession,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        reference_id: Optional[UUID] = None,
        reference_type: Optional[str] = None,
        actor_id: Optional[UUID] = None,
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            id=uuid4(),
            user_id=user_id,
            type=notification_type.value,
            title=title,
            message=message,
            reference_id=reference_id,
            reference_type=reference_type,
            actor_id=actor_id,
            is_read=False,
            created_at=datetime.utcnow(),
        )

        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        # Invalidate unread count cache
        await self._invalidate_unread_cache(user_id)

        logger.info(f"Created notification {notification.id} for user {user_id}")
        return notification

    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        is_read: Optional[bool] = None,
        notification_type: Optional[NotificationType] = None,
    ) -> tuple[List[Notification], int]:
        """Get user notifications with pagination and filters."""
        # Build query
        query = select(Notification).where(
            and_(Notification.user_id == user_id, Notification.deleted_at.is_(None))
        )

        # Apply filters
        if is_read is not None:
            query = query.where(Notification.is_read == is_read)

        if notification_type:
            query = query.where(Notification.type == notification_type.value)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total_count = result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(desc(Notification.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        notifications = result.scalars().all()

        return list(notifications), total_count

    async def get_unread_count(self, db: AsyncSession, user_id: UUID) -> int:
        """Get unread notification count with Redis caching."""
        # Try cache first
        if self.redis_client:
            try:
                cache_key = f"notification:unread:{user_id}"
                cached = await self.redis_client.get(cache_key)
                if cached is not None:
                    return int(cached)
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}")

        # Query database
        query = select(func.count()).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False,
                Notification.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        count = result.scalar() or 0

        # Cache the result
        if self.redis_client:
            try:
                cache_key = f"notification:unread:{user_id}"
                await self.redis_client.setex(
                    cache_key, settings.redis_cache_ttl, str(count)
                )
            except Exception as e:
                logger.warning(f"Redis cache write failed: {e}")

        return count

    async def mark_as_read(
        self, db: AsyncSession, notification_id: UUID, user_id: UUID
    ) -> Optional[Notification]:
        """Mark a notification as read."""
        query = select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        notification = result.scalar_one_or_none()

        if not notification:
            return None

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            await db.commit()
            await db.refresh(notification)

            # Invalidate cache
            await self._invalidate_unread_cache(user_id)

        return notification

    async def mark_all_as_read(self, db: AsyncSession, user_id: UUID) -> int:
        """Mark all unread notifications as read."""
        stmt = (
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                    Notification.deleted_at.is_(None),
                )
            )
            .values(is_read=True, read_at=datetime.utcnow())
        )

        result = await db.execute(stmt)
        await db.commit()

        # Invalidate cache
        await self._invalidate_unread_cache(user_id)

        return result.rowcount

    async def delete_notification(
        self, db: AsyncSession, notification_id: UUID, user_id: UUID
    ) -> bool:
        """Soft delete a notification."""
        query = select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        notification = result.scalar_one_or_none()

        if not notification:
            return False

        notification.deleted_at = datetime.utcnow()
        await db.commit()

        # Invalidate cache if it was unread
        if not notification.is_read:
            await self._invalidate_unread_cache(user_id)

        return True

    async def get_user_preferences(
        self, db: AsyncSession, user_id: UUID
    ) -> NotificationPreference:
        """Get user notification preferences, creating defaults if not exists."""
        query = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id
        )
        result = await db.execute(query)
        prefs = result.scalar_one_or_none()

        if not prefs:
            # Create default preferences
            prefs = NotificationPreference(
                id=uuid4(),
                user_id=user_id,
                mentions=settings.default_mentions_enabled,
                reactions=settings.default_reactions_enabled,
                replies=settings.default_replies_enabled,
                direct_messages=settings.default_direct_messages_enabled,
                channel_updates=settings.default_channel_updates_enabled,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(prefs)
            await db.commit()
            await db.refresh(prefs)

        return prefs

    async def update_user_preferences(
        self,
        db: AsyncSession,
        user_id: UUID,
        mentions: Optional[bool] = None,
        reactions: Optional[bool] = None,
        replies: Optional[bool] = None,
        direct_messages: Optional[bool] = None,
        channel_updates: Optional[bool] = None,
    ) -> NotificationPreference:
        """Update user notification preferences."""
        prefs = await self.get_user_preferences(db, user_id)

        if mentions is not None:
            prefs.mentions = mentions
        if reactions is not None:
            prefs.reactions = reactions
        if replies is not None:
            prefs.replies = replies
        if direct_messages is not None:
            prefs.direct_messages = direct_messages
        if channel_updates is not None:
            prefs.channel_updates = channel_updates

        prefs.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(prefs)

        return prefs

    async def should_notify(
        self, db: AsyncSession, user_id: UUID, notification_type: NotificationType
    ) -> bool:
        """Check if user should receive a notification of given type."""
        prefs = await self.get_user_preferences(db, user_id)

        type_map = {
            NotificationType.MENTION: prefs.mentions,
            NotificationType.REACTION: prefs.reactions,
            NotificationType.REPLY: prefs.replies,
            NotificationType.DIRECT_MESSAGE: prefs.direct_messages,
            NotificationType.CHANNEL_INVITE: prefs.channel_updates,
        }

        return type_map.get(notification_type, True)

    def extract_mentions(self, content: str) -> List[str]:
        """Extract @username mentions from message content."""
        # Match @username pattern (alphanumeric and underscores)
        pattern = r"@([a-zA-Z0-9_]+)"
        mentions = re.findall(pattern, content)
        return list(set(mentions))  # Remove duplicates

    async def _invalidate_unread_cache(self, user_id: UUID):
        """Invalidate unread count cache for user."""
        if self.redis_client:
            try:
                cache_key = f"notification:unread:{user_id}"
                await self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Redis cache invalidation failed: {e}")


# Global instance
notification_manager = NotificationManager()
