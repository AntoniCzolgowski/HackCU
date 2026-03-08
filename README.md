# MatchFlow Dallas

Local-first demo product for replaying, exploring, and stress-testing fan movement around AT&T Stadium in Arlington.

## What It Includes

- FastAPI backend with a deterministic cohort-based simulation engine
- React + Vite frontend with an interactive map, business dashboard, planner mode, and provenance report
- Seeded real-world-inspired Dallas/Arlington venues, zones, roads, and match scenario data
- Optional Google Places and Gemini enrichment layers that can be enabled later through environment variables
- One-click Windows scripts for local startup and data refresh

## Quick Start

1. Run `.\scripts\start-demo.ps1`
2. Wait for the backend and frontend health checks to pass
3. The app opens in your browser on `http://127.0.0.1:5173`

## Optional Environment Variables

Copy `.env.example` to `.env` and fill any keys you want to enable:

- `GOOGLE_MAPS_API_KEY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

The demo runs without these keys by using seeded data and heuristic recommendations.
