"""
BI Analytics Data Seeder.

This script seeds sample data for the BI analytics dashboard if the database
has too few records (< 5 users or < 20 messages). It creates realistic sample
channels and messages spread over the past few days without breaking existing data.

Usage:
    python seed_analytics_data.py

Can also be run inside a Docker container:
    docker exec colink-message python -m scripts.seed_analytics_data
"""

import asyncio
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Add the backend directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from shared.database.models import (
    Base,
    User,
    Channel,
    ChannelMember,
    ChannelType,
    Message,
    MessageType,
    UserStatus,
    UserRole,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database URL - match the one used by the services
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://colink:colink_password@localhost:5432/colink"
)

# Sample data for seeding
SAMPLE_CHANNELS = [
    {"name": "general", "description": "General discussion and announcements"},
    {"name": "engineering", "description": "Engineering team discussions"},
    {"name": "design", "description": "Design and UX discussions"},
    {"name": "marketing", "description": "Marketing campaigns and strategies"},
    {"name": "random", "description": "Off-topic conversations and fun"},
    {"name": "help-desk", "description": "Get help with any issues"},
    {"name": "announcements", "description": "Important company announcements"},
]

SAMPLE_MESSAGES = [
    "Hey everyone! How's it going?",
    "Just finished the new feature implementation 🚀",
    "Can someone review my PR please?",
    "Great work on the release yesterday!",
    "Anyone up for lunch at noon?",
    "I'll be in meetings most of the afternoon",
    "The new design looks amazing!",
    "Let's sync up later today",
    "Happy Friday! 🎉",
    "Thanks for the help earlier!",
    "Working from home today",
    "The demo went really well!",
    "Anyone seen the latest metrics?",
    "Just deployed the hotfix",
    "Coffee break anyone? ☕",
    "The client loved the presentation",
    "Need some feedback on this mockup",
    "Updated the documentation",
    "Sprint planning starts in 10 mins",
    "Great catch on that bug!",
    "The server is running smoothly now",
    "Can we schedule a quick call?",
    "Just merged the feature branch",
    "Testing the new integration",
    "All tests are passing ✅",
    "Weekend plans anyone?",
    "The new onboarding flow is live",
    "Thanks team for the hard work!",
    "Reviewing the quarterly goals",
    "Let's discuss this in the standup",
]


async def get_async_session():
    """Create an async database session."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session(), engine


async def seed_data():
    """Seed sample data for BI analytics if data is sparse."""
    session, engine = await get_async_session()
    
    try:
        async with session.begin():
            # Check current data counts
            users_count = await session.scalar(select(func.count(User.id)))
            messages_count = await session.scalar(select(func.count(Message.id)))
            channels_count = await session.scalar(select(func.count(Channel.id)))
            
            logger.info(f"Current data: {users_count} users, {channels_count} channels, {messages_count} messages")
            
            # Only seed if data is sparse
            if users_count >= 5 and messages_count >= 20:
                logger.info("Database already has sufficient data. Skipping seeding.")
                return
            
            # Get existing users
            users_result = await session.execute(select(User))
            existing_users = users_result.scalars().all()
            
            if not existing_users:
                logger.warning("No users found. Please create users first (e.g., via Keycloak).")
                return
            
            logger.info(f"Found {len(existing_users)} existing users to use for seeding")
            
            # Create sample channels if needed
            channels_result = await session.execute(select(Channel).where(Channel.deleted_at.is_(None)))
            existing_channels = channels_result.scalars().all()
            
            channels_to_use = list(existing_channels)
            
            if len(existing_channels) < 3:
                logger.info("Creating sample channels...")
                creator = existing_users[0]
                
                for ch_data in SAMPLE_CHANNELS[:5]:  # Create up to 5 sample channels
                    # Check if channel with this name already exists
                    existing = await session.execute(
                        select(Channel).where(Channel.name == ch_data["name"])
                    )
                    if existing.scalar_one_or_none():
                        continue
                    
                    channel = Channel(
                        id=uuid4(),
                        name=ch_data["name"],
                        description=ch_data["description"],
                        channel_type=ChannelType.public.value,
                        created_by_id=creator.id,
                    )
                    session.add(channel)
                    channels_to_use.append(channel)
                    
                    # Add all users as members
                    for user in existing_users:
                        member = ChannelMember(
                            id=uuid4(),
                            channel_id=channel.id,
                            user_id=user.id,
                            is_admin=(user.id == creator.id),
                        )
                        session.add(member)
                
                await session.flush()
                logger.info(f"Created {len(channels_to_use) - len(existing_channels)} new channels")
            
            if not channels_to_use:
                logger.warning("No channels available for seeding messages.")
                return
            
            # Create sample messages spread over the last 7 days
            if messages_count < 20:
                logger.info("Creating sample messages...")
                now = datetime.now(timezone.utc)
                messages_created = 0
                
                # Create 30-50 messages spread across channels and days
                target_messages = max(30, 50 - messages_count)
                
                for i in range(target_messages):
                    # Random timestamp within the last 7 days
                    days_ago = random.randint(0, 6)
                    hours_ago = random.randint(0, 23)
                    minutes_ago = random.randint(0, 59)
                    message_time = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
                    
                    # Pick random user and channel
                    author = random.choice(existing_users)
                    channel = random.choice(channels_to_use)
                    content = random.choice(SAMPLE_MESSAGES)
                    
                    message = Message(
                        id=uuid4(),
                        channel_id=channel.id,
                        author_id=author.id,
                        content=content,
                        message_type=MessageType.TEXT,
                        created_at=message_time,
                        updated_at=message_time,
                    )
                    session.add(message)
                    messages_created += 1
                
                await session.flush()
                logger.info(f"Created {messages_created} sample messages")
            
            await session.commit()
            logger.info("✅ Data seeding completed successfully!")
            
            # Log final counts
            final_users = await session.scalar(select(func.count(User.id)))
            final_channels = await session.scalar(select(func.count(Channel.id)))
            final_messages = await session.scalar(select(func.count(Message.id)))
            logger.info(f"Final data: {final_users} users, {final_channels} channels, {final_messages} messages")
            
    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_data())
