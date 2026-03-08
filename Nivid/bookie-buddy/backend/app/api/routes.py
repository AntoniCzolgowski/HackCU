from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditLog, BankrollLedger, Bet, Event, Market, OddsSnapshot, Outcome, Recommendation
from app.db.session import get_db
from app.schemas import (
    AuditOut,
    BacktestIn,
    BacktestOut,
    BankrollSummary,
    BetOut,
    EventAnalysisOut,
    EventOut,
    LedgerEntryOut,
    LiveBetIn,
    MarketOut,
    OutcomeOddsOut,
    RecommendationOut,
    RiskControlIn,
    RiskControlOut,
    SettleBetIn,
    SimulateBetIn,
    TopPickCard,
)
from app.services.backtest import run_backtest
from app.services.broker import BrokerError, outcome_name, settle_bet, submit_live_bet, submit_sim_bet
from app.services.recommendations import (
    event_analysis_snapshot,
    generate_recommendations_for_event,
    latest_recommendations_for_event,
    latest_recommendations_all_events,
    odds_history_for_event,
    probability_p_chart,
)
from app.services.storage import add_audit_log, current_balance, get_risk_control

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/events", response_model=list[EventOut])
def list_events(
    is_live: bool | None = Query(default=None),
    sport: str | None = None,
    league: str | None = None,
    limit: int = Query(default=250, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[Event]:
    settings = get_settings()
    stmt = select(Event).order_by(Event.start_time.asc())
    if is_live is not None:
        stmt = stmt.where(Event.is_live == is_live)
    if sport:
        stmt = stmt.where(Event.sport == sport)
    if league:
        stmt = stmt.where(Event.league == league)
    elif settings.world_cup_only:
        stmt = stmt.where(Event.league.ilike(f"%{settings.world_cup_league_name}%"))
    stmt = stmt.limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)) -> Event:
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/events/{event_id}/markets", response_model=list[MarketOut])
def event_markets(event_id: str, db: Session = Depends(get_db)) -> list[MarketOut]:
    markets = db.execute(select(Market).where(Market.event_id == event_id)).scalars().all()
    result: list[MarketOut] = []
    for market in markets:
        outcomes = db.execute(select(Outcome).where(Outcome.market_id == market.id)).scalars().all()
        formatted_outcomes: list[OutcomeOddsOut] = []
        for outcome in outcomes:
            snap = db.execute(
                select(OddsSnapshot)
                .where(OddsSnapshot.outcome_id == outcome.id)
                .order_by(OddsSnapshot.timestamp.desc())
                .limit(1)
            ).scalar_one_or_none()
            if snap:
                formatted_outcomes.append(
                    OutcomeOddsOut(
                        outcome_id=outcome.id,
                        outcome_name=outcome.name,
                        decimal_odds=snap.decimal_odds,
                        implied_prob=snap.implied_prob,
                        timestamp=snap.timestamp,
                    )
                )
        result.append(
            MarketOut(
                market_id=market.id,
                market_key=market.market_key,
                last_updated=market.last_updated,
                outcomes=formatted_outcomes,
            )
        )
    return result


