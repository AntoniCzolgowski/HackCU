from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import PROCESSED_DIR, REPORTS_DIR, settings
from .data_loader import (
    DEFAULT_CITY_ID,
    PROVENANCE_PATH,
    baseline_path_for,
    city_label,
    dump_json,
    list_schedule_cities,
    list_seeded_cities,
    load_json,
    load_matches_registry,
    load_seed_bundle,
)
from .recommendations import RecommendationService
from .reporting import build_business_report_pdf
from .simulator import DAY_LAYERS, SimulationEngine


@dataclass(slots=True)
class ReportJob:
    job_id: str
    status: str
    output_path: Path | None = None
    error: str | None = None
    business_id: str | None = None
    city_id: str | None = None
    match_id: str | None = None


class _MatchState:
    __slots__ = (
        "city_id",
        "match_id",
        "seed_bundle",
        "engine",
        "baseline",
        "scenarios",
        "business_detail_cache",
        "zone_detail_cache",
        "zones_by_id",
        "businesses_by_id",
        "businesses_by_zone",
        "special_venues_by_id",
    )

    def __init__(self, city_id: str, match_id: str, seed_bundle: dict[str, Any], engine: SimulationEngine, baseline: dict[str, Any]) -> None:
        self.city_id = city_id
        self.match_id = match_id
        self.seed_bundle = seed_bundle
        self.engine = engine
        self.baseline = baseline
        self.scenarios: dict[str, dict[str, Any]] = {"baseline": baseline}
        self.business_detail_cache: dict[tuple[str, int, str], dict[str, Any]] = {}
        self.zone_detail_cache: dict[tuple[str, int, str], dict[str, Any]] = {}
        self.zones_by_id = {zone["id"]: zone for zone in seed_bundle["zones"]}
        self.businesses_by_id = {business["id"]: business for business in seed_bundle["businesses"]}
        self.businesses_by_zone: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for business in seed_bundle["businesses"]:
            self.businesses_by_zone[business["zone_id"]].append(business)
        self.special_venues_by_id = {venue["id"]: venue for venue in seed_bundle.get("special_venues", [])}


