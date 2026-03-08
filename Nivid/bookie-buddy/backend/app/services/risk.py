from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import BankrollLedger, Bet, RiskControl
from app.services.calculations import fractional_kelly_fraction


@dataclass
class RiskDecision:
    passed: bool
    reasons: list[str]
    proposed_stake: float


def current_balance(db: Session) -> float:
    stmt = select(BankrollLedger.balance_after).order_by(BankrollLedger.timestamp.desc()).limit(1)
    balance = db.execute(stmt).scalar_one_or_none()
    return float(balance or 0.0)


def open_exposure_for_event(db: Session, event_id: str) -> float:
    stmt = (
        select(func.coalesce(func.sum(Bet.stake), 0.0))
        .where(Bet.event_id == event_id)
        .where(Bet.status.in_(["PENDING", "PLACED"]))
    )
    return float(db.execute(stmt).scalar_one())


def daily_loss(db: Session) -> float:
    now = datetime.now(timezone.utc)
    day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    stmt = (
        select(func.coalesce(func.sum(BankrollLedger.amount), 0.0))
        .where(BankrollLedger.timestamp >= day_start)
    )
    net = float(db.execute(stmt).scalar_one())
    return min(0.0, net)


def calculate_stake(
    db: Session,
    control: RiskControl,
    model_prob: float,
    odds: float,
    bankroll: float,
) -> float:
    if control.fractional_kelly_enabled:
        fraction = fractional_kelly_fraction(
            model_prob=model_prob,
            decimal_odds=odds,
            factor=control.fractional_kelly_factor,
        )
        sized = bankroll * fraction
    else:
        sized = control.default_flat_stake
    return max(0.0, min(sized, control.max_stake))


def evaluate_risk(
    db: Session,
    event_id: str,
    control: RiskControl,
    model_prob: float,
    odds: float,
    requested_stake: float | None = None,
) -> RiskDecision:
    reasons: list[str] = []

    balance = current_balance(db)
    stake = requested_stake if requested_stake is not None else calculate_stake(db, control, model_prob, odds, balance)

    if control.kill_switch_enabled:
        reasons.append("Global kill switch is enabled.")

    if stake <= 0:
        reasons.append("Calculated stake is zero.")

    if stake > control.max_stake:
        reasons.append(
            f"Stake {stake:.2f} exceeds max stake {control.max_stake:.2f}."
        )

    if stake > balance:
        reasons.append("Insufficient bankroll balance for stake.")

    exposure = open_exposure_for_event(db, event_id)
    if exposure + stake > control.max_exposure_per_event:
        reasons.append(
            f"Event exposure would become {exposure + stake:.2f}, above limit {control.max_exposure_per_event:.2f}."
        )

    dloss = daily_loss(db)
    if abs(dloss) >= control.max_daily_loss:
        reasons.append(
            f"Daily loss limit reached ({abs(dloss):.2f}/{control.max_daily_loss:.2f})."
        )

    return RiskDecision(passed=not reasons, reasons=reasons, proposed_stake=stake)


def classify_risk_tier(odds: float, edge: float, label: str) -> str:
    if label == "NO_BET":
        return "PASS"
    if odds <= 2.0 and edge >= 0.02:
        return "LOW_RISK"
    if odds <= 3.5:
        return "MEDIUM_RISK"
    return "HIGH_RISK"
