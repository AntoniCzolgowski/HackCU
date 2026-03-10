from __future__ import annotations

import argparse

from .data_loader import PROVENANCE_PATH, baseline_path_for, dump_json, list_schedule_cities, list_seeded_cities, load_matches_registry, load_seed_bundle
from .simulator import SimulationEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate baseline files even if they already exist.")
    args = parser.parse_args()

    for city_id in list_seeded_cities():
        registry = load_matches_registry(city_id)
        for match in registry["matches"]:
            match_id = match["match_id"]
            output_path = baseline_path_for(city_id, match_id)
            if output_path.exists() and not args.force:
                print(f"Skipping existing baseline for {city_id}/{match_id} ...")
                continue
            print(f"Generating baseline for {city_id}/{match_id} ...")
            engine = SimulationEngine(load_seed_bundle(city_id=city_id, match_id=match_id))
            baseline = engine.generate_scenario(scenario_id="baseline")
            dump_json(output_path, baseline)
            print(f"  -> {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")

            if city_id == registry["city_id"] and match_id == registry["default_match_id"]:
                provenance = engine.build_provenance_report(baseline)
                provenance["supported_cities"] = list_schedule_cities()
                provenance["schedule_source"] = "https://www.roadtrips.com/world-cup/2026-world-cup-packages/schedule/"
                dump_json(PROVENANCE_PATH, provenance)
    print("Done.")


if __name__ == "__main__":
    main()
