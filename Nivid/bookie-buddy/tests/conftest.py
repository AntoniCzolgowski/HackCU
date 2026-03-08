from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, Event, Market, Outcome
from app.services.storage import add_ledger_entry, get_risk_control


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # baseline controls + bankroll
    get_risk_control(db)
    add_ledger_entry(db, amount=1000.0, entry_type="DEPOSIT", note="test seed")

    event = Event(
        provider_event_id="test-event-1",
        sport="soccer_fifa_world_cup",
        league="FIFA World Cup 2026",
        home_team="Mexico",
        away_team="South Africa",
        start_time=datetime.now(timezone.utc),
        is_live=False,
        status="scheduled",
    )
    db.add(event)
    db.flush()

    market = Market(event_id=event.id, market_key="h2h", last_updated=datetime.now(timezone.utc))
    db.add(market)
    db.flush()

    db.add(Outcome(market_id=market.id, name="Mexico"))
    db.add(Outcome(market_id=market.id, name="South Africa"))
    db.commit()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
