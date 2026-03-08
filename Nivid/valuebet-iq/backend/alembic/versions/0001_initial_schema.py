"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-03-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider_event_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("sport", sa.String(length=64), nullable=False),
        sa.Column("league", sa.String(length=128), nullable=False),
        sa.Column("home_team", sa.String(length=128), nullable=False),
        sa.Column("away_team", sa.String(length=128), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "markets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_key", sa.String(length=64), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "market_key", name="uq_event_market"),
    )

    op.create_table(
        "outcomes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("market_id", sa.String(length=36), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("market_id", "name", name="uq_market_outcome"),
    )

    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.String(length=36), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome_id", sa.String(length=36), sa.ForeignKey("outcomes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decimal_odds", sa.Float(), nullable=False),
        sa.Column("implied_prob", sa.Float(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
    )

    op.create_table(
        "team_ratings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("team_name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("elo_rating", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.String(length=36), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome_id", sa.String(length=36), sa.ForeignKey("outcomes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("implied_prob", sa.Float(), nullable=False),
        sa.Column("normalized_implied_prob", sa.Float(), nullable=False),
        sa.Column("model_prob", sa.Float(), nullable=False),
        sa.Column("edge", sa.Float(), nullable=False),
        sa.Column("expected_value", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("recommendation_label", sa.String(length=32), nullable=False),
        sa.Column("risk_tier", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.JSON(), nullable=False),
    )

    op.create_table(
        "bets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("recommendation_id", sa.String(length=36), sa.ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome_id", sa.String(length=36), sa.ForeignKey("outcomes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stake", sa.Float(), nullable=False),
        sa.Column("odds_requested", sa.Float(), nullable=False),
        sa.Column("odds_executed", sa.Float(), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_bet_idempotency"),
    )

    op.create_table(
        "bankroll_ledger",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("balance_after", sa.Float(), nullable=False),
        sa.Column("note", sa.String(length=256), nullable=False),
        sa.Column("bet_id", sa.String(length=36), sa.ForeignKey("bets.id", ondelete="SET NULL"), nullable=True),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )

    op.create_table(
        "provider_status",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("rate_limit_remaining", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "risk_controls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("max_stake", sa.Float(), nullable=False),
        sa.Column("max_exposure_per_event", sa.Float(), nullable=False),
        sa.Column("max_daily_loss", sa.Float(), nullable=False),
        sa.Column("min_edge", sa.Float(), nullable=False),
        sa.Column("min_ev", sa.Float(), nullable=False),
        sa.Column("top_pick_edge", sa.Float(), nullable=False),
        sa.Column("top_pick_ev", sa.Float(), nullable=False),
        sa.Column("data_freshness_seconds", sa.Integer(), nullable=False),
        sa.Column("max_odds_drift_pct", sa.Float(), nullable=False),
        sa.Column("default_flat_stake", sa.Float(), nullable=False),
        sa.Column("fractional_kelly_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fractional_kelly_factor", sa.Float(), nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("live_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("kill_switch_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_events_start_time", "events", ["start_time"])
    op.create_index("ix_events_is_live", "events", ["is_live"])
    op.create_index("ix_events_sport", "events", ["sport"])
    op.create_index("ix_events_league", "events", ["league"])
    op.create_index("ix_markets_event_id", "markets", ["event_id"])
    op.create_index("ix_outcomes_market_id", "outcomes", ["market_id"])
    op.create_index("ix_odds_snapshots_event_id", "odds_snapshots", ["event_id"])
    op.create_index("ix_odds_snapshots_market_id", "odds_snapshots", ["market_id"])
    op.create_index("ix_odds_snapshots_outcome_id", "odds_snapshots", ["outcome_id"])
    op.create_index("ix_odds_snapshots_timestamp", "odds_snapshots", ["timestamp"])
    op.create_index("ix_snapshot_event_market_time", "odds_snapshots", ["event_id", "market_id", "timestamp"])
    op.create_index("ix_reco_event_created", "recommendations", ["event_id", "created_at"])
    op.create_index("ix_bet_event_placed", "bets", ["event_id", "placed_at"])


def downgrade() -> None:
    op.drop_index("ix_bet_event_placed", table_name="bets")
    op.drop_index("ix_reco_event_created", table_name="recommendations")
    op.drop_index("ix_snapshot_event_market_time", table_name="odds_snapshots")
    op.drop_index("ix_odds_snapshots_timestamp", table_name="odds_snapshots")
    op.drop_index("ix_odds_snapshots_outcome_id", table_name="odds_snapshots")
    op.drop_index("ix_odds_snapshots_market_id", table_name="odds_snapshots")
    op.drop_index("ix_odds_snapshots_event_id", table_name="odds_snapshots")
    op.drop_index("ix_outcomes_market_id", table_name="outcomes")
    op.drop_index("ix_markets_event_id", table_name="markets")
    op.drop_index("ix_events_league", table_name="events")
    op.drop_index("ix_events_sport", table_name="events")
    op.drop_index("ix_events_is_live", table_name="events")
    op.drop_index("ix_events_start_time", table_name="events")

    op.drop_table("risk_controls")
    op.drop_table("provider_status")
    op.drop_table("audit_log")
    op.drop_table("bankroll_ledger")
    op.drop_table("bets")
    op.drop_table("recommendations")
    op.drop_table("team_ratings")
    op.drop_table("odds_snapshots")
    op.drop_table("outcomes")
    op.drop_table("markets")
    op.drop_table("events")
