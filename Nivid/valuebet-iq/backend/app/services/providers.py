from __future__ import annotations

import itertools
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings


@dataclass
class ProviderOutcome:
    name: str
    decimal_odds: float
    raw: dict


@dataclass
class ProviderMarket:
    key: str
    last_updated: datetime
    outcomes: list[ProviderOutcome]


@dataclass
class ProviderEvent:
    provider_event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    competition_stage: str | None
    venue_name: str | None
    venue_city: str | None
    venue_country: str | None
    venue_lat: float | None
    venue_lon: float | None
    start_time: datetime
    is_live: bool
    status: str
    markets: list[ProviderMarket]
    context_payload: dict
    raw: dict


class BaseOddsProvider:
    provider_name = "base"

    def fetch_events(self):
        raise NotImplementedError


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return cleaned.strip("_") or "team"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _default_profile(team: str, payload: dict[str, Any]) -> dict[str, float]:
    predefined = payload.get("team_profiles", {}).get(team)
    if predefined:
        return {
            "attack": float(predefined.get("attack", 1.35)),
            "defense": float(predefined.get("defense", 1.10)),
            "strength": float(predefined.get("strength", 0.50)),
        }

    h = abs(hash(team))
    attack = 1.05 + (h % 70) / 100.0
    defense = 0.90 + ((h // 7) % 65) / 100.0
    strength = _clamp(0.35 + ((h // 13) % 55) / 100.0, 0.30, 0.90)
    return {"attack": attack, "defense": defense, "strength": strength}


def _form_from_strength(strength: float) -> list[str]:
    if strength >= 0.72:
        return ["W", "W", "D", "W", "W"]
    if strength >= 0.60:
        return ["W", "D", "W", "W", "D"]
    if strength >= 0.50:
        return ["W", "D", "L", "W", "D"]
    return ["L", "D", "L", "W", "D"]


def _standing_for_team(group_teams: list[str], team: str, payload: dict[str, Any]) -> dict[str, float]:
    ranked = sorted(group_teams, key=lambda t: _default_profile(t, payload)["strength"], reverse=True)
    rank = ranked.index(team) + 1
    points = max(0, 8 - rank * 2)
    gd = max(-3, 4 - rank)
    return {"group_rank": rank, "points": points, "goal_diff": gd}


def _player_rows(team: str, payload: dict[str, Any], strength: float) -> list[dict[str, Any]]:
    predefined = payload.get("team_players", {}).get(team)
    if predefined:
        rows = []
        for row in predefined:
            rows.append(
                {
                    "name": row.get("name"),
                    "team": team,
                    "status": row.get("status", "available"),
                    "fitness": float(row.get("fitness", 0.9)),
                    "impact": float(row.get("impact", 0.65)),
                    "score_share": float(row.get("score_share", 0.20)),
                    "assist_share": float(row.get("assist_share", 0.10)),
                }
            )
        return rows

    base = _clamp(0.58 + strength * 0.35, 0.55, 0.9)
    return [
        {
            "name": f"{team} Forward",
            "team": team,
            "status": "available",
            "fitness": 0.92,
            "impact": round(base, 2),
            "score_share": round(_clamp(0.16 + strength * 0.16, 0.15, 0.30), 2),
            "assist_share": 0.10,
        },
        {
            "name": f"{team} Creator",
            "team": team,
            "status": "available",
            "fitness": 0.90,
            "impact": round(_clamp(base - 0.06, 0.5, 0.85), 2),
            "score_share": 0.11,
            "assist_share": 0.16,
        },
    ]


def _odds_from_probability(probability: float, tick: int, salt: int) -> float:
    vig = 1.055
    implied = _clamp(probability * vig, 0.03, 0.93)
    odds = 1.0 / implied
    bump = 1.0 + 0.008 * math.sin((tick + salt) / 3.7)
    return round(max(1.01, odds * bump), 3)


def _market_outcomes(home: str, away: str, payload: dict[str, Any], tick: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    home_p = _default_profile(home, payload)
    away_p = _default_profile(away, payload)

    diff = home_p["strength"] - away_p["strength"]
    draw_prob = _clamp(0.26 - abs(diff) * 0.08, 0.16, 0.30)
    home_prob = _clamp(0.44 + diff * 0.33, 0.20, 0.72)
    away_prob = _clamp(1.0 - home_prob - draw_prob, 0.12, 0.68)
    norm_total = home_prob + draw_prob + away_prob
    home_prob, draw_prob, away_prob = [x / norm_total for x in (home_prob, draw_prob, away_prob)]

    total_xg = home_p["attack"] + away_p["attack"]
    over_prob = _clamp(0.38 + (total_xg - 2.4) * 0.20, 0.22, 0.76)
    under_prob = 1.0 - over_prob

    btts_yes = _clamp(0.45 + (min(home_p["attack"], away_p["attack"]) - 1.1) * 0.16, 0.25, 0.78)
    btts_no = 1.0 - btts_yes

    home_yes = home_prob * btts_yes * 0.85
    away_yes = away_prob * btts_yes * 0.85
    draw_yes = draw_prob * btts_yes * 0.65
    home_no = max(0.03, home_prob - home_yes)
    away_no = max(0.03, away_prob - away_yes)
    draw_no = max(0.03, draw_prob - draw_yes)

    players = _player_rows(home, payload, home_p["strength"]) + _player_rows(away, payload, away_p["strength"])

    markets = [
        {
            "key": "moneyline_3way",
            "outcomes": [
                {"name": home, "odds": _odds_from_probability(home_prob, tick, 1)},
                {"name": "Draw", "odds": _odds_from_probability(draw_prob, tick, 2)},
                {"name": away, "odds": _odds_from_probability(away_prob, tick, 3)},
            ],
        },
        {
            "key": "totals_2_5",
            "outcomes": [
                {"name": "Over 2.5", "odds": _odds_from_probability(over_prob, tick, 4)},
                {"name": "Under 2.5", "odds": _odds_from_probability(under_prob, tick, 5)},
            ],
        },
        {
            "key": "btts",
            "outcomes": [
                {"name": "Yes", "odds": _odds_from_probability(btts_yes, tick, 6)},
                {"name": "No", "odds": _odds_from_probability(btts_no, tick, 7)},
            ],
        },
        {
            "key": "result_btts",
            "outcomes": [
                {"name": f"{home} & Yes", "odds": _odds_from_probability(home_yes, tick, 8)},
                {"name": f"{home} & No", "odds": _odds_from_probability(home_no, tick, 9)},
                {"name": "Draw & Yes", "odds": _odds_from_probability(draw_yes, tick, 10)},
                {"name": "Draw & No", "odds": _odds_from_probability(draw_no, tick, 11)},
                {"name": f"{away} & Yes", "odds": _odds_from_probability(away_yes, tick, 12)},
                {"name": f"{away} & No", "odds": _odds_from_probability(away_no, tick, 13)},
            ],
        },
        {
            "key": "correct_score",
            "outcomes": [
                {"name": "1-0", "odds": _odds_from_probability(0.11 + diff * 0.04, tick, 14)},
                {"name": "2-1", "odds": _odds_from_probability(0.09 + diff * 0.03, tick, 15)},
                {"name": "1-1", "odds": _odds_from_probability(0.13 - abs(diff) * 0.02, tick, 16)},
                {"name": "0-1", "odds": _odds_from_probability(0.10 - diff * 0.04, tick, 17)},
                {"name": "2-2", "odds": _odds_from_probability(0.06, tick, 18)},
            ],
        },
        {
            "key": "player_goal_or_assist",
            "outcomes": [
                {"name": p["name"], "odds": _odds_from_probability(_clamp(p["score_share"] + p["assist_share"] * 0.55, 0.05, 0.60), tick, 19 + i)}
                for i, p in enumerate(players)
            ],
        },
        {
            "key": "player_anytime_scorer",
            "outcomes": [
                {"name": p["name"], "odds": _odds_from_probability(_clamp(p["score_share"], 0.05, 0.55), tick, 31 + i)}
                for i, p in enumerate(players)
            ],
        },
    ]

    context = {
        "pitch_type": "Natural Grass",
        "altitude_m": 150,
        "home_form": _form_from_strength(home_p["strength"]),
        "away_form": _form_from_strength(away_p["strength"]),
        "home_standing": {},
        "away_standing": {},
        "home_team_xg": round(home_p["attack"], 2),
        "away_team_xg": round(away_p["attack"], 2),
        "home_team_xga": round(home_p["defense"], 2),
        "away_team_xga": round(away_p["defense"], 2),
        "players": players,
    }
    return markets, context


class MockOddsProvider(BaseOddsProvider):
    provider_name = "mock"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.seed_path = Path(settings.mock_seed_path)

    def _events_from_groups(self, payload: dict[str, Any], now: datetime) -> list[ProviderEvent]:
        groups: dict[str, list[str]] = payload.get("groups", {})
        venues: list[dict[str, Any]] = payload.get("venues", [])
        fixtures_per_group = int(payload.get("fixtures_per_group", 6))
        start_time = date_parser.isoparse(payload.get("start_time_utc", "2026-06-11T16:00:00Z"))

        events: list[ProviderEvent] = []
        fixture_index = 0
        tick = int(now.timestamp() // 60)

        for group_name in sorted(groups.keys()):
            teams = groups[group_name]
            all_pairs = list(itertools.combinations(teams, 2))
            pairs = all_pairs[: min(fixtures_per_group, len(all_pairs))]

            for local_idx, (team_a, team_b) in enumerate(pairs):
                home_team, away_team = (team_a, team_b) if local_idx % 2 == 0 else (team_b, team_a)
                kickoff = start_time + timedelta(hours=fixture_index * 4)
                is_live = kickoff <= now <= kickoff + timedelta(hours=2)

                venue = venues[fixture_index % len(venues)] if venues else {}

                markets_raw, context = _market_outcomes(home_team, away_team, payload, tick + fixture_index)
                context["home_standing"] = _standing_for_team(teams, home_team, payload)
                context["away_standing"] = _standing_for_team(teams, away_team, payload)

                markets: list[ProviderMarket] = []
                for market in markets_raw:
                    outcomes = [
                        ProviderOutcome(name=row["name"], decimal_odds=float(row["odds"]), raw=row)
                        for row in market["outcomes"]
                    ]
                    markets.append(
                        ProviderMarket(
                            key=market["key"],
                            last_updated=now,
                            outcomes=outcomes,
                        )
                    )

                event_id = f"wc_2026_group_{group_name.lower()}_{_slug(home_team)}_{_slug(away_team)}"
                events.append(
                    ProviderEvent(
                        provider_event_id=event_id,
                        sport="soccer_fifa_world_cup",
                        league="FIFA World Cup 2026",
                        home_team=home_team,
                        away_team=away_team,
                        competition_stage=f"Group {group_name}",
                        venue_name=venue.get("name"),
                        venue_city=venue.get("city"),
                        venue_country=venue.get("country"),
                        venue_lat=venue.get("lat"),
                        venue_lon=venue.get("lon"),
                        start_time=kickoff,
                        is_live=is_live,
                        status="live" if is_live else "scheduled",
                        markets=markets,
                        context_payload=context,
                        raw={"group": group_name},
                    )
                )
                fixture_index += 1

        return events

    def fetch_events(self) -> list[ProviderEvent]:
        payload = json.loads(self.seed_path.read_text())
        now = datetime.now(timezone.utc)

        if payload.get("groups"):
            return self._events_from_groups(payload, now)

        events: list[ProviderEvent] = []
        tick = int(now.timestamp() // 60)
        for row in payload.get("events", []):
            league = row.get("league", "unknown")
            if self.settings.world_cup_only and self.settings.world_cup_league_name.lower() not in league.lower():
                continue

            markets = []
            for market in row.get("markets", []):
                outcomes = []
                for o in market.get("outcomes", []):
                    nudged = max(
                        1.01,
                        round(float(o["odds"]) * (1.0 + 0.01 * math.sin((tick + abs(hash(o["name"])) % 9) / 2.9)), 3),
                    )
                    outcomes.append(ProviderOutcome(name=o["name"], decimal_odds=nudged, raw=o))

                if outcomes:
                    markets.append(ProviderMarket(key=market.get("key", "h2h"), last_updated=now, outcomes=outcomes))

            if not markets:
                continue

            events.append(
                ProviderEvent(
                    provider_event_id=row["id"],
                    sport=row.get("sport", "soccer_fifa_world_cup"),
                    league=league,
                    home_team=row["home_team"],
                    away_team=row["away_team"],
                    competition_stage=row.get("competition_stage"),
                    venue_name=row.get("venue", {}).get("name"),
                    venue_city=row.get("venue", {}).get("city"),
                    venue_country=row.get("venue", {}).get("country"),
                    venue_lat=row.get("venue", {}).get("lat"),
                    venue_lon=row.get("venue", {}).get("lon"),
                    start_time=date_parser.isoparse(row["start_time"]),
                    is_live=bool(row.get("is_live", False)),
                    status=row.get("status", "scheduled"),
                    markets=markets,
                    context_payload=row.get("context", {}),
                    raw=row,
                )
            )

        return events


class TheOddsApiProvider(BaseOddsProvider):
    provider_name = "the_odds_api"

    def __init__(self, settings: Settings):
        self.settings = settings

    @retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(4), reraise=True)
    def _fetch_sport_odds(self, client: httpx.Client, sport_key: str) -> tuple[list[dict], int | None]:
        url = f"{self.settings.odds_api_base_url}/sports/{sport_key}/odds"
        params = {
            "apiKey": self.settings.odds_api_key,
            "regions": self.settings.odds_provider_region,
            "markets": self.settings.odds_provider_market_types,
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }
        response = client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        remaining = response.headers.get("x-requests-remaining")
        return response.json(), int(remaining) if remaining and remaining.isdigit() else None

    def fetch_events(self) -> tuple[list[ProviderEvent], int | None]:
        sports = [s.strip() for s in self.settings.odds_api_sports.split(",") if s.strip()]
        events: list[ProviderEvent] = []
        rate_remaining: int | None = None

        with httpx.Client() as client:
            for sport_key in sports:
                rows, rem = self._fetch_sport_odds(client, sport_key)
                rate_remaining = rem if rem is not None else rate_remaining
                for row in rows:
                    league = row.get("sport_title", sport_key)
                    if self.settings.world_cup_only and self.settings.world_cup_league_name.lower() not in league.lower():
                        continue

                    bookmakers = row.get("bookmakers", [])
                    if not bookmakers:
                        continue
                    chosen_book = bookmakers[0]
                    markets: list[ProviderMarket] = []

                    for m in chosen_book.get("markets", []):
                        outcomes = [
                            ProviderOutcome(name=o.get("name", "unknown"), decimal_odds=float(o["price"]), raw=o)
                            for o in m.get("outcomes", [])
                            if "price" in o
                        ]
                        if not outcomes:
                            continue
                        markets.append(
                            ProviderMarket(
                                key=m.get("key", "h2h"),
                                last_updated=date_parser.isoparse(m.get("last_update", row.get("commence_time"))),
                                outcomes=outcomes,
                            )
                        )

                    if not markets:
                        continue

                    commence_time = date_parser.isoparse(row["commence_time"])
                    is_live = commence_time <= datetime.now(timezone.utc)

                    events.append(
                        ProviderEvent(
                            provider_event_id=row["id"],
                            sport=sport_key,
                            league=league,
                            home_team=row["home_team"],
                            away_team=row["away_team"],
                            competition_stage=row.get("stage"),
                            venue_name=row.get("venue") or None,
                            venue_city=None,
                            venue_country=None,
                            venue_lat=None,
                            venue_lon=None,
                            start_time=commence_time,
                            is_live=is_live,
                            status="live" if is_live else "scheduled",
                            markets=markets,
                            context_payload={},
                            raw=row,
                        )
                    )

        return events, rate_remaining
