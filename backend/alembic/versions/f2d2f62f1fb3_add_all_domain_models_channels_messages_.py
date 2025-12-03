"""Add all domain models - channels, messages, threads, reactions, files, admin

Revision ID: f2d2f62f1fb3
Revises: a4fe540baa63
Create Date: 2025-11-18 17:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f2d2f62f1fb3"
down_revision: Union[str, Sequence[str], None] = "a4fe540baa63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create all domain tables."""

    # Create enums using raw SQL with DO block for idempotency
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE channeltype AS ENUM ('PUBLIC', 'PRIVATE', 'DIRECT');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE messagetype AS ENUM ('TEXT', 'SYSTEM', 'FILE');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE moderationaction AS ENUM ('WARN', 'MUTE', 'SUSPEND', 'DELETE_MESSAGE', 'DELETE_CHANNEL');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # 1. Create channels table (no dependencies)
    op.create_table(
        "channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("channel_type", sa.String(length=20), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_channels_created_by_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_channels"),
    )
    op.create_index("ix_channels_channel_type", "channels", ["channel_type"])
    op.create_index("ix_channels_created_at", "channels", ["created_at"])
    op.create_index("ix_channels_deleted_at", "channels", ["deleted_at"])
    op.create_index("ix_channels_name", "channels", ["name"])

    # 2. Create messages table (depends on channels, but not threads yet)
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("message_type", sa.String(length=20), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name="fk_messages_author_id_users", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["channels.id"], name="fk_messages_channel_id_channels", ondelete="CASCADE"
        ),
        # Note: thread_id foreign key will be added after threads table is created
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
    )
    op.create_index("ix_messages_author_id", "messages", ["author_id"])
    op.create_index("ix_messages_channel_id_created_at", "messages", ["channel_id", "created_at"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index("ix_messages_deleted_at", "messages", ["deleted_at"])
    op.create_index("ix_messages_message_type", "messages", ["message_type"])
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"])

    # 3. Create threads table (depends on messages)
    op.create_table(
        "threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("root_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reply_count", sa.Integer(), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False),
        sa.Column("last_reply_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["root_message_id"],
            ["messages.id"],
            name="fk_threads_root_message_id_messages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_threads"),
        sa.UniqueConstraint("root_message_id", name="uq_threads_root_message_id"),
    )
    op.create_index("ix_threads_created_at", "threads", ["created_at"])
    op.create_index("ix_threads_last_reply_at", "threads", ["last_reply_at"])

    # 4. Now add the circular foreign key from messages to threads
    op.create_foreign_key(
        "fk_messages_thread_id_threads", "messages", "threads", ["thread_id"], ["id"], ondelete="SET NULL"
    )

    # 5. Create files table (depends on users)
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("bucket", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=1024), nullable=True),
        sa.Column("scan_status", sa.String(length=50), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name="fk_files_uploaded_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_files"),
        sa.UniqueConstraint("storage_key", name="uq_files_storage_key"),
    )
    op.create_index("ix_files_created_at", "files", ["created_at"])
    op.create_index("ix_files_deleted_at", "files", ["deleted_at"])
    op.create_index("ix_files_mime_type", "files", ["mime_type"])
    op.create_index("ix_files_scan_status", "files", ["scan_status"])
    op.create_index("ix_files_uploaded_by_id", "files", ["uploaded_by_id"])

    # 6. Create channel_members table (depends on channels and users)
    op.create_table(
        "channel_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("muted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.id"],
            name="fk_channel_members_channel_id_channels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_channel_members_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_channel_members"),
        sa.UniqueConstraint("channel_id", "user_id", name="uq_channel_members_channel_user"),
    )
    op.create_index("ix_channel_members_channel_id", "channel_members", ["channel_id"])
    op.create_index("ix_channel_members_created_at", "channel_members", ["created_at"])
    op.create_index("ix_channel_members_user_id", "channel_members", ["user_id"])

    # 7. Create message_attachments table (depends on messages and files)
    op.create_table(
        "message_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            name="fk_message_attachments_file_id_files",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="fk_message_attachments_message_id_messages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_message_attachments"),
    )
    op.create_index("ix_message_attachments_created_at", "message_attachments", ["created_at"])
    op.create_index("ix_message_attachments_file_id", "message_attachments", ["file_id"])
    op.create_index("ix_message_attachments_message_id", "message_attachments", ["message_id"])

    # 8. Create reactions table (depends on messages and users)
    op.create_table(
        "reactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("emoji", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], name="fk_reactions_message_id_messages", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_reactions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reactions"),
        sa.UniqueConstraint("message_id", "user_id", "emoji", name="uq_reactions_message_user_emoji"),
    )
    op.create_index("ix_reactions_created_at", "reactions", ["created_at"])
    op.create_index("ix_reactions_emoji", "reactions", ["emoji"])
    op.create_index("ix_reactions_message_id", "reactions", ["message_id"])
    op.create_index("ix_reactions_user_id", "reactions", ["user_id"])

    # 9. Create audit_logs table (depends on users)
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name="fk_audit_logs_actor_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])

    # 10. Create moderation_actions table (depends on users)
    op.create_table(
        "moderation_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("moderator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["moderator_id"],
            ["users.id"],
            name="fk_moderation_actions_moderator_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_id"],
            ["users.id"],
            name="fk_moderation_actions_revoked_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            name="fk_moderation_actions_target_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_actions"),
    )
    op.create_index("ix_moderation_actions_action_type", "moderation_actions", ["action_type"])
    op.create_index("ix_moderation_actions_created_at", "moderation_actions", ["created_at"])
    op.create_index("ix_moderation_actions_expires_at", "moderation_actions", ["expires_at"])
    op.create_index("ix_moderation_actions_is_active", "moderation_actions", ["is_active"])
    op.create_index("ix_moderation_actions_moderator_id", "moderation_actions", ["moderator_id"])
    op.create_index(
        "ix_moderation_actions_target_user_id", "moderation_actions", ["target_user_id"]
    )


