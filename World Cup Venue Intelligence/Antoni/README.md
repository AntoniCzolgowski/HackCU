# MatchFlow World Cup Venue Intelligence (Antoni Edition)

Business-intelligence simulator for FIFA World Cup 2026 host cities.

This branch focuses on one goal: make the app genuinely useful for venue owners (bars, restaurants, hotels) while also delivering a cinematic, high-end operator dashboard experience.

## Why this version exists

Most crowd tools show heatmaps and raw footfall. Operators need decisions:

- Which match should I staff up for?
- When do I hit overload and queue risk?
- What should I stock for this fan mix?
- How does this compare across the city portfolio?

This edition turns simulation output into consulting-grade business actions.

## Antoni scope delivered

### Consulting features

- **Opportunity Board** (`/api/business/{id}/opportunity-board`)
  - Relative, match-by-match opportunity scoring (0-100)
  - Revenue, demand, risk, capture, confidence breakdown
  - Portfolio metrics: best match, volatility, risk exposure, execution pressure, stability score
  - Quick recommendation per match: `Push`, `Hold`, `Avoid`
- **Staffing Calculator**
  - Hourly staffing plan derived from 15-minute demand series and venue type ratios
- **Inventory Prep Guide**
  - Stocking recommendations (beer/cocktails/soft drinks/water/food)
  - Nationality-aware note using match cultural context
- **Capacity Alert Banner**
  - Warning and danger tiers for projected overload windows
- **CSV Export**
  - Business summary + full 15-minute series export, with safe CSV escaping

### Simulation realism upgrades

- Stronger hotel behavior realism across the 3-day window:
  - Day `-1`: preload traffic from arriving fans
  - Day `0`: match-day saturation and high pressure
  - Day `+1`: departure waves and cooling demand
- Expanded hotel coverage in city packs:
  - Dallas: 13 hotel/hotel_bar venues
  - Houston: 8
  - Kansas City: 7
  - Miami: 6
  - San Francisco: 7
  - Monterrey: 6

### Visual and cinematic upgrades

- Opportunity board KPI glow, staggered reveal, animated chart fills
- Selected entity pulse on map (Deck.gl animated radius/alpha)
- Crossfade transitions in panel flows
- Tooltip/hovers for new metrics (aligned to dashboard style)
- `prefers-reduced-motion` accessibility fallback

### Reporting quality upgrades

- Multi-page PDF report rebuilt with cursor-based layout flow to prevent overlaps
- Right-dashboard intelligence included in report:
  - capacity + staffing + inventory
  - competition + opportunity board
  - recommendation + methodology context
- Cleaner typography, spacing, and section framing for presentation use

## Host city coverage

Currently seeded for:

- Dallas
- Houston
- Kansas City
- Miami
- San Francisco
- Monterrey

## Architecture

### Backend (`apps/api`)

- FastAPI service
- Deterministic cohort simulation engine
- Business, zone, reporting, and optimization endpoints
- Optional live enrichment:
  - Open-Meteo weather overrides
  - Google Places metadata refresh
  - Gemini-generated recommendation copy (with heuristic fallback)

### Frontend (`apps/web`)

- React 19 + Vite + TypeScript
- Google Maps + Deck.gl layers for live geospatial playback
- Recharts for demand/revenue/risk visual analytics
- Right-side business drawer for operator workflow

## API highlights

- `GET /api/health`
- `GET /api/matches`
- `GET /api/meta`
- `GET /api/simulation`
- `GET /api/business/{business_id}`
- `GET /api/business/{business_id}/compare`
- `GET /api/business/{business_id}/opportunity-board`
- `GET /api/zone/{zone_id}`
- `POST /api/business/{business_id}/report`
- `GET /api/reports/{job_id}`
- `GET /api/reports/{job_id}/download`
- `POST /api/what-if` (deferred in UI, API kept)
- `GET /api/optimize-signals`
- `GET /api/provenance`

Validation behavior:

- Invalid `day` input returns `422`
- Unknown business for opportunity board returns `404`

## Quick start (Windows)

```powershell
cd "World Cup Venue Intelligence/Antoni"
.\scripts\start-demo.ps1
```

App opens at:

- Web: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`

Stop demo:

```powershell
.\scripts\stop-demo.ps1
```

Refresh live enrichment + regenerate baselines:

```powershell
.\scripts\refresh-data.ps1
```

## Environment variables

Copy `.env.example` to `.env`.

Optional keys:

- `GOOGLE_MAPS_API_KEY`
- `VITE_GOOGLE_MAPS_API_KEY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (default: `gemini-3-flash-preview`)

Match override helpers:

- `MATCHFLOW_MATCH_DATE`
- `MATCHFLOW_HOME_TEAM`
- `MATCHFLOW_AWAY_TEAM`

If no Gemini key is present, recommendations automatically fall back to deterministic heuristics.

## Testing

### Backend

```powershell
cd "World Cup Venue Intelligence/Antoni/apps/api"
python -m pip install -r requirements.txt
pytest tests -q
```

Coverage includes:

- opportunity board bounds/schema and missing business behavior
- invalid day validation (`422`)
- weather override compatibility (city-aware + legacy shape)
- simulation realism checks including hotel pre/post waves

### Frontend

```powershell
cd "World Cup Venue Intelligence/Antoni"
npm install
npm run web:test
```

## Data provenance

See [`docs/provenance-report.md`](docs/provenance-report.md) for seeded vs simulated vs live-refreshed layers.

## Security and key hygiene

- Never commit `.env` or API keys.
- Keep cloud and LLM credentials local.
- Generated reports and cached processed data are local artifacts unless explicitly shared.

## Recommended next iteration

- Scenario planner UI for `what-if` endpoint
- More city packs and neighborhood archetypes
- Calibration pass on spillover/risk to improve low-variance portfolios
- PDF branding templates per operator or city authority
