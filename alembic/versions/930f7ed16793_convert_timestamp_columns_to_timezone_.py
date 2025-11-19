"""convert timestamp columns to timezone aware

Revision ID: 930f7ed16793
Revises: f2d2f62f1fb3
Create Date: 2025-11-18 23:13:06.721774

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "930f7ed16793"
down_revision: Union[str, Sequence[str], None] = "f2d2f62f1fb3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert timestamp columns to timezone-aware."""
    # Users table
    op.execute("ALTER TABLE users ALTER COLUMN created_at TYPE timestamp with time zone")
    op.execute("ALTER TABLE users ALTER COLUMN updated_at TYPE timestamp with time zone")

    # Messages table
    op.execute("ALTER TABLE messages ALTER COLUMN created_at TYPE timestamp with time zone")
    op.execute("ALTER TABLE messages ALTER COLUMN updated_at TYPE timestamp with time zone")

    # Channels table
    op.execute("ALTER TABLE channels ALTER COLUMN created_at TYPE timestamp with time zone")
    op.execute("ALTER TABLE channels ALTER COLUMN updated_at TYPE timestamp with time zone")

    # Reactions table
    op.execute("ALTER TABLE reactions ALTER COLUMN created_at TYPE timestamp with time zone")

    # Files table
    op.execute("ALTER TABLE files ALTER COLUMN created_at TYPE timestamp with time zone")
    op.execute("ALTER TABLE files ALTER COLUMN updated_at TYPE timestamp with time zone")


def downgrade() -> None:
    """Convert timestamp columns back to timezone-naive."""
    # Files table
    op.execute("ALTER TABLE files ALTER COLUMN updated_at TYPE timestamp without time zone")
    op.execute("ALTER TABLE files ALTER COLUMN created_at TYPE timestamp without time zone")

    # Reactions table
    op.execute("ALTER TABLE reactions ALTER COLUMN created_at TYPE timestamp without time zone")

    # Channels table
    op.execute("ALTER TABLE channels ALTER COLUMN updated_at TYPE timestamp without time zone")
    op.execute("ALTER TABLE channels ALTER COLUMN created_at TYPE timestamp without time zone")

    # Messages table
    op.execute("ALTER TABLE messages ALTER COLUMN updated_at TYPE timestamp without time zone")
    op.execute("ALTER TABLE messages ALTER COLUMN created_at TYPE timestamp without time zone")

    # Users table
    op.execute("ALTER TABLE users ALTER COLUMN updated_at TYPE timestamp without time zone")
    op.execute("ALTER TABLE users ALTER COLUMN created_at TYPE timestamp without time zone")
