from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Event, Market, OddsSnapshot, Outcome
from app.schemas import BacktestOut
from app.services.calculations import expected_value, normalize_probabilities
from app.services.storage import get_risk_control


def run_backtest(db: Session, event_id: str, market_key: str, stake: float) -> BacktestOut:
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if not event:
        return BacktestOut(
            event_id=event_id,
            market_key=market_key,
            bets_simulated=0,
            wins=0,
            losses=0,
            pnl=0.0,
            roi=0.0,
            notes=["Event not found."],
        )

    market = db.execute(
        select(Market)
        .where(Market.event_id == event_id)
        .where(Market.market_key == market_key)
    ).scalar_one_or_none()
    if not market:
        return BacktestOut(
            event_id=event_id,
            market_key=market_key,
            bets_simulated=0,
            wins=0,
            losses=0,
            pnl=0.0,
            roi=0.0,
            notes=["Market not found for event."],
        )

    rows = db.execute(
        select(
            OddsSnapshot.timestamp,
            Outcome.id,
            Outcome.name,
            OddsSnapshot.decimal_odds,
            OddsSnapshot.implied_prob,
            OddsSnapshot.raw_payload,
        )
        .join(Outcome, Outcome.id == OddsSnapshot.outcome_id)
        .where(OddsSnapshot.event_id == event_id)
        .where(OddsSnapshot.market_id == market.id)
        .order_by(OddsSnapshot.timestamp.asc())
    ).all()

    if not rows:
        return BacktestOut(
            event_id=event_id,
            market_key=market_key,
            bets_simulated=0,
            wins=0,
            losses=0,
            pnl=0.0,
            roi=0.0,
            notes=["No odds snapshots stored for backtest."],
        )

    by_ts: dict = defaultdict(list)
    final_by_outcome: dict[str, tuple[str, float, dict]] = {}

    for ts, outcome_id, outcome_name, odds, implied, raw in rows:
        by_ts[ts].append((outcome_id, outcome_name, odds, implied))
        final_by_outcome[outcome_id] = (outcome_name, odds, raw or {})

    winner_outcome_id = None
    notes: list[str] = []
    for oid, (_, _, raw) in final_by_outcome.items():
        if raw.get("winner") is True or str(raw.get("result", "")).lower() in {"win", "won"}:
            winner_outcome_id = oid
            break

    if winner_outcome_id is None:
        # Inference fallback for demos when no result labels are available.
        winner_outcome_id = min(final_by_outcome.items(), key=lambda item: item[1][1])[0]
        notes.append("Winner inferred from lowest final odds due to missing result labels.")

    control = get_risk_control(db)
    pnl = 0.0
    wins = 0
    losses = 0
    bets = 0

    for _, rec_rows in sorted(by_ts.items(), key=lambda item: item[0]):
        implieds = [row[3] for row in rec_rows]
        norm = normalize_probabilities(implieds)

        scored: list[tuple[float, str, float]] = []
        for idx, (outcome_id, _name, odds, implied) in enumerate(rec_rows):
            model_prob = norm[idx]
            ev = expected_value(model_prob, odds)
            edge = model_prob - implied
            if edge >= control.min_edge and ev >= control.min_ev:
                scored.append((ev, outcome_id, odds))

        if not scored:
            continue

        scored.sort(reverse=True, key=lambda x: x[0])
        _, selected_outcome_id, selected_odds = scored[0]
        bets += 1

        if selected_outcome_id == winner_outcome_id:
            single_pnl = stake * (selected_odds - 1.0)
            wins += 1
        else:
            single_pnl = -stake
            losses += 1
        pnl += single_pnl

    roi = pnl / (bets * stake) if bets else 0.0
    if bets == 0:
        notes.append("No qualifying bets met edge/EV thresholds in historical snapshots.")

    return BacktestOut(
        event_id=event_id,
        market_key=market_key,
        bets_simulated=bets,
        wins=wins,
        losses=losses,
        pnl=round(pnl, 2),
        roi=round(roi, 4),
        notes=notes,
    )