def downgrade() -> None:
    """Downgrade schema - drop all domain tables."""
    # Drop tables in reverse order
    op.drop_index("ix_moderation_actions_target_user_id", table_name="moderation_actions")
    op.drop_index("ix_moderation_actions_moderator_id", table_name="moderation_actions")
    op.drop_index("ix_moderation_actions_is_active", table_name="moderation_actions")
    op.drop_index("ix_moderation_actions_expires_at", table_name="moderation_actions")
    op.drop_index("ix_moderation_actions_created_at", table_name="moderation_actions")
    op.drop_index("ix_moderation_actions_action_type", table_name="moderation_actions")
    op.drop_table("moderation_actions")

    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_reactions_user_id", table_name="reactions")
    op.drop_index("ix_reactions_message_id", table_name="reactions")
    op.drop_index("ix_reactions_emoji", table_name="reactions")
    op.drop_index("ix_reactions_created_at", table_name="reactions")
    op.drop_table("reactions")

    op.drop_index("ix_message_attachments_message_id", table_name="message_attachments")
    op.drop_index("ix_message_attachments_file_id", table_name="message_attachments")
    op.drop_index("ix_message_attachments_created_at", table_name="message_attachments")
    op.drop_table("message_attachments")

    op.drop_index("ix_channel_members_user_id", table_name="channel_members")
    op.drop_index("ix_channel_members_created_at", table_name="channel_members")
    op.drop_index("ix_channel_members_channel_id", table_name="channel_members")
    op.drop_table("channel_members")

    op.drop_index("ix_files_uploaded_by_id", table_name="files")
    op.drop_index("ix_files_scan_status", table_name="files")
    op.drop_index("ix_files_mime_type", table_name="files")
    op.drop_index("ix_files_deleted_at", table_name="files")
    op.drop_index("ix_files_created_at", table_name="files")
    op.drop_table("files")

    # Drop circular foreign key first
    op.drop_constraint("fk_messages_thread_id_threads", "messages", type_="foreignkey")

    op.drop_index("ix_threads_last_reply_at", table_name="threads")
    op.drop_index("ix_threads_created_at", table_name="threads")
    op.drop_table("threads")

    op.drop_index("ix_messages_thread_id", table_name="messages")
    op.drop_index("ix_messages_message_type", table_name="messages")
    op.drop_index("ix_messages_deleted_at", table_name="messages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_channel_id_created_at", table_name="messages")
    op.drop_index("ix_messages_author_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_channels_name", table_name="channels")
    op.drop_index("ix_channels_deleted_at", table_name="channels")
    op.drop_index("ix_channels_created_at", table_name="channels")
    op.drop_index("ix_channels_channel_type", table_name="channels")
    op.drop_table("channels")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS moderationaction")
    op.execute("DROP TYPE IF EXISTS messagetype")
    op.execute("DROP TYPE IF EXISTS channeltype")