@router.get("/events/{event_id}/odds-history")
def event_odds_history(event_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return odds_history_for_event(db, event_id)


@router.get("/events/{event_id}/p-chart")
def event_p_chart(event_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return probability_p_chart(db, event_id)


@router.get("/events/{event_id}/analysis", response_model=EventAnalysisOut)
def event_analysis(event_id: str, db: Session = Depends(get_db)) -> EventAnalysisOut:
    snapshot = event_analysis_snapshot(db, event_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventAnalysisOut(**snapshot)


@router.post("/events/{event_id}/recommendations/refresh", response_model=list[RecommendationOut])
def refresh_recommendations(event_id: str, db: Session = Depends(get_db)) -> list[RecommendationOut]:
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    recs = generate_recommendations_for_event(db, event_id)
    db.commit()
    return _format_recommendations(db, recs)


@router.get("/events/{event_id}/recommendations", response_model=list[RecommendationOut])
def get_recommendations(event_id: str, db: Session = Depends(get_db)) -> list[RecommendationOut]:
    recs = latest_recommendations_for_event(db, event_id)
    if not recs:
        recs = generate_recommendations_for_event(db, event_id)
        db.commit()
    return _format_recommendations(db, recs)


@router.get("/top-picks", response_model=list[TopPickCard])
def top_picks(limit: int = 20, db: Session = Depends(get_db)) -> list[TopPickCard]:
    preferred_markets = {"moneyline_3way", "h2h", "totals_2_5", "totals", "btts"}
    latest = latest_recommendations_all_events(db)
    latest = [
        row
        for row in latest
        if row.recommendation_label in {"TOP_PICK", "LEAN"}
    ]
    filtered_latest: list[Recommendation] = []
    for row in latest:
        market = db.execute(select(Market).where(Market.id == row.market_id)).scalar_one_or_none()
        if market and market.market_key in preferred_markets:
            filtered_latest.append(row)

    filtered_latest.sort(key=lambda r: (r.expected_value, r.edge, r.confidence), reverse=True)

    cards: list[TopPickCard] = []
    for rec in filtered_latest[:limit]:
        event = db.execute(select(Event).where(Event.id == rec.event_id)).scalar_one_or_none()
        outcome = db.execute(select(Outcome).where(Outcome.id == rec.outcome_id)).scalar_one_or_none()
        market = db.execute(select(Market).where(Market.id == rec.market_id)).scalar_one_or_none()
        if not event or not outcome:
            continue
        snap = db.execute(
            select(OddsSnapshot)
            .where(OddsSnapshot.outcome_id == outcome.id)
            .order_by(OddsSnapshot.timestamp.desc())
            .limit(1)
        ).scalar_one_or_none()
        cards.append(
            TopPickCard(
                event_id=event.id,
                event_label=f"{event.away_team} @ {event.home_team}",
                market_key=market.market_key if market else "unknown",
                outcome_name=outcome.name,
                recommendation_label=rec.recommendation_label,
                risk_tier=rec.risk_tier,
                edge=rec.edge,
                expected_value=rec.expected_value,
                odds=snap.decimal_odds if snap else 0.0,
            )
        )
    return cards


@router.post("/bets/simulate", response_model=BetOut)
def simulate_bet(payload: SimulateBetIn, db: Session = Depends(get_db)) -> Bet:
    try:
        bet = submit_sim_bet(db, payload)
        db.commit()
        db.refresh(bet)
        return bet
    except BrokerError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bets/live", response_model=BetOut)
def live_bet(payload: LiveBetIn, db: Session = Depends(get_db)) -> Bet:
    try:
        bet = submit_live_bet(db, payload)
        db.commit()
        db.refresh(bet)
        return bet
    except BrokerError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bets/settle", response_model=BetOut)
def settle(payload: SettleBetIn, db: Session = Depends(get_db)) -> Bet:
    try:
        bet = settle_bet(db, payload.bet_id, payload.won)
        db.commit()
        db.refresh(bet)
        return bet
    except BrokerError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bets", response_model=list[BetOut])
def list_bets(db: Session = Depends(get_db)) -> list[Bet]:
    return db.execute(select(Bet).order_by(Bet.placed_at.desc())).scalars().all()


@router.get("/bankroll", response_model=BankrollSummary)
def bankroll_summary(db: Session = Depends(get_db)) -> BankrollSummary:
    balance = current_balance(db)

    now = datetime.now(timezone.utc)
    day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    daily_net = db.execute(
        select(func.coalesce(func.sum(BankrollLedger.amount), 0.0)).where(BankrollLedger.timestamp >= day_start)
    ).scalar_one()
    open_exposure = db.execute(
        select(func.coalesce(func.sum(Bet.stake), 0.0)).where(Bet.status.in_(["PENDING", "PLACED"]))
    ).scalar_one()

    return BankrollSummary(balance=round(balance, 2), daily_pnl=round(float(daily_net), 2), open_exposure=round(float(open_exposure), 2))


@router.get("/bankroll/curve", response_model=list[LedgerEntryOut])
def bankroll_curve(db: Session = Depends(get_db)) -> list[BankrollLedger]:
    return db.execute(select(BankrollLedger).order_by(BankrollLedger.timestamp.asc())).scalars().all()


@router.get("/exposure")
def exposure_by_event(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Event.id, Event.home_team, Event.away_team, func.coalesce(func.sum(Bet.stake), 0.0))
        .outerjoin(Bet, (Bet.event_id == Event.id) & Bet.status.in_(["PENDING", "PLACED"]))
        .group_by(Event.id)
        .order_by(func.coalesce(func.sum(Bet.stake), 0.0).desc())
    ).all()

    result = []
    for event_id, home, away, exposure in rows:
        result.append(
            {
                "event_id": event_id,
                "event": f"{away} @ {home}",
                "exposure": float(exposure),
            }
        )
    return result


@router.get("/audit", response_model=list[AuditOut])
def audit_logs(limit: int = 250, db: Session = Depends(get_db)) -> list[AuditLog]:
    return db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)).scalars().all()


