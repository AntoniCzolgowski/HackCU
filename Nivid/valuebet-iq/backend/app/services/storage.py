from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditLog, BankrollLedger, RiskControl


def get_risk_control(db: Session) -> RiskControl:
    control = db.execute(select(RiskControl).order_by(RiskControl.id.asc()).limit(1)).scalar_one_or_none()
    if control:
        return control

    settings = get_settings()
    control = RiskControl(
        max_stake=settings.max_stake,
        max_exposure_per_event=settings.max_exposure_per_event,
        max_daily_loss=settings.max_daily_loss,
        min_edge=settings.min_edge,
        min_ev=settings.min_ev,
        top_pick_edge=settings.top_pick_edge,
        top_pick_ev=settings.top_pick_ev,
        data_freshness_seconds=settings.data_freshness_seconds,
        max_odds_drift_pct=settings.max_odds_drift_pct,
        default_flat_stake=settings.default_flat_stake,
        fractional_kelly_enabled=False,
        fractional_kelly_factor=0.25,
        execution_mode="SIM",
        live_enabled=False,
        kill_switch_enabled=False,
    )
    db.add(control)
    db.commit()
    db.refresh(control)
    return control


def current_balance(db: Session) -> float:
    stmt = select(BankrollLedger).order_by(BankrollLedger.timestamp.desc()).limit(1)
    entry = db.execute(stmt).scalar_one_or_none()
    return float(entry.balance_after if entry else 0.0)


def add_ledger_entry(
    db: Session,
    amount: float,
    entry_type: str,
    note: str,
    bet_id: str | None = None,
) -> BankrollLedger:
    balance_before = current_balance(db)
    entry = BankrollLedger(
        timestamp=datetime.now(timezone.utc),
        entry_type=entry_type,
        amount=amount,
        balance_after=balance_before + amount,
        note=note,
        bet_id=bet_id,
    )
    db.add(entry)
    db.flush()
    return entry


def add_audit_log(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any],
    actor: str = "system",
) -> AuditLog:
    entry = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(entry)
    db.flush()
    return entry
