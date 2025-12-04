"""
BI Analytics Router for Message Service.

This module provides endpoints for comprehensive usage analytics including:
- Total counts of users, channels, and messages
- Top channels by message count
- Daily message counts for the last 7 days
- Most active users
- Channel distribution by type
- Activity trends and growth metrics
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, cast, Date, case
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import (
    Channel,
    ChannelMember,
    Message,
    User,
    get_db,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


# ============================================================================
# Response Models for BI Analytics
# ============================================================================


class TotalsResponse(BaseModel):
    """Total counts for users, channels, and messages."""
    total_users: int = Field(..., description="Total number of users")
    total_channels: int = Field(..., description="Total number of channels")
    total_messages: int = Field(..., description="Total number of messages")
    active_users_today: int = Field(0, description="Users who sent messages today")
    messages_today: int = Field(0, description="Messages sent today")
    avg_messages_per_day: float = Field(0, description="Average messages per day (last 7 days)")


class TopChannelResponse(BaseModel):
    """Channel with message count for top channels list."""
    channel_id: str = Field(..., description="Channel UUID")
    channel_name: str = Field(..., description="Channel name")
    message_count: int = Field(..., description="Number of messages in channel")
    member_count: int = Field(0, description="Number of members in channel")


class DailyMessageResponse(BaseModel):
    """Daily message count for a specific date."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    count: int = Field(..., description="Number of messages on this date")


class TopUserResponse(BaseModel):
    """User with message count for most active users."""
    user_id: str = Field(..., description="User UUID")
    username: str = Field(..., description="Username")
    display_name: str = Field(..., description="Display name")
    message_count: int = Field(..., description="Number of messages sent")


class ChannelTypeDistribution(BaseModel):
    """Distribution of channels by type."""
    public: int = Field(0, description="Number of public channels")
    private: int = Field(0, description="Number of private channels")
    direct: int = Field(0, description="Number of direct message channels")


class HourlyActivityResponse(BaseModel):
    """Message count by hour of day."""
    hour: int = Field(..., description="Hour of day (0-23)")
    count: int = Field(..., description="Number of messages in this hour")


class AnalyticsSummaryResponse(BaseModel):
    """Complete analytics summary response."""
    totals: TotalsResponse = Field(..., description="Total counts and metrics")
    top_channels: List[TopChannelResponse] = Field(..., description="Top 5 channels by message count")
    daily_messages: List[DailyMessageResponse] = Field(..., description="Message counts per day for last 7 days")
    top_users: List[TopUserResponse] = Field([], description="Top 5 most active users")
    channel_distribution: ChannelTypeDistribution = Field(..., description="Channels by type")
    hourly_activity: List[HourlyActivityResponse] = Field([], description="Activity by hour of day")


