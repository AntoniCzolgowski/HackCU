# HackCU Monorepo

This repository contains multiple hackathon projects.  
Each project is independently runnable and has its own stack, dependencies, and environment variables.

## Repository Contents

| Path | Project | What it does | Primary stack |
|---|---|---|---|
| `Nivid/bookie-buddy` | Bookie Buddy | FIFA World Cup 2026 betting decision-support platform with simulation-first execution and risk controls | FastAPI, Streamlit, SQLAlchemy, Alembic, Docker |
| `QueryBuddy` | QueryBuddy | Natural-language-to-SQL assistant across multiple microservice-style databases | FastAPI, Anthropic Claude, React (Vite) |
| `WorkoutBuddy` | WorkoutBuddy | AI workout form tracker with rep counting, fatigue scoring, and voice coaching | Streamlit, OpenCV, MediaPipe, SQLite |
| `World Cup Venue Intelligence/Antoni` | MatchFlow Venue Intelligence | Business-intelligence simulator for World Cup venue operators (capacity, staffing, inventory, opportunity scoring) | FastAPI, React + TypeScript, Deck.gl/Maps, ReportLab |

## High-Level Structure

```text
HackCU/
  Nivid/
    bookie-buddy/
  QueryBuddy/
  WorkoutBuddy/
  World Cup Venue Intelligence/
    Antoni/
```

## Global Prerequisites

- Python 3.10+ (3.12 recommended for Bookie Buddy)
- Node.js 18+ (Node 20+ recommended for modern toolchains)
- `npm`
- Docker + Docker Compose (for Bookie Buddy full stack)
- Camera/microphone access (for WorkoutBuddy real-time mode)

## 1) Bookie Buddy (`Nivid/bookie-buddy`)

### What it is

A World Cup betting decision-support app that computes implied probabilities, model probabilities, edge/EV, and recommendation labels (`TOP_PICK`, `LEAN`, `NO_BET`, `BLOCKED_BY_RISK`) with strict safety constraints.

### Main components

- Backend API: `backend/app`
- Polling worker: `backend/app/worker.py`
- Dashboard (Streamlit): `dashboard/Home.py`
- DB migrations: `backend/alembic`
- Tests: `tests`

### Run with Docker (recommended)

```bash
cd Nivid/bookie-buddy
cp .env.example .env
docker compose up --build
```

Open:

- Dashboard: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`

### Core env vars

- `ODDS_PROVIDER_MODE` (`mock` or `odds_api`)
- `ODDS_API_KEY` (required only for live Odds API mode)
- `ENABLE_LIVE_EXECUTION` (default `false`)
- `LIVE_BETFAIR_ENABLED`, `LIVE_MATCHBOOK_ENABLED` (feature flags)
- `API_BASE_URL` (dashboard backend URL)

### Notes

- Designed for simulation-first paper trading.
- Live execution is feature-gated and blocked by default.
- Includes FIFA World Cup group fixture generation in mock mode.

## 2) QueryBuddy (`QueryBuddy`)

### What it is

A chat interface that translates natural language into SQL (and controlled data operations) across multiple mock microservice databases.

### Main components

- Backend API: `QueryBuddy/backend/main.py`
- Schema registry + execution engine: `QueryBuddy/backend/schema_registry.py`
- Frontend (Vite + React): `QueryBuddy/src`
- Edge-case report: `QueryBuddy/EDGE_CASE_REPORT.md`

### Run backend

```bash
cd QueryBuddy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
uvicorn backend.main:app --reload --port 8000
```

### Run frontend

```bash
cd QueryBuddy
npm install
npm run dev
```

Open:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

### API highlights

- `GET /api/schema`
- `POST /api/query`
- `POST /api/execute`
- `POST /api/create-db`
- `POST /api/upload-db`
- `POST /api/connect-mongo`

## 3) WorkoutBuddy (`WorkoutBuddy`)

### What it is

An AI workout assistant with:

- pose detection and joint-angle analysis
- rep counting and form scoring
- fatigue analysis and adaptive feedback
- workout logging in SQLite (`workouts.db`)
- optional voice coaching via ElevenLabs and Groq

### Main components

- Streamlit app: `WorkoutBuddy/app.py`
- Core CV loop variant: `WorkoutBuddy/main.py`
- DB layer: `WorkoutBuddy/database.py`
- Voice systems: `WorkoutBuddy/voice_feedback.py`, `WorkoutBuddy/voice_assistant.py`

### Run Streamlit app

```bash
cd WorkoutBuddy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Optional env vars:

- `ELEVENLABS_API_KEY`
- `GROQ_API_KEY`

### Notes

- Without API keys, core tracking still works, but AI voice features degrade gracefully.
- Camera permissions are required for live tracking mode.

## 4) MatchFlow Venue Intelligence (`World Cup Venue Intelligence/Antoni`)

### What it is

A World Cup host-city business simulation and operator dashboard focused on venue demand, staffing, inventory planning, and opportunity scoring.

### Main components

- API: `World Cup Venue Intelligence/Antoni/apps/api/app/main.py`
- Web app: `World Cup Venue Intelligence/Antoni/apps/web`
- Data + provenance docs: `data/`, `docs/provenance-report.md`
- Utility scripts: `scripts/`

### Run (Windows scripts)

```powershell
cd "World Cup Venue Intelligence/Antoni"
.\scripts\start-demo.ps1
```

Stop:

```powershell
.\scripts\stop-demo.ps1
```

### Manual run (cross-platform)

Backend:

```bash
cd "World Cup Venue Intelligence/Antoni/apps/api"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd "World Cup Venue Intelligence/Antoni"
npm install
npm run web:dev
```

Open:

- Web: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`

Optional env vars (from `.env.example`):

- `GOOGLE_MAPS_API_KEY`
- `VITE_GOOGLE_MAPS_API_KEY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

## Project-Level Documentation

- Bookie Buddy: `Nivid/bookie-buddy/README.md`
- QueryBuddy: `QueryBuddy/README.md`
- QueryBuddy bug/edge report: `QueryBuddy/EDGE_CASE_REPORT.md`
- MatchFlow Venue Intelligence: `World Cup Venue Intelligence/Antoni/README.md`

## Testing

Bookie Buddy:

```bash
cd Nivid/bookie-buddy
pytest -q
```

QueryBuddy:

- No unified test command documented in project README.
- Refer to `QueryBuddy/EDGE_CASE_REPORT.md` for validated bug-fix coverage notes.

WorkoutBuddy:

- No full automated suite documented; use runtime validation through Streamlit flow.

MatchFlow Venue Intelligence:

Backend:

```bash
cd "World Cup Venue Intelligence/Antoni/apps/api"
pytest tests -q
```

Frontend:

```bash
cd "World Cup Venue Intelligence/Antoni"
npm run web:test
```

## Port Reference

- `3000`: QueryBuddy frontend
- `5173`: MatchFlow frontend
- `5432`: Bookie Buddy Postgres
- `8000`: Bookie Buddy API or QueryBuddy API or MatchFlow API (run one at a time unless remapped)
- `8501`: Bookie Buddy dashboard (Docker)

## Troubleshooting

- If a dashboard/API opens the wrong app, a different service is already bound to that port.
- When running multiple projects simultaneously, remap ports to avoid collisions.
- Keep each project's virtual environment isolated.
- Do not commit `.env` files or secret keys.
