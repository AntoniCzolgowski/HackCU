# MatchFlow Dallas Provenance

This demo is designed to stay runnable without live API keys while still making the data story explicit.

## Real Or Seeded-Real Inputs

- Venue names are based on real Dallas and Arlington bars and hotels.
- City anchors and zone placement reflect real districts around AT&T Stadium, downtown Dallas, Las Colinas, and DFW Airport.
- Optional Google Places refresh can overwrite rating, price level, hours, and coordinates.

## Simulated Inputs

- The road graph is a reduced planning network rather than a full OSM export.
- Crowd movement, business footfall, and congestion loads are cohort-simulation outputs.
- DART behavior is represented as a transit access heuristic, not a timetable-accurate schedule replay.

## Replaceable Layers

- Weather defaults to a seeded hot-match profile and can be refreshed from Open-Meteo.
- Business recommendation cards use deterministic heuristics until `ANTHROPIC_API_KEY` is supplied.
- Seed outputs are committed so the app still runs if live refresh fails or APIs are unavailable.