# ============================================================================
# Analytics Endpoints
# ============================================================================


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Get BI Analytics Summary",
    description="Returns comprehensive analytics data for the BI dashboard.",
)
async def get_analytics_summary(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummaryResponse:
    """
    Get comprehensive analytics summary for the BI dashboard.
    
    Returns:
    - totals: Total counts and activity metrics
    - top_channels: Top 5 channels ordered by message count
    - daily_messages: Message counts per day for the last 7 days
    - top_users: Top 5 most active users by message count
    - channel_distribution: Breakdown of channels by type
    - hourly_activity: Message distribution by hour of day
    """
    try:
        today = datetime.now(timezone.utc).date()
        seven_days_ago = today - timedelta(days=6)

        # Get total users count
        users_stmt = select(func.count(User.id))
        users_result = await db.execute(users_stmt)
        total_users = users_result.scalar() or 0

        # Get total channels count (exclude deleted channels)
        channels_stmt = select(func.count(Channel.id)).where(Channel.deleted_at.is_(None))
        channels_result = await db.execute(channels_stmt)
        total_channels = channels_result.scalar() or 0

        # Get total messages count (exclude deleted messages)
        messages_stmt = select(func.count(Message.id)).where(Message.deleted_at.is_(None))
        messages_result = await db.execute(messages_stmt)
        total_messages = messages_result.scalar() or 0

        # Get messages today
        messages_today_stmt = (
            select(func.count(Message.id))
            .where(Message.deleted_at.is_(None))
            .where(cast(Message.created_at, Date) == today)
        )
        messages_today_result = await db.execute(messages_today_stmt)
        messages_today = messages_today_result.scalar() or 0

        # Get active users today (users who sent messages today)
        active_users_stmt = (
            select(func.count(func.distinct(Message.author_id)))
            .where(Message.deleted_at.is_(None))
            .where(cast(Message.created_at, Date) == today)
        )
        active_users_result = await db.execute(active_users_stmt)
        active_users_today = active_users_result.scalar() or 0

        # Calculate average messages per day (last 7 days)
        avg_messages_stmt = (
            select(func.count(Message.id))
            .where(Message.deleted_at.is_(None))
            .where(cast(Message.created_at, Date) >= seven_days_ago)
        )
        avg_messages_result = await db.execute(avg_messages_stmt)
        total_last_7_days = avg_messages_result.scalar() or 0
        avg_messages_per_day = round(total_last_7_days / 7, 1)

        totals = TotalsResponse(
            total_users=total_users,
            total_channels=total_channels,
            total_messages=total_messages,
            active_users_today=active_users_today,
            messages_today=messages_today,
            avg_messages_per_day=avg_messages_per_day,
        )

        # Get top 5 channels by message count with member count
        top_channels_stmt = (
            select(
                Channel.id,
                Channel.name,
                func.count(func.distinct(Message.id)).label("message_count"),
                func.count(func.distinct(ChannelMember.user_id)).label("member_count"),
            )
            .outerjoin(Message, (Message.channel_id == Channel.id) & (Message.deleted_at.is_(None)))
            .outerjoin(ChannelMember, (ChannelMember.channel_id == Channel.id) & (ChannelMember.left_at.is_(None)))
            .where(Channel.deleted_at.is_(None))
            .group_by(Channel.id, Channel.name)
            .order_by(func.count(func.distinct(Message.id)).desc())
            .limit(5)
        )
        top_channels_result = await db.execute(top_channels_stmt)
        top_channels_rows = top_channels_result.all()

        top_channels = [
            TopChannelResponse(
                channel_id=str(row.id),
                channel_name=row.name or "Unnamed Channel",
                message_count=row.message_count or 0,
                member_count=row.member_count or 0,
            )
            for row in top_channels_rows
        ]

        # Get daily message counts for the last 7 days
        daily_stmt = (
            select(
                cast(Message.created_at, Date).label("date"),
                func.count(Message.id).label("count"),
            )
            .where(Message.deleted_at.is_(None))
            .where(cast(Message.created_at, Date) >= seven_days_ago)
            .group_by(cast(Message.created_at, Date))
            .order_by(cast(Message.created_at, Date))
        )
        daily_result = await db.execute(daily_stmt)
        daily_rows = daily_result.all()

        # Create a dict for quick lookup
        daily_counts = {str(row.date): row.count for row in daily_rows}

        # Fill in all 7 days (including days with 0 messages)
        daily_messages = []
        for i in range(7):
            date = seven_days_ago + timedelta(days=i)
            date_str = str(date)
            count = daily_counts.get(date_str, 0)
            daily_messages.append(DailyMessageResponse(date=date_str, count=count))

        # Get top 5 most active users
        top_users_stmt = (
            select(
                User.id,
                User.username,
                User.display_name,
                func.count(Message.id).label("message_count"),
            )
            .join(Message, Message.author_id == User.id)
            .where(Message.deleted_at.is_(None))
            .group_by(User.id, User.username, User.display_name)
            .order_by(func.count(Message.id).desc())
            .limit(5)
        )
        top_users_result = await db.execute(top_users_stmt)
        top_users_rows = top_users_result.all()

        top_users = [
            TopUserResponse(
                user_id=str(row.id),
                username=row.username,
                display_name=row.display_name or row.username,
                message_count=row.message_count,
            )
            for row in top_users_rows
        ]

        # Get channel distribution by type
        channel_dist_stmt = (
            select(
                Channel.channel_type,
                func.count(Channel.id).label("count"),
            )
            .where(Channel.deleted_at.is_(None))
            .group_by(Channel.channel_type)
        )
        channel_dist_result = await db.execute(channel_dist_stmt)
        channel_dist_rows = channel_dist_result.all()

        channel_distribution = ChannelTypeDistribution(public=0, private=0, direct=0)
        for row in channel_dist_rows:
            if row.channel_type == "PUBLIC":
                channel_distribution.public = row.count
            elif row.channel_type == "PRIVATE":
                channel_distribution.private = row.count
            elif row.channel_type == "DIRECT":
                channel_distribution.direct = row.count

        # Get hourly activity (messages by hour of day)
        hourly_stmt = (
            select(
                func.extract('hour', Message.created_at).label("hour"),
                func.count(Message.id).label("count"),
            )
            .where(Message.deleted_at.is_(None))
            .where(cast(Message.created_at, Date) >= seven_days_ago)
            .group_by(func.extract('hour', Message.created_at))
            .order_by(func.extract('hour', Message.created_at))
        )
        hourly_result = await db.execute(hourly_stmt)
        hourly_rows = hourly_result.all()

        # Create hourly activity with all 24 hours
        hourly_counts = {int(row.hour): row.count for row in hourly_rows}
        hourly_activity = [
            HourlyActivityResponse(hour=h, count=hourly_counts.get(h, 0))
            for h in range(24)
        ]

        logger.info(
            f"Analytics summary: {total_users} users, {total_channels} channels, "
            f"{total_messages} messages, {len(top_channels)} top channels"
        )

        return AnalyticsSummaryResponse(
            totals=totals,
            top_channels=top_channels,
            daily_messages=daily_messages,
            top_users=top_users,
            channel_distribution=channel_distribution,
            hourly_activity=hourly_activity,
        )

    except Exception as e:
        logger.error(f"Error fetching analytics summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch analytics data",
        )
