from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree

import httpx


NEGATIVE_NEWS_TERMS = {
    "injury",
    "injured",
    "suspension",
    "suspended",
    "doubt",
    "doubtful",
    "out",
    "ruled out",
    "controversy",
    "dispute",
    "conflict",
    "sacked",
    "scandal",
}

POSITIVE_NEWS_TERMS = {
    "returns",
    "fit",
    "available",
    "cleared",
    "boost",
    "recovered",
}

TEAM_NEWS_TTL = timedelta(minutes=25)
WEATHER_TTL = timedelta(minutes=40)

_TEAM_NEWS_CACHE: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}
_WEATHER_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}


def _fetch_team_news_items(team: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    cached = _TEAM_NEWS_CACHE.get(team)
    if cached and now - cached[0] <= TEAM_NEWS_TTL:
        return cached[1]

    query = quote_plus(f"{team} FIFA World Cup team news")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    items: list[dict[str, Any]] = []

    try:
        response = httpx.get(url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
    except Exception:  # noqa: BLE001
        _TEAM_NEWS_CACHE[team] = (now, items)
        return items

    for node in root.findall("./channel/item")[:8]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        pub_date = (node.findtext("pubDate") or "").strip()

        lower = title.lower()
        neg = sum(1 for term in NEGATIVE_NEWS_TERMS if term in lower)
        pos = sum(1 for term in POSITIVE_NEWS_TERMS if term in lower)
        items.append(
            {
                "team": team,
                "title": title,
                "link": link,
                "published": pub_date,
                "negative_hits": neg,
                "positive_hits": pos,
            }
        )

    _TEAM_NEWS_CACHE[team] = (now, items)
    return items


def fetch_team_news(team_names: list[str], lookback_days: int = 7) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    items: list[dict[str, Any]] = []
    neg_hits = 0
    pos_hits = 0

    for team in team_names:
        team_items = _fetch_team_news_items(team)
        items.extend(team_items)
        neg_hits += sum(int(item.get("negative_hits", 0)) for item in team_items)
        pos_hits += sum(int(item.get("positive_hits", 0)) for item in team_items)

    items.sort(key=lambda x: (x["negative_hits"], x["positive_hits"]), reverse=True)
    score = max(-1.0, min(1.0, (pos_hits - neg_hits) / max(1.0, (pos_hits + neg_hits))))

    # Optional freshness hint from RSS dates where parsing is available.
    fresh_count = 0
    for item in items[:25]:
        try:
            dt = datetime.strptime(item["published"], "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                fresh_count += 1
        except Exception:  # noqa: BLE001
            continue

    return {
        "sentiment_score": score,
        "fresh_count": fresh_count,
        "items": items[:25],
    }


def fetch_weather_context(lat: float | None, lon: float | None, kickoff: datetime) -> dict[str, Any]:
    if lat is None or lon is None:
        return {
            "available": False,
            "temperature_c": None,
            "precipitation_mm": None,
            "wind_kph": None,
            "impact": 0.0,
            "summary": "No venue coordinates available.",
        }

    kickoff_utc = kickoff.astimezone(timezone.utc)
    cache_key = f"{round(lat, 3)}:{round(lon, 3)}:{kickoff_utc.strftime('%Y-%m-%dT%H')}"
    now = datetime.now(timezone.utc)
    cached_weather = _WEATHER_CACHE.get(cache_key)
    if cached_weather and now - cached_weather[0] <= WEATHER_TTL:
        return cached_weather[1]

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,precipitation,wind_speed_10m"
        "&forecast_days=3&timezone=UTC"
    )

    try:
        data = httpx.get(url, timeout=10.0).json()
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        precs = hourly.get("precipitation", [])
        winds = hourly.get("wind_speed_10m", [])
        if not times:
            raise ValueError("No hourly weather rows")

        nearest_idx = min(
            range(len(times)),
            key=lambda idx: abs(datetime.fromisoformat(times[idx]).replace(tzinfo=timezone.utc) - kickoff_utc),
        )

        temperature = float(temps[nearest_idx]) if nearest_idx < len(temps) else None
        precipitation = float(precs[nearest_idx]) if nearest_idx < len(precs) else 0.0
        wind = float(winds[nearest_idx]) if nearest_idx < len(winds) else 0.0

        adverse = 0.0
        notes = []
        if precipitation and precipitation >= 2.0:
            adverse += 0.08
            notes.append("Rain expected, likely reducing passing efficiency.")
        if wind and wind >= 20:
            adverse += 0.05
            notes.append("High wind can disrupt long balls and crosses.")
        if temperature is not None and (temperature >= 32 or temperature <= 2):
            adverse += 0.04
            notes.append("Extreme temperature may reduce intensity.")

        result = {
            "available": True,
            "temperature_c": temperature,
            "precipitation_mm": precipitation,
            "wind_kph": wind,
            "impact": -adverse,
            "summary": " ".join(notes) if notes else "Weather impact expected to be mild.",
        }
        _WEATHER_CACHE[cache_key] = (now, result)
        return result
    except Exception:  # noqa: BLE001
        result = {
            "available": False,
            "temperature_c": None,
            "precipitation_mm": None,
            "wind_kph": None,
            "impact": 0.0,
            "summary": "Weather feed unavailable.",
        }
        _WEATHER_CACHE[cache_key] = (now, result)
        return result
