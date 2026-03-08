from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import order_counter
from app.db.models import Bet, Outcome
from app.schemas import LiveBetIn, SimulateBetIn
from app.services.storage import add_audit_log, add_ledger_entry, get_risk_control


class BrokerError(Exception):
    pass


def _find_existing_by_idempotency(db: Session, key: str) -> Bet | None:
    return db.execute(select(Bet).where(Bet.idempotency_key == key)).scalar_one_or_none()


def submit_sim_bet(db: Session, payload: SimulateBetIn) -> Bet:
    existing = _find_existing_by_idempotency(db, payload.idempotency_key)
    if existing:
        return existing

    control = get_risk_control(db)
    if control.kill_switch_enabled:
        raise BrokerError("Kill switch is enabled. No orders can be submitted.")

    if payload.stake > control.max_stake:
        raise BrokerError("Stake exceeds max stake control.")

    settings = get_settings()
    if settings.sim_delay_ms > 0:
        time.sleep(settings.sim_delay_ms / 1000.0)
    slippage_factor = settings.sim_slippage_bps / 10000.0
    executed_odds = max(1.01, payload.odds_requested * (1.0 - slippage_factor))

    bet = Bet(
        recommendation_id=payload.recommendation_id,
        event_id=payload.event_id,
        outcome_id=payload.outcome_id,
        mode="SIM",
        status="PLACED",
        stake=payload.stake,
        odds_requested=payload.odds_requested,
        odds_executed=executed_odds,
        idempotency_key=payload.idempotency_key,
        placed_at=datetime.now(timezone.utc),
    )
    db.add(bet)
    db.flush()

    add_ledger_entry(
        db,
        amount=-payload.stake,
        entry_type="BET",
        note=f"SIM bet placed on outcome {payload.outcome_id}",
        bet_id=bet.id,
    )

    add_audit_log(
        db,
        action="BET_SIMULATED",
        entity_type="bet",
        entity_id=bet.id,
        details={
            "stake": payload.stake,
            "odds_requested": payload.odds_requested,
            "odds_executed": executed_odds,
            "idempotency_key": payload.idempotency_key,
        },
        actor="user",
    )
    order_counter.labels(mode="SIM", status="PLACED").inc()
    return bet


def submit_live_bet(db: Session, payload: LiveBetIn) -> Bet:
    existing = _find_existing_by_idempotency(db, payload.idempotency_key)
    if existing:
        return existing

    settings = get_settings()
    control = get_risk_control(db)

    if control.kill_switch_enabled:
        raise BrokerError("Kill switch is enabled. No orders can be submitted.")

    if not settings.enable_live_execution or not control.live_enabled:
        raise BrokerError("LIVE execution is disabled by feature flags and controls.")

    if not payload.confirm_live or payload.confirm_phrase.strip() != "ENABLE LIVE EXECUTION":
        raise BrokerError("LIVE confirmation gate failed.")

    if payload.exchange.lower() == "betfair" and not settings.live_betfair_enabled:
        raise BrokerError("Betfair live adapter is not enabled.")
    if payload.exchange.lower() == "matchbook" and not settings.live_matchbook_enabled:
        raise BrokerError("Matchbook live adapter is not enabled.")

    # Placeholder for official exchange API integration.
    # By default this blocks unless specific live adapters are enabled.
    raise BrokerError("Live adapter integration not configured in this demo build.")


def settle_bet(db: Session, bet_id: str, won: bool) -> Bet:
    bet = db.execute(select(Bet).where(Bet.id == bet_id)).scalar_one_or_none()
    if not bet:
        raise BrokerError("Bet not found")
    if bet.status not in {"PLACED", "PENDING"}:
        return bet

    payout = 0.0
    if won:
        odds = bet.odds_executed or bet.odds_requested
        payout = bet.stake * odds
        pnl = payout - bet.stake
    else:
        pnl = -bet.stake

    bet.pnl = pnl
    bet.status = "SETTLED"
    bet.settled_at = datetime.now(timezone.utc)

    if won:
        add_ledger_entry(
            db,
            amount=payout,
            entry_type="SETTLEMENT",
            note=f"Bet {bet.id} won",
            bet_id=bet.id,
        )
    else:
        add_ledger_entry(
            db,
            amount=0.0,
            entry_type="SETTLEMENT",
            note=f"Bet {bet.id} lost",
            bet_id=bet.id,
        )

    add_audit_log(
        db,
        action="BET_SETTLED",
        entity_type="bet",
        entity_id=bet.id,
        details={"won": won, "pnl": pnl},
        actor="user",
    )
    order_counter.labels(mode=bet.mode, status="SETTLED").inc()
    return bet


def outcome_name(db: Session, outcome_id: str) -> str:
    outcome = db.execute(select(Outcome).where(Outcome.id == outcome_id)).scalar_one_or_none()
    return outcome.name if outcome else outcome_id
