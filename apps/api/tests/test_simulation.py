from __future__ import annotations

from app.data_loader import load_seed_bundle
from app.simulator import SimulationEngine


DEFAULT_MATCH_ID = "dallas-netherlands-japan-2026-06-14"
WEEKDAY_MATCH_ID = "dallas-england-croatia-2026-06-17"


def test_cohort_scale_and_capacity_caps() -> None:
    engine = SimulationEngine(load_seed_bundle(city_id="dallas", match_id=DEFAULT_MATCH_ID))
    scenario = engine.generate_scenario(scenario_id="baseline-test")

    stats = scenario["metadata"]["cohort_stats"]
    nationality_total = sum(stats["nationality"].values())
    ticket_total = stats["ticket_holders"]["with_ticket"] + stats["ticket_holders"]["without_ticket"]

    assert nationality_total == scenario["metadata"]["cohort_count"]
    assert ticket_total == engine.total_real_fans
    assert engine.total_real_fans <= int(engine.match["venue_capacity"] * 1.5)

    for business in scenario["days"]["0"]["business_day_summary"].values():
        assert business["peak_capacity_pct_capped"] <= 150.0


def test_match_window_behavior_and_weekday_locals_heuristic() -> None:
    weekend_engine = SimulationEngine(load_seed_bundle(city_id="dallas", match_id=DEFAULT_MATCH_ID))
    weekday_engine = SimulationEngine(load_seed_bundle(city_id="dallas", match_id=WEEKDAY_MATCH_ID))
    weekend = weekend_engine.generate_scenario(scenario_id="weekend")

    assert weekend_engine.match["crowd_profile"]["locals_multiplier"] > weekday_engine.match["crowd_profile"]["locals_multiplier"]
    assert weekend["days"]["0"]["zone_day_summary"]["stadium_zone"]["wave_summary"]["in_match_peak"] > 0

    baseline = weekend_engine.generate_scenario(scenario_id="baseline")
    blocked = weekend_engine.generate_scenario(
        scenario_id="blocked",
        blocked_edge_ids={"downtown_stadium"},
        activation_day=0,
        activation_step=weekend_engine.kickoff_step - 4,
        duration_steps=16,
    )

    baseline_load = baseline["days"]["0"]["edges"]["total"]["design_stadium"][weekend_engine.kickoff_step]
    blocked_load = blocked["days"]["0"]["edges"]["total"]["design_stadium"][weekend_engine.kickoff_step]
    assert blocked_load >= baseline_load
