from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    id: str
    provider_event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    competition_stage: str | None = None
    venue_name: str | None = None
    venue_city: str | None = None
    venue_country: str | None = None
    start_time: datetime
    is_live: bool
    status: str

    model_config = {"from_attributes": True}


class OutcomeOddsOut(BaseModel):
    outcome_id: str
    outcome_name: str
    decimal_odds: float
    implied_prob: float
    timestamp: datetime


class MarketOut(BaseModel):
    market_id: str
    market_key: str
    last_updated: datetime
    outcomes: list[OutcomeOddsOut]


class RecommendationOut(BaseModel):
    recommendation_id: str
    event_id: str
    market_id: str
    outcome_id: str
    outcome_name: str
    implied_prob: float
    normalized_implied_prob: float
    model_prob: float
    edge: float
    expected_value: float
    confidence: float
    recommendation_label: str
    risk_tier: str
    rationale: list[str]
    model_components: dict[str, Any] = {}
    created_at: datetime


class TopPickCard(BaseModel):
    event_id: str
    event_label: str
    market_key: str
    outcome_name: str
    recommendation_label: str
    risk_tier: str
    edge: float
    expected_value: float
    odds: float


class SimulateBetIn(BaseModel):
    recommendation_id: str | None = None
    event_id: str
    outcome_id: str
    stake: float
    odds_requested: float
    idempotency_key: str = Field(min_length=8, max_length=128)


class LiveBetIn(SimulateBetIn):
    confirm_live: bool = False
    confirm_phrase: str = ""
    exchange: str = "betfair"


class SettleBetIn(BaseModel):
    bet_id: str
    won: bool


class BetOut(BaseModel):
    id: str
    recommendation_id: str | None
    event_id: str
    outcome_id: str
    mode: str
    status: str
    stake: float
    odds_requested: float
    odds_executed: float | None
    pnl: float | None
    idempotency_key: str
    placed_at: datetime
    settled_at: datetime | None

    model_config = {"from_attributes": True}


class BankrollSummary(BaseModel):
    balance: float
    daily_pnl: float
    open_exposure: float


class LedgerEntryOut(BaseModel):
    id: str
    timestamp: datetime
    entry_type: str
    amount: float
    balance_after: float
    note: str
    bet_id: str | None

    model_config = {"from_attributes": True}


class AuditOut(BaseModel):
    id: str
    timestamp: datetime
    actor: str
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any]

    model_config = {"from_attributes": True}


class RiskControlIn(BaseModel):
    max_stake: float
    max_exposure_per_event: float
    max_daily_loss: float
    min_edge: float
    min_ev: float
    top_pick_edge: float
    top_pick_ev: float
    data_freshness_seconds: int
    max_odds_drift_pct: float
    default_flat_stake: float
    fractional_kelly_enabled: bool
    fractional_kelly_factor: float
    execution_mode: str
    live_enabled: bool
    kill_switch_enabled: bool


class RiskControlOut(RiskControlIn):
    id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class BacktestIn(BaseModel):
    event_id: str
    market_key: str = "moneyline_3way"
    stake: float = 25.0


class BacktestOut(BaseModel):
    event_id: str
    market_key: str
    bets_simulated: int
    wins: int
    losses: int
    pnl: float
    roi: float
    notes: list[str]


class EventAnalysisOut(BaseModel):
    event_id: str
    weather: dict[str, Any]
    ground: dict[str, Any]
    team_standings: dict[str, Any]
    player_availability: list[dict[str, Any]]
    news_digest: list[dict[str, Any]]
    risk_flags: list[str]
    recommended_bet: dict[str, Any] | None