class MatchFlowService:
    def __init__(self) -> None:
        self._default_city_id = DEFAULT_CITY_ID
        self._match_states: dict[tuple[str, str], _MatchState] = {}
        self.recommendations = RecommendationService()
        self._report_jobs: dict[str, ReportJob] = {}
        self._report_lock = threading.Lock()
        self._provenance = self._ensure_provenance()
        default_registry = load_matches_registry(self._default_city_id)
        self._default_match_id = default_registry["default_match_id"]
        self._ensure_match(self._default_city_id, self._default_match_id)

    def _resolve_city_id(self, city_id: str | None) -> str:
        return city_id or self._default_city_id

    def _resolve_match_id(self, city_id: str, match_id: str | None) -> str:
        registry = load_matches_registry(city_id)
        return match_id or registry["default_match_id"]

    def _ensure_match(self, city_id: str, match_id: str) -> _MatchState:
        key = (city_id, match_id)
        if key in self._match_states:
            return self._match_states[key]

        seed_bundle = load_seed_bundle(city_id=city_id, match_id=match_id)
        engine = SimulationEngine(seed_bundle)
        baseline_file = baseline_path_for(city_id, match_id)
        if baseline_file.exists():
            baseline = load_json(baseline_file)
        else:
            baseline = engine.generate_scenario(scenario_id="baseline")
            dump_json(baseline_file, baseline)
        state = _MatchState(city_id, match_id, seed_bundle, engine, baseline)
        self._match_states[key] = state
        return state

    def _ms(self, city_id: str | None = None, match_id: str | None = None) -> _MatchState:
        resolved_city_id = self._resolve_city_id(city_id)
        resolved_match_id = self._resolve_match_id(resolved_city_id, match_id)
        return self._ensure_match(resolved_city_id, resolved_match_id)

    def _ensure_provenance(self) -> dict[str, Any]:
        if PROVENANCE_PATH.exists():
            return load_json(PROVENANCE_PATH)

        default_state = self._ensure_match(self._default_city_id, load_matches_registry(self._default_city_id)["default_match_id"])
        provenance = default_state.engine.build_provenance_report(default_state.baseline)
        provenance["supported_cities"] = list_schedule_cities()
        provenance["schedule_source"] = "https://www.roadtrips.com/world-cup/2026-world-cup-packages/schedule/"
        dump_json(PROVENANCE_PATH, provenance)
        return provenance

    def get_matches(self, *, city_id: str | None = None) -> dict[str, Any]:
        resolved_city_id = self._resolve_city_id(city_id)
        registry = load_matches_registry(resolved_city_id)
        seeded_cities = set(list_seeded_cities())
        return {
            "city_id": resolved_city_id,
            "available_cities": [
                {
                    "city_id": city,
                    "label": city_label(city),
                    "simulation_ready": city in seeded_cities,
                }
                for city in list_schedule_cities()
            ],
            "matches": [
                {
                    "match_id": match["match_id"],
                    "title": match["title"],
                    "stage": match["stage"],
                    "home_team": match["home_team"],
                    "away_team": match["away_team"],
                    "kickoff_local": match["kickoff_local"],
                    "venue": match["venue"],
                    "venue_capacity": match["venue_capacity"],
                }
                for match in registry["matches"]
            ],
            "default_match_id": registry["default_match_id"],
        }

    def get_meta(self, *, city_id: str | None = None, match_id: str | None = None) -> dict[str, Any]:
        ms = self._ms(city_id, match_id)
        special_venues = list(ms.special_venues_by_id.values())
        return {
            "app": {
                "name": "MatchFlow World Cup Intelligence",
                "scenario_ids": sorted(ms.scenarios),
                "city_id": ms.city_id,
            },
            "match": ms.seed_bundle["match"],
            "timeline": {
                "step_minutes": ms.engine.step_minutes,
                "steps_per_day": ms.engine.steps_per_day,
                "time_labels": ms.engine.time_labels,
                "days": ms.engine.day_offsets,
                "match_markers": ms.baseline["days"]["0"]["match_markers"],
            },
            "zones": [
                {
                    **zone,
                    "capacity": ms.engine.zone_capacity[zone["id"]],
                    "node": ms.engine.nodes[zone["node_id"]],
                }
                for zone in ms.seed_bundle["zones"]
            ],
            "edges": [
                {
                    **edge,
                    "path": self._edge_path(ms, edge),
                }
                for edge in ms.seed_bundle["edges"]
            ],
            "businesses": ms.seed_bundle["businesses"],
            "special_venues": special_venues,
            "pois": special_venues,
            "weather": ms.seed_bundle["weather"],
            "map_config": {
                "provider": "google_maps_js" if settings.google_maps_api_key else "none",
                "google_maps_api_key": settings.google_maps_api_key or None,
                "default_map_type": "roadmap",
                "available_map_types": ["roadmap", "terrain", "hybrid"],
                "initial_center": ms.seed_bundle["city"]["default_map_center"],
                "initial_zoom": ms.seed_bundle["city"]["default_map_zoom"],
            },
            "available_layers": list(DAY_LAYERS),
            "source_availability": {
                "google_places": bool(settings.google_maps_api_key),
                "anthropic": bool(settings.anthropic_api_key),
                "baseline_seed": True,
            },
        }

    def get_snapshot(
        self,
        *,
        day: int,
        step: int,
        scenario_id: str,
        layer: str,
        city_id: str | None = None,
        match_id: str | None = None,
    ) -> dict[str, Any]:
        ms = self._ms(city_id, match_id)
        scenario = ms.scenarios.get(scenario_id, ms.baseline)
        day_data = scenario["days"][str(day)]
        safe_step = max(0, min(ms.engine.steps_per_day - 1, step))
        safe_layer = layer if layer in DAY_LAYERS else "total"

        zone_snapshot = []
        for zone in ms.seed_bundle["zones"]:
            value = day_data["zones"][safe_layer][zone["id"]][safe_step]
            capacity = ms.engine.zone_capacity[zone["id"]]
            zone_snapshot.append(
                {
                    "zone_id": zone["id"],
                    "name": zone["name"],
                    "kind": zone["kind"],
                    "center": zone["center"],
                    "value": value,
                    "capacity": capacity,
                    "utilization": round(value / capacity, 3),
                    "focus_color": zone["focus_color"],
                }
            )

        edge_snapshot = []
        for edge in ms.seed_bundle["edges"]:
            load = day_data["edges"][safe_layer][edge["id"]][safe_step]
            edge_snapshot.append(
                {
                    "edge_id": edge["id"],
                    "road_name": edge["road_name"],
                    "kind": edge["kind"],
                    "load": load,
                    "capacity": edge["capacity"],
                    "congestion": round(load / edge["capacity"], 3),
                }
            )

        business_overlay = []
        for business in ms.seed_bundle["businesses"]:
            business_overlay.append(
                {
                    "business_id": business["id"],
                    "name": business["name"],
                    "type": business["type"],
                    "zone_id": business["zone_id"],
                    "value": day_data["businesses"][safe_layer][business["id"]][safe_step],
                    "rating": business["rating"],
                    "google_rating": business["rating"],
                    "capacity_estimate": business["capacity_estimate"],
                }
            )

        special_overlay = []
        for venue in ms.seed_bundle.get("special_venues", []):
            zone_id = venue["zone_id"]
            value = day_data["zones"][safe_layer][zone_id][safe_step]
            comfort_capacity = venue.get("comfort_capacity", ms.engine.zone_capacity[zone_id])
            special_overlay.append(
                {
                    "entity_id": venue["id"],
                    "entity_type": venue["entity_type"],
                    "zone_id": zone_id,
                    "name": venue["name"],
                    "value": value,
                    "comfort_capacity": comfort_capacity,
                    "crowd_pressure": round(value / comfort_capacity, 3),
                    "lat": venue["lat"],
                    "lng": venue["lng"],
                }
            )

        zone_snapshot.sort(key=lambda item: item["value"], reverse=True)
        edge_snapshot.sort(key=lambda item: item["congestion"], reverse=True)
        business_overlay.sort(key=lambda item: item["value"], reverse=True)
        special_overlay.sort(key=lambda item: item["value"], reverse=True)

        return {
            "scenario_id": scenario["scenario_id"],
            "day": day,
            "step": safe_step,
            "time_label": ms.engine.time_labels[safe_step],
            "layer": safe_layer,
            "zones": zone_snapshot,
            "edges": edge_snapshot,
            "business_overlay": business_overlay,
            "special_overlay": special_overlay,
            "summary": {
                "city_total": sum(item["value"] for item in zone_snapshot),
                "active_travelers": day_data["moving"][safe_layer][safe_step],
                "busiest_zone": zone_snapshot[0],
                "busiest_business": business_overlay[0],
                "busiest_special_venue": special_overlay[0] if special_overlay else None,
                "most_congested_edge": edge_snapshot[0],
                "weather": day_data["weather"],
                "watch_items": [
                    {
                        "label": "Top live district",
                        "value": zone_snapshot[0]["name"],
                        "detail": f"{round(zone_snapshot[0]['utilization'] * 100)}% district utilization",
                    },
                    {
                        "label": "Business to watch",
                        "value": business_overlay[0]["name"],
                        "detail": f"{business_overlay[0]['value']} active visitors now",
                    },
                    {
                        "label": "Special venue wave",
                        "value": special_overlay[0]["name"] if special_overlay else "N/A",
                        "detail": f"{special_overlay[0]['value']} active people now" if special_overlay else "No special venue data",
                    },
                ],
            },
        }

    def _edge_lookup(self, ms: _MatchState, edge_id: str) -> dict[str, Any]:
        return next(edge for edge in ms.seed_bundle["edges"] if edge["id"] == edge_id)

    def _edge_path(self, ms: _MatchState, edge: dict[str, Any]) -> list[list[float]]:
        if edge.get("path"):
            return edge["path"]
        return [
            [ms.engine.nodes[edge["source"]]["lng"], ms.engine.nodes[edge["source"]]["lat"]],
            [ms.engine.nodes[edge["target"]]["lng"], ms.engine.nodes[edge["target"]]["lat"]],
        ]

    def _series_to_payload(self, ms: _MatchState, series: list[int]) -> list[dict[str, Any]]:
        return [{"step": index, "label": ms.engine.time_labels[index], "value": value} for index, value in enumerate(series)]

    def _series_with_markers(
        self,
        ms: _MatchState,
        series: list[int],
        markers: dict[str, Any],
        peak_step: int,
        *,
        day: int,
    ) -> list[dict[str, Any]]:
        marker_lookup = {peak_step: "peak"}
        if day == 0:
            marker_lookup.update(
                {
                    markers["kickoff_step"]: "kickoff",
                    markers["halftime_step"]: "halftime",
                    max(0, markers["final_whistle_step"] - 1): "final_whistle",
                }
            )
        return [
            {
                "step": index,
                "label": ms.engine.time_labels[index],
                "value": value,
                "marker": marker_lookup.get(index),
            }
            for index, value in enumerate(series)
        ]

    def _estimate_served_revenue(self, ms: _MatchState, business: dict[str, Any], day_summary: dict[str, Any]) -> dict[str, Any]:
        avg_spend_map = ms.seed_bundle["match"]["crowd_profile"]["avg_spend_per_visitor"]
        mix = day_summary["nationality_mix"]
        weighted_spend = sum((mix.get(segment, 0) / 100.0) * avg_spend_map.get(segment, 35.0) for segment in avg_spend_map)
        capture_rate = {
            "restaurant": 0.95,
            "sports_bar": 0.92,
            "cocktail_bar": 0.88,
            "hotel_bar": 0.84,
            "hotel": 0.75,
        }.get(business["type"], 0.86)
        total = round(day_summary["served_visits_today"] * weighted_spend * capture_rate)
        return {
            "total": total,
            "avg_spend": round(weighted_spend, 2),
            "service_capture_rate": capture_rate,
            "served_visits_today": day_summary["served_visits_today"],
        }

    def _build_day_comparison(self, ms: _MatchState, scenario: dict[str, Any], business_id: str) -> list[dict[str, Any]]:
        labels = {-1: "Day Before", 0: "Match Day", 1: "Day After"}
        comparison = []
        for day in ms.engine.day_offsets:
            summary = scenario["days"][str(day)]["business_day_summary"].get(business_id)
            comparison.append(
                {
                    "day": day,
                    "label": labels.get(day, f"Day {day}"),
                    "served_visits_today": summary["served_visits_today"] if summary else 0,
                    "peak_active_visitors": summary["peak_active_visitors"] if summary else 0,
                    "peak_label": summary["peak_label"] if summary else "",
                }
            )
        return comparison

    def _build_zone_context(self, ms: _MatchState, *, day_data: dict[str, Any], business: dict[str, Any], business_id: str) -> dict[str, Any]:
        zone_businesses = ms.businesses_by_zone[business["zone_id"]]
        ranked = sorted(
            zone_businesses,
            key=lambda item: day_data["business_day_summary"][item["id"]]["served_visits_today"],
            reverse=True,
        )
        zone_total = sum(day_data["business_day_summary"][item["id"]]["served_visits_today"] for item in zone_businesses) or 1
        business_total = day_data["business_day_summary"][business_id]["served_visits_today"]
        venue_rank = next(index for index, item in enumerate(ranked, start=1) if item["id"] == business_id)
        return {
            "zone_id": business["zone_id"],
            "zone_name": ms.zones_by_id[business["zone_id"]]["name"],
            "zone_kind": ms.zones_by_id[business["zone_id"]]["kind"],
            "venues_in_zone": len(zone_businesses),
            "venue_rank": venue_rank,
            "zone_total_served_visits": zone_total,
            "share_of_zone_demand": round((business_total / zone_total) * 100, 1),
        }

    def _peer_benchmark(self, ms: _MatchState, *, day_data: dict[str, Any], business: dict[str, Any], business_id: str) -> list[dict[str, Any]]:
        peers = [item for item in ms.businesses_by_zone[business["zone_id"]] if item["id"] != business_id and item["type"] != "hotel"]
        peers.sort(key=lambda item: day_data["business_day_summary"][item["id"]]["served_visits_today"], reverse=True)
        payload = []
        for peer in peers[:6]:
            summary = day_data["business_day_summary"][peer["id"]]
            payload.append(
                {
                    "business_id": peer["id"],
                    "name": peer["name"],
                    "type": peer["type"],
                    "served_visits_today": summary["served_visits_today"],
                    "peak_label": summary["peak_label"],
                    "google_rating": peer["rating"],
                }
            )
        return payload

    def _pressure_profile(self, peak_capacity_pct_capped: float) -> tuple[str, str]:
        if peak_capacity_pct_capped >= 120:
            return "Severe", "danger"
        if peak_capacity_pct_capped >= 95:
            return "High", "warning"
        if peak_capacity_pct_capped >= 70:
            return "Elevated", "accent"
        return "Stable", "ok"

    def _peak_window_label(self, ms: _MatchState, peak_step: int) -> str:
        start_step = max(0, peak_step - 2)
        end_step = min(ms.engine.steps_per_day - 1, peak_step + 2)
        return f"{ms.engine.time_labels[start_step]}-{ms.engine.time_labels[end_step]}"

    def _build_business_playbook(self, ms: _MatchState, *, business: dict[str, Any], day_summary: dict[str, Any], zone_context: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
        peak_pct = day_summary["peak_capacity_pct_capped"]
        pressure_level, tone = self._pressure_profile(peak_pct)
        peak_step = day_summary["peak_step"]
        dominant_segment, dominant_share = max(day_summary["nationality_mix"].items(), key=lambda item: item[1])
        segment_label = {
            "team_a": ms.seed_bundle["match"]["home_team"]["name"],
            "team_b": ms.seed_bundle["match"]["away_team"]["name"],
            "neutral": "Neutral fans",
            "locals": "Locals",
        }.get(dominant_segment, dominant_segment.title())
        peak_window = self._peak_window_label(ms, peak_step)
        estimated_turns = round(day_summary["served_visits_today"] / max(1, business["capacity_estimate"]), 2)
        action_options = [
            {
                "title": "Staffing",
                "priority": "urgent" if peak_pct >= 115 else "recommended",
                "timing": "24h before",
                "detail": "Stage one dedicated queue manager and a fast-order service lane before the pre-match rush.",
            },
            {
                "title": "Inventory",
                "priority": "urgent",
                "timing": "24h before",
                "detail": f"Bias beer, water, and top sellers toward {segment_label} fan preferences and protect cold storage for the late wave.",
            },
            {
                "title": "Service flow",
                "priority": "recommended",
                "timing": "2h before peak",
                "detail": "Protect one fast-turn counter for drinks-only orders so table service does not stall at kickoff and full time.",
            },
            {
                "title": "Activation",
                "priority": "optional",
                "timing": "During peak",
                "detail": f"Push a short-lived {segment_label}-leaning watch-party bundle with bilingual signage near the main entrance.",
            },
        ]
        watchouts = []
        if peak_pct >= 120:
            watchouts.append("Demand is projected beyond practical comfort capacity; expect queues and spillover unless service is simplified.")
        if weather["temp_c"] >= 34:
            watchouts.append("Heat will lower patience for outdoor waiting; shade, water, and line visibility matter more than menu breadth.")
        if day_summary["spillover_total"] > 0:
            watchouts.append(f"{day_summary['spillover_total']} visitors were redirected by the model after the venue hit its operational cap.")
        return {
            "pressure_level": pressure_level,
            "tone": tone,
            "peak_window": peak_window,
            "estimated_turns": estimated_turns,
            "dominant_segment": dominant_segment,
            "dominant_label": segment_label,
            "dominant_share": round(dominant_share, 1),
            "spend_profile": "premium social spend" if business["price_level"] >= 3 else "high-volume watch-party spend",
            "action_options": action_options,
            "watchouts": watchouts,
        }

    def _build_business_metric_explanations(
        self,
        ms: _MatchState,
        business: dict[str, Any],
        day_summary: dict[str, Any],
        revenue: dict[str, Any],
        zone_context: dict[str, Any],
    ) -> dict[str, Any]:
        pressure_level, _ = self._pressure_profile(day_summary["peak_capacity_pct_capped"])
        return {
            "pressure": {
                "title": "Pressure",
                "definition": "A plain-English operating stress level derived from the venue's capped peak utilization.",
                "formula": "pressure = label(peak_capacity_pct_capped)",
                "inputs": {"peak_capacity_pct_capped": day_summary["peak_capacity_pct_capped"]},
                "notes": [f"Current label: {pressure_level}"],
            },
            "served_revenue": {
                "title": "Estimated revenue",
                "definition": "Modeled revenue from served visits, not dwell-summed occupancy.",
                "formula": "served_visits_today x weighted_avg_spend x service_capture_rate",
                "inputs": revenue,
                "notes": ["Uses the match fan-mix spend map and venue-type capture rate."],
            },
            "peak_capacity": {
                "title": "Peak capacity",
                "definition": "Highest active visitors point in the day divided by venue capacity, capped at 150% for display.",
                "formula": "min(150, peak_active_visitors / capacity_estimate x 100)",
                "inputs": {
                    "peak_active_visitors": day_summary["peak_active_visitors"],
                    "capacity_estimate": business["capacity_estimate"],
                    "peak_capacity_pct_capped": day_summary["peak_capacity_pct_capped"],
                },
                "notes": ["Operational display is capped at 150% so impossible values are not shown."],
            },
            "zone_share": {
                "title": "Zone share",
                "definition": "Share of served visits captured by this venue versus all tracked business venues in the same zone.",
                "formula": "served_visits_today / zone_total_served_visits x 100",
                "inputs": {
                    "served_visits_today": day_summary["served_visits_today"],
                    "zone_total_served_visits": zone_context["zone_total_served_visits"],
                },
                "notes": [f"Ranked #{zone_context['venue_rank']} in {zone_context['zone_name']}."],
            },
            "active_visitors": {
                "title": "Active visitors over time",
                "definition": "Canonical 15-minute active-visitor series used by the map, chart, and capacity metrics.",
                "formula": "active_visitors_15m[t] = capped visitors present in the venue during timestep t",
                "inputs": {
                    "peak_step": day_summary["peak_step"],
                    "peak_active_visitors": day_summary["peak_active_visitors"],
                },
                "notes": ["This is the one venue-demand metric used throughout the product."],
            },
        }

    def _build_zone_metric_explanations(self, venue: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "active_people": {
                "title": "Active people",
                "definition": "People currently present in the special venue zone at each 15-minute timestep.",
                "formula": "active_people_15m[t] = zone occupancy at timestep t",
                "inputs": {"peak_active_people": summary["peak_active_people"], "peak_label": summary["peak_label"]},
                "notes": [f"Zone type: {venue['entity_type']}"],
            },
            "arrivals": {
                "title": "Arrivals",
                "definition": "Positive changes in active people from one timestep to the next.",
                "formula": "max(0, active[t] - active[t-1])",
                "inputs": {"cumulative_entries": summary["cumulative_entries"]},
                "notes": [],
            },
            "departures": {
                "title": "Departures",
                "definition": "Negative changes in active people from one timestep to the next.",
                "formula": "max(0, active[t-1] - active[t])",
                "inputs": {"cumulative_exits": summary["cumulative_exits"]},
                "notes": [],
            },
        }

    def _top_corridors_for_zone(self, ms: _MatchState, day_data: dict[str, Any], zone_id: str) -> list[dict[str, Any]]:
        zone_node = ms.zones_by_id[zone_id]["node_id"]
        corridors = []
        for edge in ms.seed_bundle["edges"]:
            if edge["source"] != zone_node and edge["target"] != zone_node:
                continue
            series = day_data["edges"]["total"][edge["id"]]
            peak_load = max(series)
            peak_step = series.index(peak_load) if peak_load else 0
            corridors.append(
                {
                    "edge_id": edge["id"],
                    "road_name": edge["road_name"],
                    "peak_load": peak_load,
                    "peak_label": ms.engine.time_labels[peak_step],
                }
            )
        corridors.sort(key=lambda item: item["peak_load"], reverse=True)
        return corridors[:3]

    async def get_business_detail(
        self,
        *,
        business_id: str,
        day: int,
        scenario_id: str,
        city_id: str | None = None,
        match_id: str | None = None,
    ) -> dict[str, Any]:
        ms = self._ms(city_id, match_id)
        cache_key = (business_id, day, scenario_id)
        if cache_key in ms.business_detail_cache:
            return ms.business_detail_cache[cache_key]

        business = ms.businesses_by_id.get(business_id)
        if business is None:
            raise KeyError(business_id)

        scenario = ms.scenarios.get(scenario_id, ms.baseline)
        day_data = scenario["days"][str(day)]
        day_summary = day_data["business_day_summary"][business_id]
        revenue = self._estimate_served_revenue(ms, business, day_summary)
        zone_context = self._build_zone_context(ms, day_data=day_data, business=business, business_id=business_id)
        playbook = self._build_business_playbook(ms, business=business, day_summary=day_summary, zone_context=zone_context, weather=day_data["weather"])
        recommendation = await self.recommendations.generate(
            business=business,
            day_summary=day_summary,
            match=ms.seed_bundle["match"],
            weather=day_data["weather"],
        )
        payload = {
            "entity_type": "business",
            "business": business,
            "day": day,
            "scenario_id": scenario["scenario_id"],
            "active_visitors_series_15m": self._series_with_markers(
                ms,
                day_summary["active_visitors_series_15m"],
                day_data["match_markers"],
                day_summary["peak_step"],
                day=day,
            ),
            "peak": {
                "step": day_summary["peak_step"],
                "label": day_summary["peak_label"],
                "active_visitors": day_summary["peak_active_visitors"],
            },
            "peak_active_visitors": day_summary["peak_active_visitors"],
            "peak_capacity_pct_capped": day_summary["peak_capacity_pct_capped"],
            "served_visits_today": day_summary["served_visits_today"],
            "served_revenue": revenue,
            "google_rating": {"value": business["rating"], "source": business["source"]},
            "nationality_mix": day_summary["nationality_mix"],
            "day_comparison": self._build_day_comparison(ms, scenario, business_id),
            "zone_context": zone_context,
            "audience_profile": {
                "dominant_segment": playbook["dominant_segment"],
                "dominant_label": playbook["dominant_label"],
                "dominant_share": playbook["dominant_share"],
                "spend_profile": playbook["spend_profile"],
            },
            "playbook": playbook,
            "peer_benchmark": self._peer_benchmark(ms, day_data=day_data, business=business, business_id=business_id),
            "insight_cards": [
                {"label": "Pressure", "value": playbook["pressure_level"], "detail": f"Peak window {playbook['peak_window']}", "tone": playbook["tone"], "metric_key": "pressure"},
                {"label": "Est. Revenue", "value": f"${revenue['total']:,.0f}", "detail": f"{revenue['served_visits_today']} served visits x ${revenue['avg_spend']:.0f} avg", "tone": "accent" if revenue["total"] > 15000 else "ok", "metric_key": "served_revenue"},
                {"label": "Peak Capacity", "value": f"{round(day_summary['peak_capacity_pct_capped'])}%", "detail": f"{day_summary['peak_active_visitors']} active visitors vs {business['capacity_estimate']} capacity", "tone": "danger" if day_summary["peak_capacity_pct_capped"] >= 120 else ("warning" if day_summary["peak_capacity_pct_capped"] >= 85 else "ok"), "metric_key": "peak_capacity"},
                {"label": "Zone share", "value": f"{zone_context['share_of_zone_demand']}%", "detail": f"Rank #{zone_context['venue_rank']} of {zone_context['venues_in_zone']} nearby venues", "tone": "ok", "metric_key": "zone_share"},
            ],
            "metric_explanations": self._build_business_metric_explanations(ms, business, day_summary, revenue, zone_context),
            "recommendation": recommendation,
            "visible_sections": {
                "demand": True,
                "capacity": True,
                "revenue": True,
                "audience": True,
                "recommendations": True,
                "competition": True,
                "report_sections": True,
            },
            "provenance": {
                "business_source": business["source"],
                "forecast_source": "simulated_active_visitors",
                "recommendation_source": recommendation["source"],
            },
            "report_support": {"can_generate_pdf": True},
        }
        ms.business_detail_cache[cache_key] = payload
        return payload

    def get_business_match_comparison(self, *, business_id: str, city_id: str | None = None) -> dict[str, Any]:
        resolved_city_id = self._resolve_city_id(city_id)
        registry = load_matches_registry(resolved_city_id)
        comparisons = []
        for match in registry["matches"]:
            ms = self._ensure_match(resolved_city_id, match["match_id"])
            if business_id not in ms.businesses_by_id:
                continue
            day_summary = ms.baseline["days"]["0"]["business_day_summary"].get(business_id)
            if not day_summary:
                continue
            revenue = self._estimate_served_revenue(ms, ms.businesses_by_id[business_id], day_summary)
            dominant_segment = max(day_summary["nationality_mix"].items(), key=lambda item: item[1])
            comparisons.append(
                {
                    "match_id": match["match_id"],
                    "title": match["title"],
                    "stage": match["stage"],
                    "home_team": match["home_team"],
                    "away_team": match["away_team"],
                    "kickoff_local": match["kickoff_local"],
                    "served_visits_today": day_summary["served_visits_today"],
                    "peak_active_visitors": day_summary["peak_active_visitors"],
                    "peak_label": day_summary["peak_label"],
                    "revenue_estimate": revenue["total"],
                    "dominant_nationality": dominant_segment[0],
                    "dominant_share": round(dominant_segment[1], 1),
                }
            )
        comparisons.sort(key=lambda item: item["revenue_estimate"], reverse=True)
        return {"business_id": business_id, "city_id": resolved_city_id, "comparisons": comparisons}

    def get_zone_detail(
        self,
        *,
        zone_id: str,
        day: int,
        scenario_id: str,
        city_id: str | None = None,
        match_id: str | None = None,
    ) -> dict[str, Any]:
        ms = self._ms(city_id, match_id)
        cache_key = (zone_id, day, scenario_id)
        if cache_key in ms.zone_detail_cache:
            return ms.zone_detail_cache[cache_key]
        if zone_id not in {"stadium_zone", "fanzone_zone"}:
            raise KeyError(zone_id)
        scenario = ms.scenarios.get(scenario_id, ms.baseline)
        day_data = scenario["days"][str(day)]
        summary = day_data["zone_day_summary"][zone_id]
        venue = ms.special_venues_by_id[zone_id]
        payload = {
            "entity_type": venue["entity_type"],
            "zone_id": zone_id,
            "venue": venue,
            "day": day,
            "scenario_id": scenario["scenario_id"],
            "active_people_series_15m": self._series_with_markers(
                ms,
                summary["active_people_series_15m"],
                day_data["match_markers"],
                summary["peak_step"],
                day=day,
            ),
            "peak_active_people": summary["peak_active_people"],
            "peak": {"step": summary["peak_step"], "label": summary["peak_label"], "active_people": summary["peak_active_people"]},
            "arrivals_series_15m": self._series_to_payload(ms, summary["arrivals_series_15m"]),
            "departures_series_15m": self._series_to_payload(ms, summary["departures_series_15m"]),
            "cumulative_entries": summary["cumulative_entries"],
            "cumulative_exits": summary["cumulative_exits"],
            "audience_mix": summary["audience_mix"],
            "wave_summary": summary["wave_summary"],
            "top_inbound_corridors": self._top_corridors_for_zone(ms, day_data, zone_id),
            "metric_explanations": self._build_zone_metric_explanations(venue, summary),
        }
        ms.zone_detail_cache[cache_key] = payload
        return payload

    async def create_business_report_job(
        self,
        *,
        business_id: str,
        day: int,
        scenario_id: str,
        visible_sections: dict[str, bool] | None,
        city_id: str | None = None,
        match_id: str | None = None,
    ) -> dict[str, Any]:
        ms = self._ms(city_id, match_id)
        detail = await self.get_business_detail(
            business_id=business_id,
            day=day,
            scenario_id=scenario_id,
            city_id=ms.city_id,
            match_id=ms.match_id,
        )
        comparison = self.get_business_match_comparison(business_id=business_id, city_id=ms.city_id)
        job_id = f"report-{uuid4().hex[:10]}"
        output_path = REPORTS_DIR / ms.city_id / f"{job_id}.pdf"
        job = ReportJob(job_id=job_id, status="queued", output_path=output_path, business_id=business_id, city_id=ms.city_id, match_id=ms.match_id)
        with self._report_lock:
            self._report_jobs[job_id] = job
        worker = threading.Thread(
            target=self._run_report_job,
            kwargs={
                "job_id": job_id,
                "match": ms.seed_bundle["match"],
                "detail": detail,
                "comparison": comparison,
                "visible_sections": visible_sections or detail["visible_sections"],
                "output_path": output_path,
            },
            daemon=True,
        )
        worker.start()
        return {"job_id": job_id, "status": job.status}

    def get_report_job(self, job_id: str) -> dict[str, Any]:
        job = self._report_jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return {
            "job_id": job.job_id,
            "status": job.status,
            "error": job.error,
            "download_url": f"/api/reports/{job_id}/download" if job.status == "completed" else None,
        }

    def get_report_path(self, job_id: str) -> Path:
        job = self._report_jobs.get(job_id)
        if job is None or job.output_path is None or not job.output_path.exists():
            raise KeyError(job_id)
        return job.output_path

    def create_what_if(
        self,
        *,
        day: int,
        step: int,
        blocked_edge_ids: list[str],
        duration_steps: int | None,
        city_id: str | None = None,
        match_id: str | None = None,
    ) -> dict[str, Any]:
        ms = self._ms(city_id, match_id)
        blocked = set(blocked_edge_ids)
        scenario_id = ms.engine.scenario_hash(day=day, step=step, blocked_edge_ids=blocked, duration_steps=duration_steps)
        if scenario_id not in ms.scenarios:
            ms.scenarios[scenario_id] = ms.engine.generate_scenario(
                scenario_id=scenario_id,
                blocked_edge_ids=blocked,
                activation_day=day,
                activation_step=step,
                duration_steps=duration_steps,
            )
        baseline_snapshot = self.get_snapshot(day=day, step=min(ms.engine.steps_per_day - 1, step + 2), scenario_id="baseline", layer="total", city_id=ms.city_id, match_id=ms.match_id)
        scenario_snapshot = self.get_snapshot(day=day, step=min(ms.engine.steps_per_day - 1, step + 2), scenario_id=scenario_id, layer="total", city_id=ms.city_id, match_id=ms.match_id)
        baseline_edge_map = {item["edge_id"]: item for item in baseline_snapshot["edges"]}
        scenario_edge_map = {item["edge_id"]: item for item in scenario_snapshot["edges"]}
        edge_deltas = []
        for edge_id, edge in scenario_edge_map.items():
            edge_deltas.append({"edge_id": edge_id, "road_name": edge["road_name"], "delta_congestion": round(edge["congestion"] - baseline_edge_map[edge_id]["congestion"], 3)})
        edge_deltas.sort(key=lambda item: item["delta_congestion"], reverse=True)
        return {
            "scenario_id": scenario_id,
            "blocked_edge_ids": sorted(blocked),
            "impact_summary": {
                "blocked_edges": [self._edge_lookup(ms, edge_id) for edge_id in blocked],
                "top_spillovers": edge_deltas[:3],
                "busiest_zone_after_reroute": scenario_snapshot["summary"]["busiest_zone"],
                "busiest_business_after_reroute": scenario_snapshot["summary"]["busiest_business"],
            },
        }

    def get_signal_plan(
        self,
        *,
        day: int,
        step: int,
        scenario_id: str,
        city_id: str | None = None,
        match_id: str | None = None,
    ) -> dict[str, Any]:
        ms = self._ms(city_id, match_id)
        snapshot = self.get_snapshot(day=day, step=step, scenario_id=scenario_id, layer="total", city_id=ms.city_id, match_id=ms.match_id)
        node_scores: dict[str, dict[str, Any]] = defaultdict(lambda: {"score": 0.0, "edge": None})
        for edge in snapshot["edges"]:
            edge_meta = self._edge_lookup(ms, edge["edge_id"])
            for node_id in (edge_meta["source"], edge_meta["target"]):
                node_scores[node_id]["score"] += edge["congestion"]
                if node_scores[node_id]["edge"] is None or edge["congestion"] > node_scores[node_id]["edge"]["congestion"]:
                    node_scores[node_id]["edge"] = edge
        ranked = sorted(node_scores.items(), key=lambda item: item[1]["score"], reverse=True)[:5]
        recommendations = []
        for node_id, payload in ranked:
            node = ms.engine.nodes[node_id]
            dominant_edge = payload["edge"]
            recommendations.append(
                {
                    "intersection_id": node_id,
                    "label": node["label"],
                    "lat": node["lat"],
                    "lng": node["lng"],
                    "score": round(payload["score"], 3),
                    "focus_road": dominant_edge["road_name"],
                    "recommended_green_extension_sec": min(45, max(10, round(dominant_edge["congestion"] * 28))),
                    "direction_bias": "outbound" if "stadium" in dominant_edge["edge_id"] else "throughput",
                }
            )
        return {"scenario_id": scenario_id, "day": day, "step": step, "recommendations": recommendations}

    def get_provenance(self) -> dict[str, Any]:
        return self._provenance

    def rebuild_baseline_artifacts(self) -> dict[str, Any]:
        generated: list[str] = []
        for city_id in list_seeded_cities():
            registry = load_matches_registry(city_id)
            for match in registry["matches"]:
                state = self._ensure_match(city_id, match["match_id"])
                baseline = state.engine.generate_scenario(scenario_id="baseline")
                output_path = baseline_path_for(city_id, match["match_id"])
                dump_json(output_path, baseline)
                state.baseline = baseline
                state.scenarios["baseline"] = baseline
                generated.append(str(output_path))
                if city_id == self._default_city_id and match["match_id"] == registry["default_match_id"]:
                    self._provenance = state.engine.build_provenance_report(baseline)
                    self._provenance["supported_cities"] = list_schedule_cities()
                    self._provenance["schedule_source"] = "https://www.roadtrips.com/world-cup/2026-world-cup-packages/schedule/"
                    dump_json(PROVENANCE_PATH, self._provenance)
        return {"generated_files": generated, "provenance_path": str(PROVENANCE_PATH)}

    def _run_report_job(
        self,
        *,
        job_id: str,
        match: dict[str, Any],
        detail: dict[str, Any],
        comparison: dict[str, Any],
        visible_sections: dict[str, bool],
        output_path: Path,
    ) -> None:
        job = self._report_jobs[job_id]
        job.status = "running"
        try:
            build_business_report_pdf(match=match, detail=detail, comparison=comparison, visible_sections=visible_sections, output_path=output_path)
            job.status = "completed"
        except Exception as exc:  # pragma: no cover
            job.status = "failed"
            job.error = str(exc)