@router.get("/settings/risk", response_model=RiskControlOut)
def get_risk_settings(db: Session = Depends(get_db)):
    return get_risk_control(db)


@router.put("/settings/risk", response_model=RiskControlOut)
def update_risk_settings(payload: RiskControlIn, db: Session = Depends(get_db)):
    control = get_risk_control(db)
    for field, value in payload.model_dump().items():
        setattr(control, field, value)
    add_audit_log(
        db,
        action="RISK_SETTINGS_UPDATED",
        entity_type="risk_controls",
        entity_id=str(control.id),
        details=payload.model_dump(),
        actor="user",
    )
    db.commit()
    db.refresh(control)
    return control


@router.post("/settings/kill-switch")
def set_kill_switch(enabled: bool, db: Session = Depends(get_db)) -> dict[str, Any]:
    control = get_risk_control(db)
    control.kill_switch_enabled = enabled
    add_audit_log(
        db,
        action="KILL_SWITCH_TOGGLED",
        entity_type="risk_controls",
        entity_id=str(control.id),
        details={"enabled": enabled},
        actor="user",
    )
    db.commit()
    return {"kill_switch_enabled": enabled}


@router.post("/backtest/run", response_model=BacktestOut)
def backtest(payload: BacktestIn, db: Session = Depends(get_db)) -> BacktestOut:
    return run_backtest(db, payload.event_id, payload.market_key, payload.stake)


@router.post("/seed/deposit")
def seed_deposit(amount: float = 1000.0, db: Session = Depends(get_db)) -> dict[str, float]:
    from app.services.storage import add_ledger_entry

    add_ledger_entry(db, amount=amount, entry_type="DEPOSIT", note="Manual deposit seed")
    add_audit_log(
        db,
        action="BANKROLL_SEEDED",
        entity_type="bankroll",
        entity_id="main",
        details={"amount": amount},
        actor="user",
    )
    db.commit()
    return {"balance": current_balance(db)}


def _format_recommendations(db: Session, recs: list[Recommendation]) -> list[RecommendationOut]:
    result: list[RecommendationOut] = []
    for rec in recs:
        result.append(
            RecommendationOut(
                recommendation_id=rec.id,
                event_id=rec.event_id,
                market_id=rec.market_id,
                outcome_id=rec.outcome_id,
                outcome_name=outcome_name(db, rec.outcome_id),
                implied_prob=rec.implied_prob,
                normalized_implied_prob=rec.normalized_implied_prob,
                model_prob=rec.model_prob,
                edge=rec.edge,
                expected_value=rec.expected_value,
                confidence=rec.confidence,
                recommendation_label=rec.recommendation_label,
                risk_tier=rec.risk_tier,
                rationale=rec.rationale,
                created_at=rec.created_at,
                model_components=rec.model_components or {},
            )
        )
    return result
