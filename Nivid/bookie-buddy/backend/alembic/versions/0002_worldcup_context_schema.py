"""world cup context schema

Revision ID: 0002_worldcup_context
Revises: 0001_initial
Create Date: 2026-03-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_worldcup_context"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("competition_stage", sa.String(length=128), nullable=True))
    op.add_column("events", sa.Column("venue_name", sa.String(length=128), nullable=True))
    op.add_column("events", sa.Column("venue_city", sa.String(length=128), nullable=True))
    op.add_column("events", sa.Column("venue_country", sa.String(length=128), nullable=True))
    op.add_column("events", sa.Column("venue_lat", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("venue_lon", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("context_payload", sa.JSON(), nullable=True))

    op.add_column("recommendations", sa.Column("model_components", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "model_components")

    op.drop_column("events", "context_payload")
    op.drop_column("events", "venue_lon")
    op.drop_column("events", "venue_lat")
    op.drop_column("events", "venue_country")
    op.drop_column("events", "venue_city")
    op.drop_column("events", "venue_name")
    op.drop_column("events", "competition_stage")
