from sqlalchemy import func, select

from app.db.models import Bet, Event, Outcome
from app.schemas import SimulateBetIn
from app.services.broker import submit_sim_bet
from app.services.risk import evaluate_risk
from app.services.storage import get_risk_control


def test_risk_blocks_when_stake_exceeds_max(db_session):
    control = get_risk_control(db_session)
    event = db_session.execute(select(Event)).scalar_one()

    result = evaluate_risk(
        db=db_session,
        event_id=event.id,
        control=control,
        model_prob=0.6,
        odds=2.1,
        requested_stake=control.max_stake + 1,
    )

    assert result.passed is False
    assert any("exceeds max stake" in reason.lower() for reason in result.reasons)


def test_risk_passes_for_safe_stake(db_session):
    control = get_risk_control(db_session)
    event = db_session.execute(select(Event)).scalar_one()

    result = evaluate_risk(
        db=db_session,
        event_id=event.id,
        control=control,
        model_prob=0.57,
        odds=1.95,
        requested_stake=10.0,
    )

    assert result.passed is True


def test_idempotent_sim_submission(db_session):
    event = db_session.execute(select(Event)).scalar_one()
    outcome = db_session.execute(select(Outcome)).scalars().first()

    payload = SimulateBetIn(
        event_id=event.id,
        outcome_id=outcome.id,
        stake=25.0,
        odds_requested=2.0,
        idempotency_key="unique-order-key-123",
    )

    first = submit_sim_bet(db_session, payload)
    second = submit_sim_bet(db_session, payload)
    db_session.commit()

    assert first.id == second.id
    bet_count = db_session.execute(select(func.count(Bet.id))).scalar_one()
    assert bet_count == 1
