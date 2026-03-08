from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
CITY_DATA_DIR = ROOT / "data" / "cities"
DEFAULT_CITIES = ["houston", "kansas-city", "miami", "san-francisco", "monterrey"]
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{coordinates}?{query}"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def route_geometry(source: dict[str, Any], target: dict[str, Any]) -> tuple[list[list[float]], float, float, str | None]:
    coordinates = f"{source['lng']},{source['lat']};{target['lng']},{target['lat']}"
    query = urlencode({"overview": "full", "geometries": "geojson", "steps": "true"})
    with urlopen(OSRM_URL.format(coordinates=coordinates, query=query), timeout=45) as response:
        payload = json.load(response)

    if payload.get("code") != "Ok":
        raise RuntimeError(f"OSRM failed for {source['label']} -> {target['label']}: {payload}")

    route = payload["routes"][0]
    legs = route.get("legs", [])
    step_distances: dict[str, float] = {}
    for leg in legs:
        for step in leg.get("steps", []):
            name = str(step.get("name") or "").strip()
            if not name:
                continue
            step_distances[name] = step_distances.get(name, 0.0) + float(step.get("distance") or 0.0)

    sorted_names = sorted(step_distances.items(), key=lambda item: item[1], reverse=True)
    if not sorted_names:
        road_name = None
    elif len(sorted_names) == 1 or sorted_names[1][1] < sorted_names[0][1] * 0.3:
        road_name = sorted_names[0][0]
    else:
        road_name = f"{sorted_names[0][0]} via {sorted_names[1][0]}"

    return (
        route["geometry"]["coordinates"],
        float(route["distance"]) / 1000.0,
        float(route["duration"]) / 60.0,
        road_name,
    )


def refresh_city(city_id: str, *, sleep_seconds: float) -> None:
    city_dir = CITY_DATA_DIR / city_id
    if not city_dir.exists():
        raise FileNotFoundError(f"City pack not found: {city_dir}")

    base_path = city_dir / "base.json"
    edge_path_path = city_dir / "edge_paths.json"
    base = load_json(base_path)
    nodes = {node["id"]: node for node in base["nodes"]}
    edge_paths = {}

    print(f"Refreshing {city_id}...")
    for edge in base["edges"]:
        source = nodes[edge["source"]]
        target = nodes[edge["target"]]
        geometry, distance_km, duration_minutes, road_name = route_geometry(source, target)
        edge_paths[edge["id"]] = geometry
        edge["distance_km"] = round(distance_km, 1)
        edge["base_travel_minutes"] = max(1, round(duration_minutes))
        if road_name:
            edge["road_name"] = road_name
        print(
            f"  {edge['id']}: {source['label']} -> {target['label']} | "
            f"{edge['road_name']} | {edge['distance_km']} km | {edge['base_travel_minutes']} min"
        )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    dump_json(base_path, base)
    dump_json(edge_path_path, edge_paths)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh city edge paths and route metadata from OSRM.")
    parser.add_argument("--city", action="append", dest="cities", help="Specific city_id to refresh. Can be used multiple times.")
    parser.add_argument("--include-dallas", action="store_true", help="Also refresh Dallas.")
    parser.add_argument("--sleep", type=float, default=0.15, help="Delay between OSRM calls in seconds.")
    args = parser.parse_args()

    cities = args.cities or list(DEFAULT_CITIES)
    if args.include_dallas and "dallas" not in cities:
        cities.insert(0, "dallas")

    for city_id in cities:
        refresh_city(city_id, sleep_seconds=args.sleep)

    print("Route refresh complete.")


if __name__ == "__main__":
    main()
