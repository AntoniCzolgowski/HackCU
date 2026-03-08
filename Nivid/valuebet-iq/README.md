# ValueBet IQ

ValueBet IQ is a production-style hackathon web app for FIFA World Cup betting decision support.

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
- Streamlit dashboard (6 pages, futuristic dark UI)
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

- Dashboard: http://localhost:8501
- API docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics

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
