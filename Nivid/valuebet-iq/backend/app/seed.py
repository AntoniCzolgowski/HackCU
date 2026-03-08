from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.storage import add_audit_log, add_ledger_entry, current_balance, get_risk_control
from app.worker import run_poll_cycle


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ValueBet IQ with bankroll and optional mock odds snapshots.")
    parser.add_argument("--with-odds", action="store_true", help="Run one polling cycle to ingest odds and generate recs.")
    parser.add_argument("--deposit", type=float, default=None, help="Deposit amount if bankroll is empty.")
    args = parser.parse_args()

    settings = get_settings()
    db = SessionLocal()
    try:
        get_risk_control(db)
        bal = current_balance(db)
        if bal <= 0:
            amount = args.deposit if args.deposit is not None else settings.bankroll_start
            add_ledger_entry(db, amount=amount, entry_type="DEPOSIT", note="Initial bankroll seed")
            add_audit_log(
                db,
                action="BANKROLL_SEEDED",
                entity_type="bankroll",
                entity_id="main",
                details={"amount": amount},
            )
        db.commit()
    finally:
        db.close()

    if args.with_odds:
        run_poll_cycle()


if __name__ == "__main__":
    main()
