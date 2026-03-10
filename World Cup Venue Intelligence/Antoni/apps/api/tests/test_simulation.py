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


def test_match_day_bars_do_not_fill_before_opening_time() -> None:
    engine = SimulationEngine(load_seed_bundle(city_id="dallas", match_id=DEFAULT_MATCH_ID))
    scenario = engine.generate_scenario(scenario_id="morning-realism")
    day = scenario["days"]["0"]["business_day_summary"]

    happiest_hour = day["biz_happiest_hour"]["active_visitors_series_15m"]
    texas_live = day["biz_texas_live"]["active_visitors_series_15m"]

    assert max(happiest_hour[: engine._step_for_clock(11, 0)]) == 0
    assert max(texas_live[: engine._step_for_clock(10, 0)]) == 0


def test_hotels_follow_preload_matchday_fill_and_departure_waves() -> None:
    engine = SimulationEngine(load_seed_bundle(city_id="dallas", match_id=DEFAULT_MATCH_ID))
    scenario = engine.generate_scenario(scenario_id="hotel-wave-realism")

    hotel_ids = [
        business["id"]
        for business in engine.seed_bundle["businesses"]
        if business["type"] in {"hotel", "hotel_bar"}
    ]
    assert hotel_ids

    peaks_day_minus = [
        max(scenario["days"]["-1"]["business_day_summary"][business_id]["active_visitors_series_15m"])
        for business_id in hotel_ids
    ]
    peaks_match_day = [
        max(scenario["days"]["0"]["business_day_summary"][business_id]["active_visitors_series_15m"])
        for business_id in hotel_ids
    ]
    peaks_day_plus = [
        max(scenario["days"]["1"]["business_day_summary"][business_id]["active_visitors_series_15m"])
        for business_id in hotel_ids
    ]

    avg_minus = sum(peaks_day_minus) / len(peaks_day_minus)
    avg_match = sum(peaks_match_day) / len(peaks_match_day)
    avg_plus = sum(peaks_day_plus) / len(peaks_day_plus)

    # Hotels should run hot before kickoff, hit the highest pressure on match day,
    # then cool materially after departure waves begin.
    assert avg_minus >= avg_match * 0.9
    assert avg_match >= avg_minus
    assert avg_plus <= avg_match * 0.85

    airport_arrivals = scenario["days"]["1"]["zone_day_summary"]["airport_zone"]["arrivals_series_15m"]
    local_peak_count = sum(
        1
        for index in range(1, len(airport_arrivals) - 1)
        if airport_arrivals[index] >= airport_arrivals[index - 1]
        and airport_arrivals[index] >= airport_arrivals[index + 1]
        and airport_arrivals[index] > 2000
    )
    assert local_peak_count >= 3

    flagship_hotel = max(
        (
            business
            for business in engine.seed_bundle["businesses"]
            if business["type"] in {"hotel", "hotel_bar"}
        ),
        key=lambda item: item["capacity_estimate"],
    )["id"]
    flagship_series = scenario["days"]["1"]["business_day_summary"][flagship_hotel]["active_visitors_series_15m"]
    drops = [max(0, flagship_series[index - 1] - flagship_series[index]) for index in range(1, len(flagship_series))]
    major_drop_threshold = max(40, round(engine._business_capacity_limit(flagship_hotel) / 15))
    assert sum(1 for value in drops if value >= major_drop_threshold) >= 3
