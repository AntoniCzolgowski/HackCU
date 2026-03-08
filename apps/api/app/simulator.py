from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import networkx as nx


DAY_LAYERS = ("total", "team_a", "team_b", "neutral", "locals")


@dataclass(frozen=True)
class Cohort:
    cohort_id: str
    size: int
    nationality: str
    budget_cat: int
    has_ticket: bool
    transport_mode: str
    accommodation: str
    lodging_zone_id: str
    arrival_day: int
    alcohol_profile: str
    preferred_vibe: str
    home_zone_id: str


@dataclass(frozen=True)
class ActivityIntent:
    zone_id: str
    start_step: int
    end_step: int
    purpose: str
    business_id: str | None = None
    crowd_share: float = 1.0


class SimulationEngine:
    def __init__(self, seed_bundle: dict[str, Any]) -> None:
        self.seed_bundle = seed_bundle
        self.city = seed_bundle["city"]
        self.match = seed_bundle["match"]
        self.step_minutes = int(self.match["step_minutes"])
        self.timeline = self.match["timeline"]
        self.steps_per_day = int(self.timeline["steps"])
        self.day_offsets = [int(value) for value in self.match["day_offsets"]]
        self.nodes = {node["id"]: node for node in seed_bundle["nodes"]}
        self.edges = {edge["id"]: edge for edge in seed_bundle["edges"]}
        self.zones = {zone["id"]: zone for zone in seed_bundle["zones"]}
        self.businesses = {business["id"]: business for business in seed_bundle["businesses"]}
        self.special_venues = {
            venue["id"]: venue for venue in seed_bundle.get("special_venues", seed_bundle.get("fanzones", []))
        }
        self.businesses_by_zone: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for business in seed_bundle["businesses"]:
            self.businesses_by_zone[business["zone_id"]].append(business)

        self.crowd_profile = self.match.get("crowd_profile", {})
        self.graph = self._build_graph()
        self.zone_graph_node = {zone_id: zone["node_id"] for zone_id, zone in self.zones.items()}
        self.zone_capacity = self._build_zone_capacity()
        self.time_labels = [self._format_step_label(step) for step in range(self.steps_per_day)]
        self.cohort_size = 50
        attendance_multiplier = float(self.crowd_profile.get("attendance_multiplier", 1.18))
        self.total_real_fans = min(
            int(round(self.match["venue_capacity"] * attendance_multiplier)),
            int(self.match["venue_capacity"] * 1.5),
        )
        self.cohort_count = math.ceil(self.total_real_fans / self.cohort_size)
        self.kickoff_step = self._step_for_iso(self.match["kickoff_local"])
        self.halftime_step = min(self.steps_per_day - 1, self.kickoff_step + 4)
        self.final_whistle_step = min(self.steps_per_day, self.kickoff_step + 8)
        self.business_cap_factor = 1.5
        self.zone_adjacency = {
            "stadium_zone": ["texas_live_zone", "arlington_hotels_zone", "fanzone_zone"],
            "fanzone_zone": ["texas_live_zone", "arlington_hotels_zone", "stadium_zone"],
            "texas_live_zone": ["arlington_hotels_zone", "fanzone_zone", "stadium_zone", "downtown_zone"],
            "arlington_hotels_zone": ["texas_live_zone", "fanzone_zone", "stadium_zone", "downtown_zone"],
            "downtown_zone": ["uptown_zone", "deep_ellum_zone", "texas_live_zone", "local_zone"],
            "uptown_zone": ["downtown_zone", "deep_ellum_zone", "local_zone"],
            "deep_ellum_zone": ["downtown_zone", "uptown_zone", "local_zone"],
            "local_zone": ["downtown_zone", "uptown_zone", "deep_ellum_zone", "fanzone_zone"],
            "las_colinas_zone": ["downtown_zone", "uptown_zone", "local_zone"],
            "airport_zone": ["downtown_zone", "las_colinas_zone", "local_zone"],
        }

    def _build_graph(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        for node_id, node in self.nodes.items():
            graph.add_node(node_id, **node)
        for edge in self.seed_bundle["edges"]:
            directions = ((edge["source"], edge["target"]),)
            if edge.get("bidirectional", False):
                directions = ((edge["source"], edge["target"]), (edge["target"], edge["source"]))
            for source, target in directions:
                graph.add_edge(
                    source,
                    target,
                    display_edge_id=edge["id"],
                    base_travel_minutes=float(edge["base_travel_minutes"]),
                    capacity=int(edge["capacity"]),
                    road_name=edge["road_name"],
                    kind=edge["kind"],
                )
        return graph

    def _build_zone_capacity(self) -> dict[str, int]:
        capacities: dict[str, int] = {}
        kind_defaults = {
            "stadium": 80000,
            "fanzone": 18000,
            "bar_cluster": 9000,
            "hotel_cluster": 14000,
            "residential": 18000,
            "transport": 12000,
        }
        for zone_id, zone in self.zones.items():
            capacities[zone_id] = kind_defaults.get(zone["kind"], 8000)
        return capacities

    def _format_step_label(self, step: int) -> str:
        total_minutes = self.timeline["start_hour"] * 60 + step * self.step_minutes
        hour = (total_minutes // 60) % 24
        minute = total_minutes % 60
        return f"{hour:02d}:{minute:02d}"

    def _step_for_iso(self, iso_value: str) -> int:
        kickoff = datetime.fromisoformat(iso_value)
        total_minutes = kickoff.hour * 60 + kickoff.minute
        start_minutes = int(self.timeline["start_hour"]) * 60
        return max(0, min(self.steps_per_day - 1, round((total_minutes - start_minutes) / self.step_minutes)))

    def generate_scenario(
        self,
        *,
        scenario_id: str,
        blocked_edge_ids: set[str] | None = None,
        activation_day: int | None = None,
        activation_step: int = 0,
        duration_steps: int | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        blocked_edge_ids = blocked_edge_ids or set()
        if seed is None:
            seed = self.match.get("rng_seed", 20260714)
        rng = random.Random(seed)
        cohorts = self._spawn_cohorts(rng)
        day_payload: dict[str, dict[str, Any]] = {}

        for day in self.day_offsets:
            aggregates = self._empty_day_payload()
            for cohort in cohorts:
                if cohort.nationality != "locals" and day < cohort.arrival_day:
                    continue
                self._simulate_cohort_day(
                    cohort=cohort,
                    day=day,
                    rng=rng,
                    aggregates=aggregates,
                    blocked_edge_ids=blocked_edge_ids if activation_day == day else set(),
                    activation_step=activation_step if activation_day == day else 0,
                    duration_steps=duration_steps if activation_day == day else None,
                )

            day_payload[str(day)] = self._finalize_day_payload(aggregates, day)

        return {
            "scenario_id": scenario_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "seed": seed,
                "cohort_count": len(cohorts),
                "cohort_size": self.cohort_size,
                "total_real_fans": self.total_real_fans,
                "step_minutes": self.step_minutes,
                "steps_per_day": self.steps_per_day,
                "time_labels": self.time_labels,
                "day_offsets": self.day_offsets,
                "cohort_stats": self._summarize_cohorts(cohorts),
                "blocked_edge_ids": sorted(blocked_edge_ids),
                "activation_day": activation_day,
                "activation_step": activation_step,
                "duration_steps": duration_steps,
            },
            "days": day_payload,
        }

    def _empty_day_payload(self) -> dict[str, Any]:
        def series_map(keys: list[str]) -> dict[str, list[int]]:
            return {key: [0 for _ in range(self.steps_per_day)] for key in keys}

        zone_ids = list(self.zones)
        edge_ids = list(self.edges)
        business_ids = list(self.businesses)
        return {
            "zones": {layer: series_map(zone_ids) for layer in DAY_LAYERS},
            "edges": {layer: series_map(edge_ids) for layer in DAY_LAYERS},
            "businesses": {layer: series_map(business_ids) for layer in DAY_LAYERS},
            "moving": {layer: [0 for _ in range(self.steps_per_day)] for layer in DAY_LAYERS},
            "business_nationality_mix": {
                business_id: {layer: 0 for layer in ("team_a", "team_b", "neutral", "locals")}
                for business_id in business_ids
            },
            "edge_reroutes": Counter(),
            "business_spillover": Counter(),
        }

    def _spawn_cohorts(self, rng: random.Random) -> list[Cohort]:
        cohorts: list[Cohort] = []
        for index in range(self.cohort_count):
            cohort_size = min(self.cohort_size, self.total_real_fans - index * self.cohort_size)
            if cohort_size <= 0:
                break
            nw = self.crowd_profile.get("nationality_weights", {"team_a": 0.38, "team_b": 0.24, "neutral": 0.16, "locals": 0.22})
            nationality = self._weighted_choice(
                rng,
                [(k, v) for k, v in nw.items()],
            )
            budget_cat = self._weighted_choice(
                rng,
                [(1, 0.08), (2, 0.17), (3, 0.30), (4, 0.45)],
            )
            tr = self.crowd_profile.get("ticket_rates", {"team_a": 0.84, "team_b": 0.81, "neutral": 0.58, "locals": 0.44})
            has_ticket = rng.random() < tr.get(nationality, 0.50)
            accommodation = self._choose_accommodation(rng, nationality, budget_cat)
            lodging_zone_id = self._choose_lodging_zone(rng, accommodation)
            transport_mode = self._choose_transport_mode(rng, nationality, budget_cat, lodging_zone_id)
            arrival_day = self._choose_arrival_day(rng, nationality)
            preferred_vibe = self._choose_preferred_vibe(rng, nationality)
            alcohol_profile = self._choose_alcohol_profile(rng, nationality, preferred_vibe)
            home_zone_id = "local_zone" if nationality == "locals" else lodging_zone_id
            cohorts.append(
                Cohort(
                    cohort_id=f"cohort-{index:04d}",
                    size=cohort_size,
                    nationality=nationality,
                    budget_cat=budget_cat,
                    has_ticket=has_ticket,
                    transport_mode=transport_mode,
                    accommodation=accommodation,
                    lodging_zone_id=lodging_zone_id,
                    arrival_day=arrival_day,
                    alcohol_profile=alcohol_profile,
                    preferred_vibe=preferred_vibe,
                    home_zone_id=home_zone_id,
                )
            )
        return cohorts

    def _choose_accommodation(self, rng: random.Random, nationality: str, budget_cat: int) -> str:
        if nationality == "locals":
            return "local_home"
        if budget_cat == 1:
            options = [("downtown_hotel", 0.54), ("suburban_hotel", 0.18), ("airbnb", 0.28)]
        elif budget_cat == 2:
            options = [("downtown_hotel", 0.41), ("suburban_hotel", 0.28), ("airbnb", 0.31)]
        elif budget_cat == 3:
            options = [("downtown_hotel", 0.26), ("suburban_hotel", 0.38), ("airbnb", 0.36)]
        else:
            options = [("downtown_hotel", 0.14), ("suburban_hotel", 0.48), ("airbnb", 0.38)]
        return self._weighted_choice(rng, options)

    def _choose_lodging_zone(self, rng: random.Random, accommodation: str) -> str:
        if accommodation == "local_home":
            return "local_zone"
        if accommodation == "downtown_hotel":
            return self._weighted_choice(rng, [("downtown_zone", 0.78), ("uptown_zone", 0.22)])
        if accommodation == "suburban_hotel":
            return self._weighted_choice(rng, [("las_colinas_zone", 0.58), ("arlington_hotels_zone", 0.42)])
        return self._weighted_choice(rng, [("deep_ellum_zone", 0.52), ("arlington_hotels_zone", 0.24), ("uptown_zone", 0.24)])

    def _choose_transport_mode(
        self,
        rng: random.Random,
        nationality: str,
        budget_cat: int,
        lodging_zone_id: str,
    ) -> str:
        if nationality == "locals":
            return self._weighted_choice(rng, [("car", 0.64), ("rideshare", 0.16), ("dart", 0.08), ("walk", 0.12)])
        if lodging_zone_id == "arlington_hotels_zone":
            return self._weighted_choice(rng, [("walk", 0.34), ("rideshare", 0.31), ("car", 0.21), ("dart", 0.14)])
        if lodging_zone_id in {"downtown_zone", "uptown_zone", "deep_ellum_zone"}:
            if budget_cat <= 2:
                return self._weighted_choice(rng, [("rideshare", 0.44), ("dart", 0.29), ("car", 0.13), ("walk", 0.14)])
            return self._weighted_choice(rng, [("rideshare", 0.29), ("dart", 0.32), ("car", 0.27), ("walk", 0.12)])
        return self._weighted_choice(rng, [("car", 0.46), ("rideshare", 0.28), ("dart", 0.18), ("walk", 0.08)])

    def _choose_arrival_day(self, rng: random.Random, nationality: str) -> int:
        if nationality == "locals":
            return -1
        return self._weighted_choice(rng, [(-3, 0.18), (-1, 0.62), (0, 0.20)])

    def _choose_preferred_vibe(self, rng: random.Random, nationality: str) -> str:
        options = {
            "team_a": [("sports_bar", 0.55), ("fanzone", 0.25), ("hotel_bar", 0.15), ("quiet", 0.05)],
            "team_b": [("fanzone", 0.42), ("sports_bar", 0.31), ("hotel_bar", 0.19), ("quiet", 0.08)],
            "neutral": [("hotel_bar", 0.28), ("sports_bar", 0.31), ("fanzone", 0.18), ("quiet", 0.23)],
            "locals": [("quiet", 0.33), ("sports_bar", 0.32), ("fanzone", 0.18), ("hotel_bar", 0.17)],
        }
        return self._weighted_choice(rng, options[nationality])

    def _choose_alcohol_profile(self, rng: random.Random, nationality: str, preferred_vibe: str) -> str:
        weights = {
            "team_a": [("high", 0.41), ("medium", 0.42), ("low", 0.17)],
            "team_b": [("high", 0.29), ("medium", 0.49), ("low", 0.22)],
            "neutral": [("high", 0.23), ("medium", 0.43), ("low", 0.34)],
            "locals": [("high", 0.18), ("medium", 0.39), ("low", 0.43)],
        }[nationality]
        if preferred_vibe == "quiet":
            weights = [(name, weight * (0.7 if name == "high" else 1.15)) for name, weight in weights]
        return self._weighted_choice(rng, weights)

    def _simulate_cohort_day(
        self,
        *,
        cohort: Cohort,
        day: int,
        rng: random.Random,
        aggregates: dict[str, Any],
        blocked_edge_ids: set[str],
        activation_step: int,
        duration_steps: int | None,
    ) -> None:
        intents = self._build_day_intents(cohort, day, rng)
        if not intents:
            return

        active_until = None if duration_steps is None else activation_step + duration_steps
        current_zone_id = intents[0].zone_id
        current_step = intents[0].start_step
        hospitality_visits = 0

        for index, intent in enumerate(intents):
            if index == 0:
                self._record_zone_presence(aggregates, current_zone_id, current_step, intent.end_step, cohort)
                hospitality_visits += self._record_business_presence(
                    aggregates,
                    intent,
                    current_step,
                    intent.end_step,
                    cohort,
                    hospitality_visits,
                )
                current_zone_id = intent.zone_id
                current_step = intent.end_step
                continue

            if current_zone_id != intent.zone_id:
                travel = self._simulate_trip(
                    origin_zone_id=current_zone_id,
                    destination_zone_id=intent.zone_id,
                    departure_step=current_step,
                    blocked_edge_ids=blocked_edge_ids,
                    activation_step=activation_step,
                    active_until=active_until,
                )
                travel["departure_step"] = current_step
                self._record_trip(aggregates, travel, cohort)
                current_step = min(self.steps_per_day, travel["arrival_step"])
                if travel["rerouted"]:
                    for edge_id in travel["used_blocked_alternatives"]:
                        aggregates["edge_reroutes"][edge_id] += cohort.size

            stay_start = max(current_step, intent.start_step)
            stay_end = min(self.steps_per_day, max(stay_start + 1, intent.end_step))
            self._record_zone_presence(aggregates, intent.zone_id, stay_start, stay_end, cohort)
            hospitality_visits += self._record_business_presence(
                aggregates,
                intent,
                stay_start,
                stay_end,
                cohort,
                hospitality_visits,
            )
            current_zone_id = intent.zone_id
            current_step = stay_end

    def _build_day_intents(self, cohort: Cohort, day: int, rng: random.Random) -> list[ActivityIntent]:
        if day == -1:
            return self._build_day_minus_one_intents(cohort, rng)
        if day == 0:
            return self._build_match_day_intents(cohort, rng)
        return self._build_day_plus_one_intents(cohort, rng)

    def _is_overnight_traveler(self, cohort: Cohort) -> bool:
        return cohort.nationality != "locals" and cohort.accommodation != "local_home" and cohort.arrival_day <= -1

    def _choose_departure_wave_start(self, rng: random.Random, cohort: Cohort) -> int:
        options = [
            (self._step_for_clock(9, 0), 0.22),
            (self._step_for_clock(11, 0), 0.36),
            (self._step_for_clock(13, 0), 0.28),
            (self._step_for_clock(15, 0), 0.14),
        ]
        if cohort.transport_mode in {"dart", "rideshare"}:
            options = [(step, weight * (1.14 if step <= self._step_for_clock(11, 0) else 0.92)) for step, weight in options]
        if cohort.transport_mode == "car":
            options = [(step, weight * (1.08 if step >= self._step_for_clock(13, 0) else 0.96)) for step, weight in options]
        if cohort.alcohol_profile == "high":
            options = [(step, weight * (1.18 if step >= self._step_for_clock(13, 0) else 0.84)) for step, weight in options]
        if cohort.budget_cat <= 2:
            options = [(step, weight * (1.12 if step <= self._step_for_clock(11, 0) else 0.94)) for step, weight in options]
        return self._weighted_choice(rng, options)

    def _choose_post_match_return_step(self, rng: random.Random, cohort: Cohort, match_end: int) -> int:
        offsets = [(8, 0.24), (12, 0.34), (16, 0.26), (20, 0.16)]
        if cohort.transport_mode in {"walk", "dart"}:
            offsets = [(offset, weight * (1.12 if offset <= 12 else 0.9)) for offset, weight in offsets]
        if cohort.transport_mode == "rideshare":
            offsets = [(offset, weight * (1.08 if offset >= 12 else 0.94)) for offset, weight in offsets]
        if cohort.transport_mode == "car":
            offsets = [(offset, weight * (1.15 if offset >= 16 else 0.88)) for offset, weight in offsets]
        if cohort.alcohol_profile == "high":
            offsets = [(offset, weight * (1.16 if offset >= 16 else 0.85)) for offset, weight in offsets]
        if cohort.nationality == "locals":
            offsets = [(offset, weight * (1.18 if offset <= 12 else 0.84)) for offset, weight in offsets]
        return min(self.steps_per_day - 4, match_end + self._weighted_choice(rng, offsets))

    def _step_for_clock(self, hour: int, minute: int = 0) -> int:
        total_minutes = hour * 60 + minute
        start_minutes = int(self.timeline["start_hour"]) * 60
        return max(0, min(self.steps_per_day, round((total_minutes - start_minutes) / self.step_minutes)))

    def _intent_reference_step(self, start_step: int, end_step: int) -> int:
        if end_step <= start_step:
            return max(0, min(self.steps_per_day - 1, start_step))
        midpoint = start_step + max(0, (end_step - start_step - 1) // 2)
        return max(0, min(self.steps_per_day - 1, midpoint))

    def _choose_wake_step(self, rng: random.Random, cohort: Cohort, day: int) -> int:
        options = [
            (self._step_for_clock(8, 0), 0.24),
            (self._step_for_clock(8, 30), 0.36),
            (self._step_for_clock(9, 0), 0.26),
            (self._step_for_clock(9, 30), 0.14),
        ]
        if cohort.nationality == "locals":
            options = [(step, weight * (1.18 if step <= self._step_for_clock(8, 30) else 0.88)) for step, weight in options]
        if self._is_overnight_traveler(cohort):
            options = [(step, weight * (1.16 if step >= self._step_for_clock(9, 0) else 0.9)) for step, weight in options]
        if cohort.alcohol_profile == "high":
            options = [(step, weight * (1.14 if step >= self._step_for_clock(9, 0) else 0.84)) for step, weight in options]
        if cohort.has_ticket and day == 0:
            options = [(step, weight * (1.08 if step <= self._step_for_clock(8, 30) else 0.94)) for step, weight in options]
        if day == 1:
            options = [(step, weight * (1.12 if step >= self._step_for_clock(9, 0) else 0.86)) for step, weight in options]
        return self._weighted_choice(rng, options)

    def _build_day_minus_one_intents(self, cohort: Cohort, rng: random.Random) -> list[ActivityIntent]:
        if cohort.nationality != "locals" and cohort.arrival_day == 0:
            return []

        intents: list[ActivityIntent] = []
        if cohort.arrival_day == -1:
            intents.append(ActivityIntent("airport_zone", 0, 4, "arrival", None, 0.0))
            intents.append(
                ActivityIntent(
                    cohort.lodging_zone_id,
                    4,
                    12,
                    "check_in",
                    self._pick_business(
                        rng,
                        cohort,
                        cohort.lodging_zone_id,
                        "hotel",
                        self._intent_reference_step(4, 12),
                    ),
                    0.4,
                )
            )
        else:
            morning_zone = cohort.home_zone_id if cohort.nationality == "locals" else cohort.lodging_zone_id
            wake_step = self._choose_wake_step(rng, cohort, -1)
            if wake_step > 0:
                intents.append(
                    ActivityIntent(
                        morning_zone,
                        0,
                        wake_step,
                        "overnight_stay" if cohort.nationality != "locals" else "home",
                        self._pick_business(
                            rng,
                            cohort,
                            morning_zone,
                            "hotel",
                            self._intent_reference_step(0, wake_step),
                        ) if cohort.nationality != "locals" else None,
                        0.1 if cohort.nationality != "locals" else 0.0,
                    )
                )
            breakfast_end = min(16, max(wake_step + 4, self._step_for_clock(9, 30)))
            intents.append(
                ActivityIntent(
                    morning_zone,
                    wake_step,
                    breakfast_end,
                    "breakfast",
                    self._pick_business(
                        rng,
                        cohort,
                        morning_zone,
                        "breakfast",
                        self._intent_reference_step(wake_step, breakfast_end),
                    ),
                    0.3 if cohort.nationality != "locals" else 0.18,
                )
            )

        midday_zone = self._choose_explore_zone(rng, cohort, allow_stadium=False)
        evening_zone = self._choose_pre_evening_zone(rng, cohort)
        late_zone = cohort.lodging_zone_id if cohort.nationality != "locals" else "local_zone"
        midday_start = 12 if cohort.arrival_day == -1 else breakfast_end
        intents.append(
            ActivityIntent(
                midday_zone,
                midday_start,
                28,
                "explore_city",
                self._pick_business(
                    rng,
                    cohort,
                    midday_zone,
                    "explore",
                    self._intent_reference_step(midday_start, 28),
                ),
                0.44,
            )
        )
        intents.append(
            ActivityIntent(
                evening_zone,
                28,
                46,
                "day_before_bar",
                self._pick_business(
                    rng,
                    cohort,
                    evening_zone,
                    "prematch",
                    self._intent_reference_step(28, 46),
                ),
                0.78,
            )
        )
        if self._is_overnight_traveler(cohort):
            intents.append(
                ActivityIntent(
                    late_zone,
                    46,
                    58,
                    "hotel_reset",
                    self._pick_business(
                        rng,
                        cohort,
                        late_zone,
                        "hotel",
                        self._intent_reference_step(46, 58),
                    ),
                    0.28,
                )
            )
            intents.append(
                ActivityIntent(
                    late_zone,
                    58,
                    80,
                    "overnight_stay",
                    self._pick_business(
                        rng,
                        cohort,
                        late_zone,
                        "hotel",
                        self._intent_reference_step(58, 80),
                    ),
                    0.12,
                )
            )
        else:
            intents.append(
                ActivityIntent(
                    late_zone,
                    46,
                    72,
                    "hotel_reset",
                    self._pick_business(
                        rng,
                        cohort,
                        late_zone,
                        "hotel",
                        self._intent_reference_step(46, 72),
                    ),
                    0.35,
                )
            )
            intents.append(
                ActivityIntent(
                    late_zone,
                    72,
                    80,
                    "late_night",
                    self._pick_business(
                        rng,
                        cohort,
                        late_zone,
                        "hotel",
                        self._intent_reference_step(72, 80),
                    ),
                    0.18,
                )
            )
        return intents

    def _build_match_day_intents(self, cohort: Cohort, rng: random.Random) -> list[ActivityIntent]:
        intents: list[ActivityIntent] = []
        base_zone = cohort.lodging_zone_id if cohort.nationality != "locals" else "local_zone"
        explore_end = max(18, self.kickoff_step - 8)
        pre_match_start = explore_end
        pre_match_end = self.kickoff_step
        match_end = self.final_whistle_step
        return_wave_start = self._choose_post_match_return_step(rng, cohort, match_end)

        if cohort.nationality != "locals" and cohort.arrival_day == 0:
            intents.append(ActivityIntent("airport_zone", 0, 6, "arrival", None, 0.0))
            intents.append(
                ActivityIntent(
                    base_zone,
                    6,
                    14,
                    "check_in",
                    self._pick_business(
                        rng,
                        cohort,
                        base_zone,
                        "hotel",
                        self._intent_reference_step(6, 14),
                    ),
                    0.47,
                )
            )
            morning_end = 14
        else:
            wake_step = self._choose_wake_step(rng, cohort, 0)
            if wake_step > 0:
                intents.append(
                    ActivityIntent(
                        base_zone,
                        0,
                        wake_step,
                        "overnight_stay" if cohort.nationality != "locals" else "home",
                        self._pick_business(
                            rng,
                            cohort,
                            base_zone,
                            "hotel",
                            self._intent_reference_step(0, wake_step),
                        ) if cohort.nationality != "locals" else None,
                        0.1 if cohort.nationality != "locals" else 0.0,
                    )
                )
            breakfast_end = min(explore_end, max(wake_step + 4, self._step_for_clock(9, 30)))
            intents.append(
                ActivityIntent(
                    base_zone,
                    wake_step,
                    breakfast_end,
                    "wake",
                    self._pick_business(
                        rng,
                        cohort,
                        base_zone,
                        "breakfast",
                        self._intent_reference_step(wake_step, breakfast_end),
                    ),
                    0.32 if cohort.nationality != "locals" else 0.18,
                )
            )
            morning_end = breakfast_end

        midday_zone = self._choose_explore_zone(rng, cohort, allow_stadium=False)
        intents.append(
            ActivityIntent(
                midday_zone,
                morning_end,
                explore_end,
                "explore_city",
                self._pick_business(
                    rng,
                    cohort,
                    midday_zone,
                    "explore",
                    self._intent_reference_step(morning_end, explore_end),
                ),
                0.68 if cohort.nationality != "locals" else 0.56,
            )
        )

        if cohort.has_ticket:
            pre_match_zone = self._choose_prematch_zone(rng, cohort)
            intents.append(
                ActivityIntent(
                    pre_match_zone,
                    pre_match_start,
                    pre_match_end,
                    "pre_match_bar",
                self._pick_business(
                    rng,
                    cohort,
                    pre_match_zone,
                    "prematch",
                    self._intent_reference_step(pre_match_start, pre_match_end),
                ),
                    0.95,
                )
            )
            intents.append(ActivityIntent("stadium_zone", pre_match_end, match_end, "match", None, 0.0))
        else:
            watch_zone = "fanzone_zone" if cohort.preferred_vibe == "fanzone" else self._choose_watch_party_zone(rng, cohort)
            intents.append(
                ActivityIntent(
                    watch_zone,
                    pre_match_start,
                    pre_match_end,
                    "watch_party_setup",
                    self._pick_business(
                        rng,
                        cohort,
                        watch_zone,
                        "prematch",
                        self._intent_reference_step(pre_match_start, pre_match_end),
                    ),
                    0.76,
                )
            )
            intents.append(
                ActivityIntent(
                    watch_zone,
                    pre_match_end,
                    match_end,
                    "watch_party",
                    self._pick_business(
                        rng,
                        cohort,
                        watch_zone,
                        "watch_party",
                        self._intent_reference_step(pre_match_end, match_end),
                    ),
                    0.9,
                )
            )

        post_zone = self._choose_post_match_zone(rng, cohort)
        intents.append(
            ActivityIntent(
                post_zone,
                match_end,
                return_wave_start,
                "celebration",
                self._pick_business(
                    rng,
                    cohort,
                    post_zone,
                    "celebration",
                    self._intent_reference_step(match_end, return_wave_start),
                ),
                0.82,
            )
        )
        intents.append(
            ActivityIntent(
                base_zone,
                return_wave_start,
                80,
                "overnight_stay" if self._is_overnight_traveler(cohort) else "return",
                self._pick_business(
                    rng,
                    cohort,
                    base_zone,
                    "hotel",
                    self._intent_reference_step(return_wave_start, 80),
                ),
                0.46 if self._is_overnight_traveler(cohort) else 0.24,
            )
        )
        return intents

    def _build_day_plus_one_intents(self, cohort: Cohort, rng: random.Random) -> list[ActivityIntent]:
        base_zone = cohort.lodging_zone_id if cohort.nationality != "locals" else "local_zone"
        wake_step = self._choose_wake_step(rng, cohort, 1)
        breakfast_end = max(wake_step + 4, self._step_for_clock(9, 30))
        intents: list[ActivityIntent] = [
            ActivityIntent(
                base_zone,
                0,
                wake_step,
                "overnight_stay" if cohort.nationality != "locals" else "home",
                self._pick_business(
                    rng,
                    cohort,
                    base_zone,
                    "hotel",
                    self._intent_reference_step(0, wake_step),
                ) if cohort.nationality != "locals" else None,
                0.1 if cohort.nationality != "locals" else 0.0,
            ),
            ActivityIntent(
                base_zone,
                wake_step,
                breakfast_end,
                "slow_morning",
                self._pick_business(
                    rng,
                    cohort,
                    base_zone,
                    "breakfast",
                    self._intent_reference_step(wake_step, breakfast_end),
                ),
                0.24 if cohort.nationality != "locals" else 0.16,
            ),
        ]
        if cohort.nationality == "locals":
            quiet_zone = self._choose_local_reset_zone(rng, cohort)
            intents.append(
                ActivityIntent(
                    quiet_zone,
                    breakfast_end,
                    42,
                    "local_recovery",
                    self._pick_business(
                        rng,
                        cohort,
                        quiet_zone,
                        "quiet",
                        self._intent_reference_step(breakfast_end, 42),
                    ),
                    0.24,
                )
            )
            city_zone = self._choose_explore_zone(rng, cohort, allow_stadium=False)
            intents.append(
                ActivityIntent(
                    city_zone,
                    42,
                    60,
                    "city_reset",
                    self._pick_business(
                        rng,
                        cohort,
                        city_zone,
                        "quiet",
                        self._intent_reference_step(42, 60),
                    ),
                    0.32,
                )
            )
            intents.append(
                ActivityIntent(
                    "local_zone",
                    60,
                    80,
                    "home",
                    self._pick_business(
                        rng,
                        cohort,
                        "local_zone",
                        "quiet",
                        self._intent_reference_step(60, 80),
                    ),
                    0.18,
                )
            )
            return intents

        if self._is_overnight_traveler(cohort):
            departure_wave_start = self._choose_departure_wave_start(rng, cohort)
            travel_span = self._weighted_choice(rng, [(14, 0.28), (18, 0.44), (22, 0.28)])
            airport_arrival_end = min(self.steps_per_day - 10, departure_wave_start + travel_span)
            intents = [
                ActivityIntent(
                    base_zone,
                    0,
                    wake_step,
                    "overnight_stay",
                    self._pick_business(
                        rng,
                        cohort,
                        base_zone,
                        "hotel",
                        self._intent_reference_step(0, wake_step),
                    ),
                    0.1,
                ),
                ActivityIntent(
                    base_zone,
                    wake_step,
                    departure_wave_start,
                    "slow_checkout",
                    self._pick_business(
                        rng,
                        cohort,
                        base_zone,
                        "breakfast",
                        self._intent_reference_step(wake_step, departure_wave_start),
                    ),
                    0.22,
                ),
                ActivityIntent("airport_zone", departure_wave_start, airport_arrival_end, "airport_departure", None, 0.0),
                ActivityIntent("airport_zone", airport_arrival_end, 80, "departed", None, 0.0),
            ]
            return intents

        if cohort.arrival_day == 0 and cohort.alcohol_profile == "high":
            intents.append(
                ActivityIntent(
                    "texas_live_zone",
                    breakfast_end,
                    24,
                    "late_checkout_party",
                    self._pick_business(
                        rng,
                        cohort,
                        "texas_live_zone",
                        "celebration",
                        self._intent_reference_step(breakfast_end, 24),
                    ),
                    0.61,
                )
            )
        else:
            city_zone = self._choose_explore_zone(rng, cohort, allow_stadium=False)
            intents.append(
                ActivityIntent(
                    city_zone,
                    breakfast_end,
                    24,
                    "last_stop",
                    self._pick_business(
                        rng,
                        cohort,
                        city_zone,
                        "explore",
                        self._intent_reference_step(breakfast_end, 24),
                    ),
                    0.48,
                )
            )
        intents.append(ActivityIntent("airport_zone", 24, 56, "airport_departure", None, 0.0))
        intents.append(ActivityIntent("airport_zone", 56, 80, "departed", None, 0.0))
        return intents

    def _choose_explore_zone(self, rng: random.Random, cohort: Cohort, *, allow_stadium: bool) -> str:
        options = [
            ("downtown_zone", 0.28),
            ("uptown_zone", 0.18),
            ("deep_ellum_zone", 0.19),
            ("texas_live_zone", 0.19),
            ("fanzone_zone", 0.16 if cohort.preferred_vibe == "fanzone" else 0.06),
        ]
        if cohort.nationality == "locals":
            options.append(("local_zone", 0.18))
        if allow_stadium:
            options.append(("stadium_zone", 0.04))
        return self._weighted_choice(rng, options)

    def _choose_pre_evening_zone(self, rng: random.Random, cohort: Cohort) -> str:
        if cohort.preferred_vibe == "quiet":
            return self._weighted_choice(rng, [(cohort.home_zone_id, 0.52), ("downtown_zone", 0.18), ("uptown_zone", 0.14), ("texas_live_zone", 0.16)])
        return self._weighted_choice(rng, [("texas_live_zone", 0.32), ("downtown_zone", 0.24), ("uptown_zone", 0.21), ("deep_ellum_zone", 0.23)])

    def _choose_prematch_zone(self, rng: random.Random, cohort: Cohort) -> str:
        if cohort.transport_mode == "walk":
            return self._weighted_choice(rng, [("arlington_hotels_zone", 0.26), ("texas_live_zone", 0.54), ("fanzone_zone", 0.20)])
        if cohort.preferred_vibe == "fanzone":
            return self._weighted_choice(rng, [("fanzone_zone", 0.48), ("texas_live_zone", 0.36), ("arlington_hotels_zone", 0.16)])
        return self._weighted_choice(rng, [("texas_live_zone", 0.51), ("arlington_hotels_zone", 0.23), ("fanzone_zone", 0.14), ("downtown_zone", 0.12)])

    def _choose_watch_party_zone(self, rng: random.Random, cohort: Cohort) -> str:
        options = [("texas_live_zone", 0.36), ("fanzone_zone", 0.26), ("downtown_zone", 0.18), ("deep_ellum_zone", 0.12), ("local_zone", 0.08)]
        if cohort.preferred_vibe == "quiet":
            options = [("local_zone", 0.34), ("arlington_hotels_zone", 0.24), ("downtown_zone", 0.22), ("fanzone_zone", 0.20)]
        return self._weighted_choice(rng, options)

    def _choose_post_match_zone(self, rng: random.Random, cohort: Cohort) -> str:
        if cohort.alcohol_profile == "low":
            return self._weighted_choice(rng, [(cohort.home_zone_id, 0.46), ("arlington_hotels_zone", 0.24), ("downtown_zone", 0.14), ("fanzone_zone", 0.16)])
        if cohort.preferred_vibe == "quiet":
            return self._weighted_choice(rng, [(cohort.home_zone_id, 0.38), ("arlington_hotels_zone", 0.24), ("downtown_zone", 0.18), ("uptown_zone", 0.20)])
        return self._weighted_choice(rng, [("texas_live_zone", 0.33), ("arlington_hotels_zone", 0.23), ("downtown_zone", 0.18), ("uptown_zone", 0.13), ("deep_ellum_zone", 0.13)])

    def _choose_local_reset_zone(self, rng: random.Random, cohort: Cohort) -> str:
        if cohort.preferred_vibe == "quiet":
            return self._weighted_choice(rng, [("local_zone", 0.54), ("downtown_zone", 0.24), ("uptown_zone", 0.22)])
        return self._weighted_choice(rng, [("local_zone", 0.34), ("texas_live_zone", 0.21), ("downtown_zone", 0.22), ("deep_ellum_zone", 0.23)])

    def _business_type_preferences(self, purpose: str) -> set[str] | None:
        mapping = {
            "breakfast": {"hotel", "hotel_bar"},
            "hotel": {"hotel", "hotel_bar"},
            "check_in": {"hotel", "hotel_bar"},
            "hotel_reset": {"hotel", "hotel_bar"},
            "overnight_stay": {"hotel", "hotel_bar"},
            "slow_checkout": {"hotel", "hotel_bar"},
            "prematch": {"sports_bar", "cocktail_bar", "hotel_bar"},
            "watch_party": {"sports_bar", "cocktail_bar", "hotel_bar"},
            "celebration": {"sports_bar", "cocktail_bar", "hotel_bar"},
            "day_before_bar": {"sports_bar", "cocktail_bar", "hotel_bar"},
            "explore": {"sports_bar", "cocktail_bar", "hotel_bar"},
            "quiet": {"cocktail_bar", "hotel_bar", "hotel"},
        }
        return mapping.get(purpose)

    def _is_business_open_at_step(self, business: dict[str, Any], step: int) -> bool:
        hours = str(business.get("hours", "")).strip()
        if not hours or hours == "24/7":
            return True
        try:
            open_label, close_label = hours.split("-", maxsplit=1)
            open_hour, open_minute = (int(part) for part in open_label.split(":"))
            close_hour, close_minute = (int(part) for part in close_label.split(":"))
        except ValueError:
            return True

        total_minutes = self.timeline["start_hour"] * 60 + step * self.step_minutes
        day_minutes = total_minutes % (24 * 60)
        open_minutes = (open_hour * 60) + open_minute
        close_minutes = (close_hour * 60) + close_minute
        if open_minutes == close_minutes:
            return True
        if close_minutes < open_minutes:
            return day_minutes >= open_minutes or day_minutes < close_minutes
        return open_minutes <= day_minutes < close_minutes

    def _pick_business(
        self,
        rng: random.Random,
        cohort: Cohort,
        zone_id: str,
        purpose: str,
        reference_step: int | None = None,
    ) -> str | None:
        candidates = self.businesses_by_zone.get(zone_id, [])
        if not candidates:
            return None

        if reference_step is not None:
            candidates = [business for business in candidates if self._is_business_open_at_step(business, reference_step)]
            if not candidates:
                return None

        preferred_types = self._business_type_preferences(purpose)
        if preferred_types:
            preferred_candidates = [business for business in candidates if business["type"] in preferred_types]
            if preferred_candidates:
                candidates = preferred_candidates

        weighted: list[tuple[str, float]] = []
        for business in candidates:
            weight = (business["rating"] * 0.8) + (business["capacity_estimate"] / 900)
            if purpose in {"breakfast", "hotel", "check_in", "overnight_stay", "slow_checkout"}:
                if business["type"] == "hotel":
                    weight *= 1.95
                elif business["type"] == "hotel_bar":
                    weight *= 1.45
            if purpose in {"prematch", "celebration", "watch_party", "day_before_bar"} and business["type"] in {"sports_bar", "cocktail_bar", "hotel_bar"}:
                weight *= 1.6
            if cohort.preferred_vibe == "sports_bar" and business["type"] == "sports_bar":
                weight *= 1.45
            if cohort.preferred_vibe == "hotel_bar" and business["type"] in {"hotel", "hotel_bar"}:
                weight *= 1.38
            if cohort.preferred_vibe == "quiet" and business["type"] == "cocktail_bar":
                weight *= 1.22
            if cohort.nationality == "team_a" and business["type"] == "sports_bar":
                weight *= 1.18
            if cohort.nationality == "team_b" and business["type"] in {"hotel_bar", "hotel"}:
                weight *= 1.12
            if purpose == "quiet" and business["type"] == "sports_bar":
                weight *= 0.72
            weighted.append((business["id"], weight))
        return self._weighted_choice(rng, weighted)

    def _simulate_trip(
        self,
        *,
        origin_zone_id: str,
        destination_zone_id: str,
        departure_step: int,
        blocked_edge_ids: set[str],
        activation_step: int,
        active_until: int | None,
    ) -> dict[str, Any]:
        origin_node = self.zone_graph_node[origin_zone_id]
        destination_node = self.zone_graph_node[destination_zone_id]
        baseline_segments = self._route_segments(self.graph, origin_node, destination_node)
        baseline_step_edges = self._expand_segments(baseline_segments)

        if not blocked_edge_ids or departure_step >= self.steps_per_day:
            return {
                "step_edges": baseline_step_edges,
                "arrival_step": departure_step + len(baseline_step_edges),
                "rerouted": False,
                "used_blocked_alternatives": [],
            }

        if active_until is not None and departure_step >= active_until:
            return {
                "step_edges": baseline_step_edges,
                "arrival_step": departure_step + len(baseline_step_edges),
                "rerouted": False,
                "used_blocked_alternatives": [],
            }

        blocked_graph = self._graph_without_edges(blocked_edge_ids)
        travel_end = departure_step + len(baseline_step_edges)
        if activation_step >= travel_end:
            return {
                "step_edges": baseline_step_edges,
                "arrival_step": travel_end,
                "rerouted": False,
                "used_blocked_alternatives": [],
            }

        if activation_step <= departure_step:
            rerouted_segments = self._route_segments(blocked_graph, origin_node, destination_node, fallback_graph=self.graph)
            rerouted_step_edges = self._expand_segments(rerouted_segments)
            return {
                "step_edges": rerouted_step_edges,
                "arrival_step": departure_step + len(rerouted_step_edges),
                "rerouted": True,
                "used_blocked_alternatives": list({segment["display_edge_id"] for segment in rerouted_segments}),
            }

        current_node = origin_node
        prefix_step_edges: list[str] = []
        step_cursor = departure_step
        for segment in baseline_segments:
            segment_edges = [segment["display_edge_id"] for _ in range(segment["step_span"])]
            next_cursor = step_cursor + segment["step_span"]
            if next_cursor <= activation_step:
                prefix_step_edges.extend(segment_edges)
                step_cursor = next_cursor
                current_node = segment["target"]
                continue

            keep_steps = max(0, activation_step - step_cursor)
            prefix_step_edges.extend(segment_edges[:keep_steps])
            current_node = segment["target"]
            break

        rerouted_segments = self._route_segments(blocked_graph, current_node, destination_node, fallback_graph=self.graph)
        rerouted_step_edges = self._expand_segments(rerouted_segments)
        return {
            "step_edges": prefix_step_edges + rerouted_step_edges,
            "arrival_step": departure_step + len(prefix_step_edges) + len(rerouted_step_edges),
            "rerouted": True,
            "used_blocked_alternatives": list({segment["display_edge_id"] for segment in rerouted_segments}),
        }

    def _route_segments(
        self,
        graph: nx.DiGraph,
        origin_node: str,
        destination_node: str,
        *,
        fallback_graph: nx.DiGraph | None = None,
    ) -> list[dict[str, Any]]:
        try:
            path = nx.shortest_path(graph, origin_node, destination_node, weight="base_travel_minutes")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            if fallback_graph is None:
                raise
            path = nx.shortest_path(fallback_graph, origin_node, destination_node, weight="base_travel_minutes")

        segments: list[dict[str, Any]] = []
        for index in range(len(path) - 1):
            source, target = path[index], path[index + 1]
            edge_data = graph.get_edge_data(source, target) or (fallback_graph.get_edge_data(source, target) if fallback_graph else None)
            if edge_data is None:
                continue
            step_span = max(1, math.ceil(float(edge_data["base_travel_minutes"]) / self.step_minutes))
            segments.append(
                {
                    "display_edge_id": edge_data["display_edge_id"],
                    "source": source,
                    "target": target,
                    "step_span": step_span,
                }
            )
        return segments

    def _expand_segments(self, segments: list[dict[str, Any]]) -> list[str]:
        return [segment["display_edge_id"] for segment in segments for _ in range(segment["step_span"])]

    def _graph_without_edges(self, blocked_edge_ids: set[str]) -> nx.DiGraph:
        graph = self.graph.copy()
        to_remove = [
            (source, target)
            for source, target, data in graph.edges(data=True)
            if data["display_edge_id"] in blocked_edge_ids
        ]
        graph.remove_edges_from(to_remove)
        return graph

    def _record_zone_presence(
        self,
        aggregates: dict[str, Any],
        zone_id: str,
        start_step: int,
        end_step: int,
        cohort: Cohort,
    ) -> None:
        if start_step >= self.steps_per_day:
            return
        layer = cohort.nationality
        for step in range(max(0, start_step), min(self.steps_per_day, end_step)):
            aggregates["zones"]["total"][zone_id][step] += cohort.size
            aggregates["zones"][layer][zone_id][step] += cohort.size

    def _record_business_presence(
        self,
        aggregates: dict[str, Any],
        intent: ActivityIntent,
        start_step: int,
        end_step: int,
        cohort: Cohort,
        hospitality_visits: int,
    ) -> int:
        if not intent.business_id or intent.crowd_share <= 0:
            return 0
        layer = cohort.nationality
        business = self.businesses.get(intent.business_id)
        if business is None:
            return 0
        visit_multiplier = self._business_visit_multiplier(intent, business, hospitality_visits)
        if visit_multiplier <= 0:
            return 0
        business_load = max(0, round(cohort.size * intent.crowd_share * visit_multiplier))
        if business_load <= 0:
            return 0
        active_steps = 0
        for step in range(max(0, start_step), min(self.steps_per_day, end_step)):
            if not self._is_business_open_at_step(business, step):
                continue
            aggregates["businesses"]["total"][intent.business_id][step] += business_load
            aggregates["businesses"][layer][intent.business_id][step] += business_load
            active_steps += 1
        if active_steps <= 0:
            return 0
        aggregates["business_nationality_mix"][intent.business_id][layer] += business_load * active_steps
        return 1 if self._counts_as_hospitality_visit(intent, business) else 0

    def _record_trip(self, aggregates: dict[str, Any], travel: dict[str, Any], cohort: Cohort) -> None:
        layer = cohort.nationality
        edge_weight = {
            "car": 1.0,
            "rideshare": 0.85,
            "dart": 0.35,
            "walk": 0.15,
        }[cohort.transport_mode]
        for offset, display_edge_id in enumerate(travel["step_edges"]):
            absolute_step = travel["departure_step"] + offset
            if absolute_step >= self.steps_per_day:
                break
            edge_value = round(cohort.size * edge_weight)
            aggregates["edges"]["total"][display_edge_id][absolute_step] += edge_value
            aggregates["edges"][layer][display_edge_id][absolute_step] += edge_value
            aggregates["moving"]["total"][absolute_step] += cohort.size
            aggregates["moving"][layer][absolute_step] += cohort.size

    def _counts_as_hospitality_visit(self, intent: ActivityIntent, business: dict[str, Any]) -> bool:
        if business["type"] == "hotel":
            return False
        if intent.purpose in {"check_in", "hotel_reset", "return", "overnight_stay", "slow_checkout", "departed", "airport_departure"}:
            return False
        return business["type"] in {"sports_bar", "cocktail_bar", "restaurant", "hotel_bar"}

    def _business_visit_multiplier(self, intent: ActivityIntent, business: dict[str, Any], hospitality_visits: int) -> float:
        if not self._counts_as_hospitality_visit(intent, business):
            return 1.0
        if hospitality_visits <= 0:
            return 1.0
        if hospitality_visits == 1:
            return 0.45
        if hospitality_visits == 2:
            return 0.2
        return 0.0

    def _business_capacity_limit(self, business_id: str) -> int:
        return max(1, round(self.businesses[business_id]["capacity_estimate"] * self.business_cap_factor))

    def _candidate_spillover_targets(self, business_id: str) -> list[str]:
        business = self.businesses[business_id]
        zone_id = business["zone_id"]
        ordered_targets: list[str] = []

        for candidate in self.businesses_by_zone.get(zone_id, []):
            if candidate["id"] != business_id:
                ordered_targets.append(candidate["id"])

        for neighbor_zone in self.zone_adjacency.get(zone_id, []):
            for candidate in self.businesses_by_zone.get(neighbor_zone, []):
                if candidate["id"] != business_id and candidate["id"] not in ordered_targets:
                    ordered_targets.append(candidate["id"])

        return ordered_targets

    def _apply_business_capacity_caps(self, aggregates: dict[str, Any]) -> None:
        for step in range(self.steps_per_day):
            for business_id in self.businesses:
                total_series = aggregates["businesses"]["total"][business_id]
                current_total = total_series[step]
                limit = self._business_capacity_limit(business_id)
                overflow = max(0, current_total - limit)
                if overflow <= 0:
                    continue

                layer_values = {
                    layer: aggregates["businesses"][layer][business_id][step]
                    for layer in DAY_LAYERS
                    if layer != "total"
                }
                layer_total = sum(layer_values.values()) or 1
                total_series[step] = limit
                for layer, value in layer_values.items():
                    scaled = round(value * (limit / layer_total))
                    aggregates["businesses"][layer][business_id][step] = min(scaled, limit)

                remaining = overflow
                origin_business = self.businesses[business_id]
                for target_id in self._candidate_spillover_targets(business_id):
                    target_business = self.businesses[target_id]
                    if origin_business["type"] in {"sports_bar", "cocktail_bar", "restaurant"} and target_business["type"] == "hotel":
                        continue
                    if origin_business["type"] == "hotel" and target_business["type"] not in {"hotel", "hotel_bar", "restaurant"}:
                        continue
                    if not self._is_business_open_at_step(target_business, step):
                        continue
                    target_total = aggregates["businesses"]["total"][target_id][step]
                    headroom = self._business_capacity_limit(target_id) - target_total
                    if headroom <= 0:
                        continue
                    moved = min(headroom, remaining)
                    aggregates["businesses"]["total"][target_id][step] += moved
                    for layer, value in layer_values.items():
                        share = value / layer_total
                        aggregates["businesses"][layer][target_id][step] += round(moved * share)
                    remaining -= moved
                    if remaining <= 0:
                        break

                if remaining > 0:
                    fallback_zone = "fanzone_zone" if "fanzone_zone" in self.zones else "local_zone"
                    aggregates["zones"]["total"][fallback_zone][step] += remaining
                    for layer, value in layer_values.items():
                        share = value / layer_total
                        aggregates["zones"][layer][fallback_zone][step] += round(remaining * share)
                    aggregates["business_spillover"][business_id] += remaining

    @staticmethod
    def _series_arrivals(series: list[int]) -> list[int]:
        arrivals = [series[0]]
        arrivals.extend(max(0, series[index] - series[index - 1]) for index in range(1, len(series)))
        return arrivals

    @staticmethod
    def _series_departures(series: list[int]) -> list[int]:
        departures = [0]
        departures.extend(max(0, series[index - 1] - series[index]) for index in range(1, len(series)))
        return departures

    @staticmethod
    def _served_visits(series: list[int]) -> int:
        return int(series[0] + sum(max(0, series[index] - series[index - 1]) for index in range(1, len(series))))

    def _finalize_day_payload(self, aggregates: dict[str, Any], day: int) -> dict[str, Any]:
        self._apply_business_capacity_caps(aggregates)

        edge_summaries = {}
        for edge_id, edge in self.edges.items():
            load_series = aggregates["edges"]["total"][edge_id]
            peak_load = max(load_series)
            edge_summaries[edge_id] = {
                "peak_load": peak_load,
                "peak_congestion": round(peak_load / edge["capacity"], 3),
                "road_name": edge["road_name"],
                "kind": edge["kind"],
            }

        business_day_summary: dict[str, Any] = {}
        for business_id, business in self.businesses.items():
            total_series = [int(value) for value in aggregates["businesses"]["total"][business_id]]
            peak_value = max(total_series)
            peak_step = total_series.index(peak_value) if peak_value > 0 else 0
            mix_counts = {
                layer: sum(aggregates["businesses"][layer][business_id])
                for layer in DAY_LAYERS
                if layer != "total"
            }
            mix_total = sum(mix_counts.values()) or 1
            capacity_limit = self._business_capacity_limit(business_id)
            capacity_estimate = max(1, business["capacity_estimate"])
            served_visits = self._served_visits(total_series)
            business_day_summary[business_id] = {
                "name": business["name"],
                "type": business["type"],
                "active_visitors_series_15m": total_series,
                "total_daily_footfall": served_visits,
                "served_visits_today": served_visits,
                "peak_step": peak_step,
                "peak_label": self.time_labels[peak_step],
                "peak_value": peak_value,
                "peak_active_visitors": peak_value,
                "peak_capacity_pct_capped": round(min(150.0, (peak_value / capacity_estimate) * 100), 1),
                "operational_capacity_limit": capacity_limit,
                "capacity_estimate": capacity_estimate,
                "spillover_total": int(aggregates["business_spillover"].get(business_id, 0)),
                "nationality_mix": {
                    layer: round((value / mix_total) * 100, 1)
                    for layer, value in mix_counts.items()
                },
            }

        zone_day_summary: dict[str, Any] = {}
        for zone_id, zone in self.zones.items():
            total_series = [int(value) for value in aggregates["zones"]["total"][zone_id]]
            peak_value = max(total_series)
            peak_step = total_series.index(peak_value) if peak_value > 0 else 0
            arrivals = self._series_arrivals(total_series)
            departures = self._series_departures(total_series)
            mix_counts = {
                layer: sum(aggregates["zones"][layer][zone_id])
                for layer in DAY_LAYERS
                if layer != "total"
            }
            mix_total = sum(mix_counts.values()) or 1
            zone_day_summary[zone_id] = {
                "zone_id": zone_id,
                "name": zone["name"],
                "kind": zone["kind"],
                "active_people_series_15m": total_series,
                "peak_active_people": peak_value,
                "peak_step": peak_step,
                "peak_label": self.time_labels[peak_step],
                "arrivals_series_15m": arrivals,
                "departures_series_15m": departures,
                "cumulative_entries": int(sum(arrivals)),
                "cumulative_exits": int(sum(departures)),
                "audience_mix": {
                    layer: round((value / mix_total) * 100, 1)
                    for layer, value in mix_counts.items()
                },
                "wave_summary": {
                    "pre_match_peak": max(total_series[: self.kickoff_step] or [0]),
                    "in_match_peak": max(total_series[self.kickoff_step:self.final_whistle_step] or [0]),
                    "post_match_peak": max(total_series[self.final_whistle_step:] or [0]),
                },
            }

        return {
            "time_labels": self.time_labels,
            "zones": aggregates["zones"],
            "edges": aggregates["edges"],
            "businesses": aggregates["businesses"],
            "moving": aggregates["moving"],
            "edge_reroutes": dict(aggregates["edge_reroutes"]),
            "business_spillover": dict(aggregates["business_spillover"]),
            "edge_summaries": edge_summaries,
            "business_day_summary": business_day_summary,
            "zone_day_summary": zone_day_summary,
            "match_markers": {
                "kickoff_step": self.kickoff_step,
                "halftime_step": self.halftime_step,
                "final_whistle_step": self.final_whistle_step,
                "kickoff_label": self.time_labels[self.kickoff_step],
                "halftime_label": self.time_labels[self.halftime_step],
                "final_whistle_label": self.time_labels[min(self.steps_per_day - 1, self.final_whistle_step - 1)],
            },
            "weather": self.seed_bundle["weather"][str(day)],
        }

    def _summarize_cohorts(self, cohorts: list[Cohort]) -> dict[str, dict[str, int]]:
        return {
            "nationality": dict(Counter(cohort.nationality for cohort in cohorts)),
            "budget_cat": dict(Counter(str(cohort.budget_cat) for cohort in cohorts)),
            "transport_mode": dict(Counter(cohort.transport_mode for cohort in cohorts)),
            "accommodation": dict(Counter(cohort.accommodation for cohort in cohorts)),
            "arrival_day": dict(Counter(str(cohort.arrival_day) for cohort in cohorts)),
            "ticket_holders": {
                "with_ticket": sum(cohort.size for cohort in cohorts if cohort.has_ticket),
                "without_ticket": sum(cohort.size for cohort in cohorts if not cohort.has_ticket),
            },
        }

    def build_provenance_report(self, baseline_scenario: dict[str, Any]) -> dict[str, Any]:
        baseline_day = baseline_scenario["days"]["0"]
        busiest_business = max(
            baseline_day["business_day_summary"].values(),
            key=lambda item: item["total_daily_footfall"],
        )
        most_congested_edge = max(
            baseline_day["edge_summaries"].items(),
            key=lambda item: item[1]["peak_congestion"],
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": [
                {
                    "id": "seed_graph",
                    "label": "Road network graph",
                    "status": "hybrid_seeded",
                    "details": "The simulation uses a reduced corridor graph for speed, while the rendered polylines follow road-aligned routes derived from open routing data.",
                },
                {
                    "id": "business_seed",
                    "label": "Bars and hotels",
                    "status": "seeded_real",
                    "details": "Venue names are real-world references, while ratings, capacity estimates, and some coordinates are curated for the demo.",
                },
                {
                    "id": "weather",
                    "label": "Weather",
                    "status": "seeded_replaceable",
                    "details": "Weather defaults to a seeded July scenario and can be replaced with Open-Meteo refresh data.",
                },
                {
                    "id": "simulation",
                    "label": "Fan movement simulation",
                    "status": "simulated",
                    "details": "Cohort behaviors are deterministic and generated from weighted heuristics linked to budget, nationality, and transport mode.",
                },
                {
                    "id": "llm_recommendations",
                    "label": "Business recommendation cards",
                    "status": "heuristic_or_live",
                    "details": "Heuristic text is used by default. Anthropic can be enabled later through environment variables.",
                },
            ],
            "baseline_highlights": {
                "match_day_busiest_business": busiest_business,
                "match_day_most_congested_edge": {
                    "edge_id": most_congested_edge[0],
                    **most_congested_edge[1],
                },
            },
            "cohort_model": baseline_scenario["metadata"]["cohort_stats"],
        }

    def scenario_hash(
        self,
        *,
        day: int,
        step: int,
        blocked_edge_ids: set[str],
        duration_steps: int | None,
    ) -> str:
        payload = f"{day}:{step}:{','.join(sorted(blocked_edge_ids))}:{duration_steps or 'full'}"
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
        return f"scenario-{digest[:8]}"

    @staticmethod
    def _weighted_choice(rng: random.Random, options: list[tuple[Any, float]]) -> Any:
        total = sum(weight for _, weight in options)
        threshold = rng.random() * total
        rolling = 0.0
        for value, weight in options:
            rolling += weight
            if rolling >= threshold:
                return value
        return options[-1][0]
