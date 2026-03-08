from __future__ import annotations

import copy
import csv
import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import CITY_DATA_DIR, PROCESSED_DIR, RAW_DIR, SEED_DIR


SCHEDULE_PATH = SEED_DIR / "world_cup_schedule.csv"
PROVENANCE_PATH = PROCESSED_DIR / "provenance_report.json"
LIVE_ENRICHMENT_PATH = RAW_DIR / "live_enrichment.json"
DEFAULT_CITY_ID = "dallas"

CITY_TIMEZONES = {
    "dallas": "America/Chicago",
    "houston": "America/Chicago",
    "kansas-city": "America/Chicago",
    "miami": "America/New_York",
    "san-francisco": "America/Los_Angeles",
    "monterrey": "America/Monterrey",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


TEAM_TRAITS: dict[str, dict[str, Any]] = {
    "Algeria": {"color": "#006233", "fan_strength": 0.92, "ticket_rate": 0.74, "spend": 36, "note": "Algerian supporters gather loudly around communal watch spots and respond well to high-energy service windows."},
    "Argentina": {"color": "#74ACDF", "fan_strength": 1.18, "ticket_rate": 0.84, "spend": 48, "note": "Argentine fans arrive early, sing continuously, and keep spending well into the post-match window."},
    "Australia": {"color": "#FFCD00", "fan_strength": 0.86, "ticket_rate": 0.69, "spend": 40, "note": "Australian travelers skew social and favor flexible grab-and-go service around kickoff and full time."},
    "Austria": {"color": "#ED2939", "fan_strength": 0.85, "ticket_rate": 0.68, "spend": 39, "note": "Austrian fans lean toward beer-led gatherings and arrive in smaller, orderly groups."},
    "Brazil": {"color": "#009739", "fan_strength": 1.14, "ticket_rate": 0.82, "spend": 50, "note": "Brazilian fans create carnival-style atmospheres and sustain late post-match celebration demand."},
    "Cape Verde": {"color": "#003893", "fan_strength": 0.76, "ticket_rate": 0.65, "spend": 34, "note": "Cape Verde supporters cluster tightly and favor upbeat social venues over quiet lounges."},
    "Colombia": {"color": "#FCD116", "fan_strength": 1.02, "ticket_rate": 0.78, "spend": 44, "note": "Colombian fans arrive in yellow waves, favor music-heavy bars, and keep the post-match dwell high."},
    "Croatia": {"color": "#171796", "fan_strength": 0.9, "ticket_rate": 0.73, "spend": 42, "note": "Croatian supporters are organized, beer-driven, and responsive to simple fast-pour service."},
    "Curacao": {"color": "#0057B8", "fan_strength": 0.74, "ticket_rate": 0.63, "spend": 33, "note": "Curacao supporters mix easily with neutrals and perform well in open-air watch-party environments."},
    "Ecuador": {"color": "#FFD100", "fan_strength": 0.88, "ticket_rate": 0.71, "spend": 36, "note": "Ecuadorian fans travel in social groups and favor lively, Latin-forward match atmospheres."},
    "England": {"color": "#C8102E", "fan_strength": 1.08, "ticket_rate": 0.81, "spend": 49, "note": "England fans are early-arriving, beer-heavy, and can spike both pre-match and full-time demand."},
    "Germany": {"color": "#1F2937", "fan_strength": 1.0, "ticket_rate": 0.79, "spend": 45, "note": "German fans favor efficient service, premium lager, and substantial food around the match window."},
    "Japan": {"color": "#BC002D", "fan_strength": 0.9, "ticket_rate": 0.77, "spend": 41, "note": "Japanese fans arrive early, value orderly service, and maintain strong in-match occupancy."},
    "Jordan": {"color": "#007A3D", "fan_strength": 0.78, "ticket_rate": 0.66, "spend": 34, "note": "Jordanian fans tend to cluster in family and friend groups with steady food-and-tea demand around kickoff."},
    "Netherlands": {"color": "#F97316", "fan_strength": 1.02, "ticket_rate": 0.8, "spend": 47, "note": "Dutch supporters travel well, adopt central meeting points, and create strong pre-match bar demand."},
    "Paraguay": {"color": "#D52B1E", "fan_strength": 0.84, "ticket_rate": 0.69, "spend": 35, "note": "Paraguayan fans gravitate toward high-energy bars and respond well to sharable food bundles."},
    "Playoff A": {"color": "#7C3AED", "fan_strength": 0.82, "ticket_rate": 0.67, "spend": 38, "note": "Playoff-qualified supporters behave like high-uncertainty travelers: later booking, later arrivals, and strong social clustering."},
    "Playoff C": {"color": "#8B5CF6", "fan_strength": 0.82, "ticket_rate": 0.67, "spend": 38, "note": "Playoff-qualified supporters behave like high-uncertainty travelers: later booking, later arrivals, and strong social clustering."},
    "Playoff D": {"color": "#A855F7", "fan_strength": 0.82, "ticket_rate": 0.67, "spend": 38, "note": "Playoff-qualified supporters behave like high-uncertainty travelers: later booking, later arrivals, and strong social clustering."},
    "Poland": {"color": "#DC143C", "fan_strength": 0.94, "ticket_rate": 0.78, "spend": 44, "note": "Polish fans gather in large beer-led groups, arrive early, and stay late in pub environments."},
    "Portugal": {"color": "#006600", "fan_strength": 1.01, "ticket_rate": 0.79, "spend": 46, "note": "Portuguese fans are social and sustained spenders, especially in late-afternoon and evening kickoffs."},
    "Qatar": {"color": "#8A1538", "fan_strength": 0.8, "ticket_rate": 0.68, "spend": 43, "note": "Qatari fans skew premium and respond well to polished hospitality and lounge-like service."},
    "Saudi Arabia": {"color": "#006C35", "fan_strength": 0.9, "ticket_rate": 0.73, "spend": 39, "note": "Saudi supporters favor group seating, family-style ordering, and strong pre-match congregation."},
    "Scotland": {"color": "#005EB8", "fan_strength": 0.98, "ticket_rate": 0.79, "spend": 46, "note": "Scottish fans create loud pub atmospheres and can stretch the post-match beer window."},
    "South Africa": {"color": "#007749", "fan_strength": 0.83, "ticket_rate": 0.68, "spend": 35, "note": "South African supporters gather in upbeat groups and respond well to visible communal watch areas."},
    "South Korea": {"color": "#CD2E3A", "fan_strength": 0.9, "ticket_rate": 0.75, "spend": 40, "note": "South Korean fans arrive early, favor organized service, and sustain in-match occupancy for the full broadcast window."},
    "Switzerland": {"color": "#D52B1E", "fan_strength": 0.87, "ticket_rate": 0.72, "spend": 43, "note": "Swiss supporters favor orderly service and mid-premium food and drink spend."},
    "Tunisia": {"color": "#E70013", "fan_strength": 0.84, "ticket_rate": 0.69, "spend": 35, "note": "Tunisian fans respond well to communal viewing spaces and fast food service near kickoff."},
    "Uruguay": {"color": "#6CB4EE", "fan_strength": 0.95, "ticket_rate": 0.77, "spend": 44, "note": "Uruguayan fans are intense but steady, with strong pre-match food demand and late full-time linger."},
    "Uzbekistan": {"color": "#0099B5", "fan_strength": 0.79, "ticket_rate": 0.67, "spend": 34, "note": "Uzbekistan supporters skew family-and-friend-group oriented and fit well in seated watch venues."},
}


def normalize_team_label(label: str) -> str:
    cleaned = (label or "").strip()
    if not cleaned:
        return "Unknown"
    if cleaned == "UEFA Winner B":
        return "Poland"
    if cleaned in {"UEFA Winner C", "Winner C"}:
        return "Playoff C"
    if cleaned in {"UEFA Winner D", "Winner D"}:
        return "Playoff D"
    if "Winner" in cleaned:
        return "Playoff A"
    return cleaned


def _slug_team(label: str) -> str:
    return normalize_team_label(label).lower().replace(" ", "_").replace("-", "_")


def _city_dir(city_id: str) -> Path:
    return CITY_DATA_DIR / city_id


def _venue_capacity(venue_name: str) -> int:
    return {
        "AT&T Stadium": 80000,
        "NRG Stadium": 72000,
        "Arrowhead Stadium": 76000,
        "Hard Rock Stadium": 65000,
        "Levi's Stadium": 68000,
        "Estadio BBVA": 53000,
    }.get(venue_name, 60000)


def _team_info(label: str, color_hint: str | None) -> dict[str, Any]:
    name = normalize_team_label(label)
    traits = TEAM_TRAITS.get(name, {})
    return {
        "id": _slug_team(name),
        "name": name,
        "color": color_hint or traits.get("color", "#94A3B8"),
    }


def _weekday_multiplier(match_date: date) -> float:
    weekday = match_date.weekday()
    if weekday <= 3:
        return 0.82
    if weekday == 4:
        return 0.95
    return 1.15


def _kickoff_dt(row: dict[str, str]) -> datetime:
    timezone = ZoneInfo(CITY_TIMEZONES.get(row["city_id"], "America/Chicago"))
    local_time = datetime.fromisoformat(f"{row['match_date_local']}T{row['kickoff_local']}:00")
    return local_time.replace(tzinfo=timezone)


def _team_strength(name: str) -> float:
    return TEAM_TRAITS.get(name, {}).get("fan_strength", 0.85)


def _team_ticket_rate(name: str) -> float:
    return TEAM_TRAITS.get(name, {}).get("ticket_rate", 0.68)


def _team_spend(name: str) -> float:
    return TEAM_TRAITS.get(name, {}).get("spend", 38)


def _team_note(name: str) -> str:
    return TEAM_TRAITS.get(name, {}).get("note", "")


def _build_weather(kickoff: datetime) -> dict[str, dict[str, Any]]:
    if kickoff.month == 6:
        day_before_temp = 31 if kickoff.hour >= 18 else 33
        match_day_temp = 34 if kickoff.hour >= 18 else 36
        day_after_temp = 32 if kickoff.hour >= 18 else 34
    else:
        day_before_temp = 33
        match_day_temp = 35
        day_after_temp = 32

    def walking_modifier(temp_c: int, evening: bool) -> float:
        base = 0.96 if evening else 0.88
        return round(max(0.68, base - max(0, temp_c - 30) * 0.02), 2)

    evening = kickoff.hour >= 18
    return {
        "-1": {
            "temp_c": day_before_temp,
            "condition": "Warm and clear" if evening else "Hot and sunny",
            "walking_modifier": walking_modifier(day_before_temp, evening),
        },
        "0": {
            "temp_c": match_day_temp,
            "condition": "Pleasant evening kickoff" if evening else "Hot afternoon",
            "walking_modifier": walking_modifier(match_day_temp, evening),
        },
        "1": {
            "temp_c": day_after_temp,
            "condition": "Warm with light cloud" if evening else "Dry heat easing",
            "walking_modifier": walking_modifier(day_after_temp, evening),
        },
    }


def _build_crowd_profile(home_team: str, away_team: str, kickoff: datetime) -> dict[str, Any]:
    home_strength = _team_strength(home_team)
    away_strength = _team_strength(away_team)
    locals_multiplier = _weekday_multiplier(kickoff.date())
    evening_boost = 1.08 if kickoff.hour >= 18 else 0.96

    weights = {
        "team_a": 0.27 * home_strength,
        "team_b": 0.26 * away_strength,
        "neutral": 0.18 * (1.02 if kickoff.hour >= 18 else 0.94),
        "locals": 0.23 * locals_multiplier * evening_boost,
    }
    total = sum(weights.values()) or 1.0
    nationality_weights = {key: round(value / total, 4) for key, value in weights.items()}

    ticket_rates = {
        "team_a": round(min(0.9, _team_ticket_rate(home_team) + 0.04), 2),
        "team_b": round(min(0.9, _team_ticket_rate(away_team) + 0.04), 2),
        "neutral": 0.56 if kickoff.hour >= 18 else 0.5,
        "locals": round(min(0.62, 0.38 * locals_multiplier + (0.05 if kickoff.hour >= 18 else 0.0)), 2),
    }

    avg_spend = {
        "team_a": round(_team_spend(home_team), 2),
        "team_b": round(_team_spend(away_team), 2),
        "neutral": round(max(_team_spend(home_team), _team_spend(away_team)) + 8, 2),
        "locals": 32 if kickoff.hour >= 18 else 29,
    }

    return {
        "nationality_weights": nationality_weights,
        "ticket_rates": ticket_rates,
        "avg_spend_per_visitor": avg_spend,
        "locals_multiplier": locals_multiplier,
        "attendance_multiplier": min(1.5, round(1.2 + max(home_strength, away_strength) * 0.15 + (0.08 if kickoff.hour >= 18 else 0.0), 2)),
    }


@lru_cache(maxsize=1)
def load_schedule_rows() -> list[dict[str, str]]:
    with SCHEDULE_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=_kickoff_dt)
    return rows


