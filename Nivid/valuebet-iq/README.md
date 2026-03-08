# ValueBet IQ

ValueBet IQ is a production-style web app for FIFA World Cup betting decision support.

It helps a user:
1. Select a game.
2. Load odds and market data.
3. Compare implied vs model probabilities.
4. Compute edge + EV.
5. Rank picks with risk-aware labels.
6. Simulate execution (paper trading by default).
7. Incorporate player availability, team standing/form, venue/weather, and fresh team news signals.

## Safety and Compliance

- No scraping or browser automation of consumer bookmakers.
- No Selenium/Playwright bookmaker interaction.
- Default mode is `SIM` paper trading.
- `LIVE` mode is optional, disabled by default, behind explicit feature flags.
- `LIVE` mode requires confirmation gates and kill switch.
- Decision support only, no guaranteed profit predictions.

## Tech Stack

- Python 3.12
- FastAPI backend
- Polling worker with `httpx` + retry/backoff
- SQLAlchemy + Alembic
- Postgres
- Streamlit dashboard 
- Docker Compose

## Project Structure

```text
valuebet-iq/
  backend/
    app/
      api/routes.py
      core/{config.py,logging.py,metrics.py}
      db/{models.py,session.py}
      services/{backtest.py,broker.py,calculations.py,external_context.py,model_prob.py,providers.py,recommendations.py,risk.py,soccer_model.py,storage.py}
      main.py
      seed.py
      worker.py
    alembic/
      versions/0001_initial_schema.py
    Dockerfile
    requirements.txt
    alembic.ini
    data/mock/mock_odds.json
  dashboard/
    Home.py
    pages/
      1_Match_Detail.py
      2_Top_Picks.py
      3_Bankroll_and_Simulation.py
      4_Audit_Log.py
      5_Settings_and_Risk_Controls.py
    utils/api.py
    Dockerfile
    requirements.txt
  tests/
    test_calculations.py
    test_soccer_model.py
    test_risk_and_idempotency.py
  docker-compose.yml
  .env.example
```

## Quick Start

1. Copy environment file:

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose up --build
```

3. Open:

- Dashboard: http://localhost:8520
- API docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics

Note: if you see a different dashboard at `localhost:8501`, another local Streamlit app is already using that port. Stop that process or remap the dashboard port in `docker-compose.yml`.

## API Highlights

- `GET /api/events`
- `GET /api/events/{event_id}/markets`
- `GET /api/events/{event_id}/recommendations`
- `GET /api/events/{event_id}/analysis`
- `GET /api/events/{event_id}/p-chart`
- `POST /api/events/{event_id}/recommendations/refresh`
- `GET /api/top-picks`
- `POST /api/bets/simulate`
- `POST /api/bets/live` (feature-gated; default blocked)
- `POST /api/bets/settle`
- `GET /api/bankroll`, `GET /api/bankroll/curve`
- `GET /api/audit`
- `GET/PUT /api/settings/risk`
- `POST /api/settings/kill-switch`
- `POST /api/backtest/run`

## Backtest

Backtest runs on stored `odds_snapshots` for an event/market.
If winner labels are missing in snapshots, a fallback inference is used and documented in notes.

## Tests

Run locally from project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pytest -q
```

## Demo Notes

- Works in `mock` mode without funded exchange accounts.
- Seed snapshots are loaded from `backend/data/mock/mock_odds.json`.
- Worker polls continuously and updates recommendations + audit trail.
- Weather context uses Open-Meteo forecast endpoint.
- News context uses Google News RSS search per team to detect injury/dispute risk headlines.

## Beginner Glossary

- `Event`: A match, for example Mexico vs South Africa.
- `Market`: Bet type, for example 3-way moneyline, Over/Under 2.5, BTTS (Both Teams To Score).
- `Selection` / `Outcome`: One option in a market, for example "Mexico win".
- `Decimal Odds`: Payout multiplier. `2.50` means a 1-unit stake returns 2.50 total if it wins.
- `Implied Probability`: Market-estimated chance from odds. Formula: `1 / decimal_odds`.
- `Overround`: Built-in bookmaker margin that pushes combined implied probabilities above 100%.
- `Normalized Implied Probability`: Implied probabilities adjusted to remove overround.
- `Model Probability`: ValueBet IQ probability estimate from odds, team strength, players, weather, and news.
- `Edge`: Difference between model and market probability. Formula: `model_prob - implied_prob`.
- `Expected Value (EV)`: Long-run value estimate. Formula: `model_prob * decimal_odds - 1`.
- `TOP_PICK`: High-value recommendation that passes all risk checks.
- `LEAN`: Smaller value signal; weaker than top pick.
- `NO_BET`: Not enough edge or confidence.
- `BLOCKED_BY_RISK`: Positive edge exists, but risk controls block execution.
- `Risk Tier`: Safety label: `LOW_RISK`, `MEDIUM_RISK`, `HIGH_RISK`, or `PASS`.
- `Bankroll`: Total budget tracked by the app.
- `Stake`: Amount placed on a single bet.
- `Max Stake`: Per-bet cap.
- `Max Exposure per Event`: Maximum combined risk on one match.
- `Max Daily Loss`: Daily drawdown guardrail; blocks new bets after limit.
- `Data Freshness`: Maximum age of odds data before recommendations are blocked.
- `Odds Drift Tolerance`: Max allowed movement from quote to execution.
- `SIM Mode`: Default paper-trading mode (no real money).
- `LIVE Mode`: Optional real execution via official APIs only, behind confirmations and kill switch.
- `Kill Switch`: Emergency stop for all new order execution.
- `Idempotency Key`: Unique request key that prevents accidental duplicate bets.
- `Audit Log`: Immutable activity trail for recommendations, risk decisions, and orders.
- `Backtest`: Replay strategy logic on stored historical odds snapshots.
