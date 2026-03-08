from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import poll_latency
from app.db.models import Event, ProviderStatus
from app.db.session import SessionLocal
from app.services.providers import MockOddsProvider, TheOddsApiProvider
from app.services.recommendations import generate_recommendations_for_event, upsert_provider_events

logger = logging.getLogger(__name__)


@contextmanager
def timed_poll():
    with poll_latency.time():
        yield


def _provider_status(db, provider_name: str) -> ProviderStatus:
    row = db.execute(select(ProviderStatus).where(ProviderStatus.provider == provider_name)).scalar_one_or_none()
    if row:
        return row
    row = ProviderStatus(provider=provider_name, status="init")
    db.add(row)
    db.flush()
    return row


def run_poll_cycle() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        if settings.odds_provider_mode == "odds_api":
            provider = TheOddsApiProvider(settings)
            events, rate_remaining = provider.fetch_events()
        else:
            provider = MockOddsProvider(settings)
            events = provider.fetch_events()
            rate_remaining = None

        with timed_poll():
            persisted_events = []
            active_ids: list[str] = []
            for provider_event in events:
                persisted = upsert_provider_events(db, provider.provider_name, [provider_event])
                if not persisted:
                    continue
                event_obj = persisted[0]
                generate_recommendations_for_event(db, event_obj.id)
                db.commit()
                persisted_events.append(event_obj)
                active_ids.append(event_obj.provider_event_id)

            if active_ids:
                # Keep DB aligned with current provider board for World Cup events.
                db.execute(
                    delete(Event)
                    .where(Event.league.ilike("%FIFA World Cup%"))
                    .where(Event.provider_event_id.not_in(active_ids))
                )
                db.commit()

        status = _provider_status(db, provider.provider_name)
        status.status = "ok"
        status.last_success_at = datetime.now(timezone.utc)
        status.error_message = None
        status.rate_limit_remaining = rate_remaining
        db.commit()
        logger.info("Polling cycle completed", extra={"events": len(persisted_events), "provider": provider.provider_name})
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        provider_name = "the_odds_api" if settings.odds_provider_mode == "odds_api" else "mock"
        status = _provider_status(db, provider_name)
        status.status = "error"
        status.last_error_at = datetime.now(timezone.utc)
        status.error_message = str(exc)
        db.commit()
        logger.exception("Polling cycle failed")
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Worker started", extra={"provider_mode": settings.odds_provider_mode})
    while True:
        run_poll_cycle()
        time.sleep(settings.odds_poll_interval_seconds)


if __name__ == "__main__":
    main()