def list_seeded_cities() -> list[str]:
    if not CITY_DATA_DIR.exists():
        return []
    return sorted(path.name for path in CITY_DATA_DIR.iterdir() if path.is_dir())


def list_schedule_cities() -> list[str]:
    return sorted({row["city_id"] for row in load_schedule_rows()})


def city_label(city_id: str) -> str:
    for row in load_schedule_rows():
        if row["city_id"] == city_id:
            return row["city_name"]
    return city_id.replace("-", " ").title()


def _build_match_config(row: dict[str, str]) -> dict[str, Any]:
    kickoff = _kickoff_dt(row)
    home_name = normalize_team_label(row["home_team_label"])
    away_name = normalize_team_label(row["away_team_label"])
    crowd_profile = _build_crowd_profile(home_name, away_name, kickoff)
    return {
        "match_id": row["match_id"],
        "title": f"{home_name} vs {away_name}",
        "stage": row["stage"],
        "city_id": row["city_id"],
        "city": row["city_name"],
        "venue": row["venue_name"],
        "venue_capacity": _venue_capacity(row["venue_name"]),
        "kickoff_local": kickoff.isoformat(),
        "home_team": _team_info(row["home_team_label"], row.get("home_team_color") or None),
        "away_team": _team_info(row["away_team_label"], row.get("away_team_color") or None),
        "day_offsets": [-1, 0, 1],
        "step_minutes": 15,
        "timeline": {"start_hour": 6, "end_hour": 26, "steps": 80},
        "crowd_profile": crowd_profile,
        "cultural_notes": {
            "team_a": _team_note(home_name),
            "team_b": _team_note(away_name),
            "neutral": "Neutral supporters spread across headline bars and fan zones, spending more on flexible premium experiences.",
            "locals": "Locals react strongly to evening kickoffs and headline teams, but are less present on weekday afternoon matches.",
        },
        "rng_seed": int(kickoff.strftime("%Y%m%d")),
        "source_url": row["source_url"],
        "special_venue_ids": ["stadium_zone", "fanzone_zone"],
    }


