from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx

from .config import RAW_DIR, settings
from .data_loader import LIVE_ENRICHMENT_PATH, dump_json, load_seed_bundle
from .service import MatchFlowService


async def fetch_open_meteo(seed_bundle: dict[str, Any]) -> dict[str, Any]:
    stadium = next(item for item in seed_bundle["fanzones"] if item["kind"] == "stadium")
    kickoff = date.fromisoformat(seed_bundle["match"]["kickoff_local"].split("T")[0])
    proxy_date = kickoff.replace(year=kickoff.year - 1)
    params = {
        "latitude": stadium["lat"],
        "longitude": stadium["lng"],
        "start_date": proxy_date.isoformat(),
        "end_date": proxy_date.isoformat(),
        "hourly": "temperature_2m",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get("https://archive-api.open-meteo.com/v1/archive", params=params)
        response.raise_for_status()
        data = response.json()

    hourly_temps = data.get("hourly", {}).get("temperature_2m", []) or [33]
    midday_temp = round(sum(hourly_temps[10:18]) / max(1, len(hourly_temps[10:18])), 1)
    return {
        "-1": {"temp_c": round(midday_temp - 2), "condition": "Open-Meteo historical proxy", "walking_modifier": 0.9},
        "0": {"temp_c": midday_temp, "condition": "Open-Meteo historical proxy", "walking_modifier": 0.84},
        "1": {"temp_c": round(midday_temp - 1), "condition": "Open-Meteo historical proxy", "walking_modifier": 0.88},
    }


async def fetch_google_places(seed_bundle: dict[str, Any]) -> dict[str, Any]:
    if not settings.google_maps_api_key:
        return {}

    overrides: dict[str, Any] = {}
    headers = {
        "X-Goog-Api-Key": settings.google_maps_api_key,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.priceLevel,places.location,places.regularOpeningHours",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        for business in seed_bundle["businesses"]:
            body = {
                "textQuery": f"{business['name']} Texas",
                "maxResultCount": 1,
                "locationBias": {
                    "circle": {
                        "center": {
                            "latitude": business["lat"],
                            "longitude": business["lng"],
                        },
                        "radius": 3500.0,
                    }
                },
            }
            response = await client.post("https://places.googleapis.com/v1/places:searchText", headers=headers, json=body)
            if not response.is_success:
                continue
            places = response.json().get("places", [])
            if not places:
                continue
            place = places[0]
            location = place.get("location", {})
            overrides[business["id"]] = {
                "rating": place.get("rating", business["rating"]),
                "price_level": _google_price_level(place.get("priceLevel"), business["price_level"]),
                "lat": location.get("latitude", business["lat"]),
                "lng": location.get("longitude", business["lng"]),
                "hours": _hours_summary(place.get("regularOpeningHours"), business["hours"]),
                "source": "google_places_live",
            }
    return overrides


def _hours_summary(payload: dict[str, Any] | None, fallback: str) -> str:
    if not payload:
        return fallback
    weekday = payload.get("weekdayDescriptions")
    if weekday:
        return weekday[0]
    return fallback


def _google_price_level(value: str | None, fallback: int) -> int:
    mapping = {
        "PRICE_LEVEL_FREE": 0,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4,
    }
    return mapping.get(value or "", fallback)


async def refresh() -> dict[str, Any]:
    seed_bundle = load_seed_bundle()
    weather_overrides = await fetch_open_meteo(seed_bundle)
    business_overrides = await fetch_google_places(seed_bundle)
    payload = {
        "generated_at": date.today().isoformat(),
        "weather_overrides": weather_overrides,
        "business_overrides": business_overrides,
    }
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dump_json(LIVE_ENRICHMENT_PATH, payload)
    service = MatchFlowService()
    artifacts = service.rebuild_baseline_artifacts()
    return {
        "live_enrichment_path": str(LIVE_ENRICHMENT_PATH),
        **artifacts,
        "weather_override_days": sorted(weather_overrides),
        "business_overrides": len(business_overrides),
    }


def main() -> None:
    result = asyncio.run(refresh())
    print(result)


if __name__ == "__main__":
    main()
