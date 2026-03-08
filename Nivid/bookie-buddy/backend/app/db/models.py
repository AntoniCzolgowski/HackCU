from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider_event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sport: Mapped[str] = mapped_column(String(64), index=True)
    league: Mapped[str] = mapped_column(String(128), index=True)
    home_team: Mapped[str] = mapped_column(String(128), index=True)
    away_team: Mapped[str] = mapped_column(String(128), index=True)
    competition_stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    venue_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    venue_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    venue_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    venue_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    markets: Mapped[list[Market]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Market(Base):
    __tablename__ = "markets"
    __table_args__ = (UniqueConstraint("event_id", "market_key", name="uq_event_market"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    market_key: Mapped[str] = mapped_column(String(64), index=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    event: Mapped[Event] = relationship(back_populates="markets")
    outcomes: Mapped[list[Outcome]] = relationship(back_populates="market", cascade="all, delete-orphan")


class Outcome(Base):
    __tablename__ = "outcomes"
    __table_args__ = (UniqueConstraint("market_id", "name", name="uq_market_outcome"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)

    market: Mapped[Market] = relationship(back_populates="outcomes")
    snapshots: Mapped[list[OddsSnapshot]] = relationship(back_populates="outcome", cascade="all, delete-orphan")


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"), index=True)
    outcome_id: Mapped[str] = mapped_column(ForeignKey("outcomes.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    decimal_odds: Mapped[float] = mapped_column(Float)
    implied_prob: Mapped[float] = mapped_column(Float)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    outcome: Mapped[Outcome] = relationship(back_populates="snapshots")


class TeamRating(Base):
    __tablename__ = "team_ratings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    team_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    elo_rating: Mapped[float] = mapped_column(Float, default=1500.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"), index=True)
    outcome_id: Mapped[str] = mapped_column(ForeignKey("outcomes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    implied_prob: Mapped[float] = mapped_column(Float)
    normalized_implied_prob: Mapped[float] = mapped_column(Float)
    model_prob: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    recommendation_label: Mapped[str] = mapped_column(String(32), index=True)
    risk_tier: Mapped[str] = mapped_column(String(32), index=True)
    rationale: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_components: Mapped[dict] = mapped_column(JSON, default=dict)


class Bet(Base):
    __tablename__ = "bets"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_bet_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    outcome_id: Mapped[str] = mapped_column(ForeignKey("outcomes.id", ondelete="CASCADE"), index=True)

    mode: Mapped[str] = mapped_column(String(16), index=True)  # SIM | LIVE
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)

    stake: Mapped[float] = mapped_column(Float)
    odds_requested: Mapped[float] = mapped_column(Float)
    odds_executed: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BankrollLedger(Base):
    __tablename__ = "bankroll_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    entry_type: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(String(256), default="")
    bet_id: Mapped[str | None] = mapped_column(ForeignKey("bets.id", ondelete="SET NULL"), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ProviderStatus(Base):
    __tablename__ = "provider_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limit_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RiskControl(Base):
    __tablename__ = "risk_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    max_stake: Mapped[float] = mapped_column(Float)
    max_exposure_per_event: Mapped[float] = mapped_column(Float)
    max_daily_loss: Mapped[float] = mapped_column(Float)
    min_edge: Mapped[float] = mapped_column(Float)
    min_ev: Mapped[float] = mapped_column(Float)
    top_pick_edge: Mapped[float] = mapped_column(Float)
    top_pick_ev: Mapped[float] = mapped_column(Float)
    data_freshness_seconds: Mapped[int] = mapped_column(Integer)
    max_odds_drift_pct: Mapped[float] = mapped_column(Float)
    default_flat_stake: Mapped[float] = mapped_column(Float)
    fractional_kelly_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    fractional_kelly_factor: Mapped[float] = mapped_column(Float, default=0.25)
    execution_mode: Mapped[str] = mapped_column(String(16), default="SIM")
    live_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    kill_switch_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


Index("ix_snapshot_event_market_time", OddsSnapshot.event_id, OddsSnapshot.market_id, OddsSnapshot.timestamp)
Index("ix_reco_event_created", Recommendation.event_id, Recommendation.created_at)
Index("ix_bet_event_placed", Bet.event_id, Bet.placed_at)