@lru_cache(maxsize=32)
def load_matches_registry(city_id: str | None = None) -> dict[str, Any]:
    selected_city_id = city_id or DEFAULT_CITY_ID
    matches = [_build_match_config(row) for row in load_schedule_rows() if row["city_id"] == selected_city_id]
    if not matches:
        raise ValueError(f"Unsupported city_id: {selected_city_id}")
    return {
        "city_id": selected_city_id,
        "matches": matches,
        "default_match_id": matches[0]["match_id"],
    }


@lru_cache(maxsize=16)
def _load_city_components(city_id: str) -> dict[str, Any]:
    city_dir = _city_dir(city_id)
    if not city_dir.exists():
        raise ValueError(f"City pack not found: {city_id}")

    base = load_json(city_dir / "base.json")
    businesses = load_json(city_dir / "businesses.json")["businesses"]
    special_venues = load_json(city_dir / "special_venues.json")["special_venues"]
    for venue in special_venues:
        venue.setdefault("kind", venue.get("entity_type", "poi"))
    edge_paths = load_json(city_dir / "edge_paths.json")

    for edge in base.get("edges", []):
        edge["path"] = edge_paths.get(edge["id"], edge.get("path"))

    if LIVE_ENRICHMENT_PATH.exists():
        enrichment = load_json(LIVE_ENRICHMENT_PATH)
        business_overrides = enrichment.get("business_overrides", {})
        for business in businesses:
            override = business_overrides.get(business["id"])
            if override:
                business.update(override)

    return {
        "city": base["city"],
        "nodes": base["nodes"],
        "edges": base["edges"],
        "zones": base["zones"],
        "businesses": businesses,
        "special_venues": special_venues,
        "provenance": base.get("provenance", {}),
    }


_seed_cache: dict[tuple[str, str], dict[str, Any]] = {}


def load_seed_bundle(city_id: str | None = None, match_id: str | None = None) -> dict[str, Any]:
    selected_city_id = city_id or DEFAULT_CITY_ID
    registry = load_matches_registry(selected_city_id)
    selected_match_id = match_id or registry["default_match_id"]
    cache_key = (selected_city_id, selected_match_id)
    if cache_key in _seed_cache:
        return _seed_cache[cache_key]

    city_base = _load_city_components(selected_city_id)
    match_entry = next((item for item in registry["matches"] if item["match_id"] == selected_match_id), None)
    if match_entry is None:
        raise ValueError(f"Unknown match_id for {selected_city_id}: {selected_match_id}")

    payload = copy.deepcopy(city_base)
    payload["match"] = match_entry
    payload["weather"] = _build_weather(datetime.fromisoformat(match_entry["kickoff_local"]))
    payload["fanzones"] = copy.deepcopy(payload["special_venues"])
    _seed_cache[cache_key] = payload
    return payload


def baseline_path_for(city_id: str, match_id: str) -> Path:
    return PROCESSED_DIR / city_id / f"baseline_{match_id}.json"
