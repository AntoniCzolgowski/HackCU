from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.data_loader import list_seeded_cities, load_matches_registry, load_seed_bundle
from app.main import app


client = TestClient(app)
DEFAULT_MATCH_ID = "dallas-netherlands-japan-2026-06-14"


def test_meta_matches_and_simulation_endpoints() -> None:
    matches_response = client.get("/api/matches", params={"city_id": "dallas"})
    assert matches_response.status_code == 200
    matches = matches_response.json()
    assert matches["default_match_id"] == DEFAULT_MATCH_ID
    assert len(matches["matches"]) == 5

    monterrey_response = client.get("/api/matches", params={"city_id": "monterrey"})
    assert monterrey_response.status_code == 200
    monterrey = monterrey_response.json()
    assert len(monterrey["matches"]) == 3
    assert monterrey["matches"][0]["title"] == "Poland vs Tunisia"

    meta_response = client.get("/api/meta", params={"city_id": "dallas", "match_id": DEFAULT_MATCH_ID})
    assert meta_response.status_code == 200
    meta = meta_response.json()
    assert meta["match"]["venue"] == "AT&T Stadium"
    assert meta["timeline"]["match_markers"]["kickoff_label"]
    assert any(item["entity_type"] == "stadium" for item in meta["special_venues"])

    simulation_response = client.get(
        "/api/simulation",
        params={"day": 0, "step": 48, "scenario": "baseline", "layer": "total", "city_id": "dallas", "match_id": DEFAULT_MATCH_ID},
    )
    assert simulation_response.status_code == 200
    snapshot = simulation_response.json()
    assert snapshot["special_overlay"]
    assert snapshot["summary"]["busiest_special_venue"]["entity_type"] in {"stadium", "fanzone"}


def test_business_zone_and_report_endpoints() -> None:
    business_response = client.get(
        "/api/business/biz_texas_live",
        params={"day": 0, "scenario": "baseline", "city_id": "dallas", "match_id": DEFAULT_MATCH_ID},
    )
    assert business_response.status_code == 200
    business = business_response.json()
    assert business["entity_type"] == "business"
    assert business["served_revenue"]["total"] > 0
    assert business["metric_explanations"]["served_revenue"]["formula"]

    zone_response = client.get(
        "/api/zone/stadium_zone",
        params={"day": 0, "scenario": "baseline", "city_id": "dallas", "match_id": DEFAULT_MATCH_ID},
    )
    assert zone_response.status_code == 200
    zone = zone_response.json()
    assert zone["entity_type"] == "stadium"
    assert zone["top_inbound_corridors"]

    report_response = client.post(
        "/api/business/biz_texas_live/report",
        params={"city_id": "dallas", "match_id": DEFAULT_MATCH_ID},
        json={"day": 0, "scenario": "baseline", "visible_sections": {"demand": True}},
    )
    assert report_response.status_code == 200
    report_job = report_response.json()
    assert report_job["job_id"].startswith("report-")

    download_url = None
    for _ in range(20):
        status_response = client.get(f"/api/reports/{report_job['job_id']}")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        if status_payload["status"] == "completed":
            download_url = status_payload["download_url"]
            break
        time.sleep(0.1)

    assert download_url is not None
    download_response = client.get(download_url)
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/pdf"


def test_all_seeded_cities_have_live_meta_simulation_and_drawer_data() -> None:
    expected_cities = {"dallas", "houston", "kansas-city", "miami", "san-francisco", "monterrey"}
    assert expected_cities.issubset(set(list_seeded_cities()))

    matches_response = client.get("/api/matches", params={"city_id": "dallas"})
    assert matches_response.status_code == 200
    available_cities = {item["city_id"]: item["simulation_ready"] for item in matches_response.json()["available_cities"]}
    for city_id in expected_cities:
        assert available_cities.get(city_id) is True

    for city_id in expected_cities:
        registry = load_matches_registry(city_id)
        match_id = registry["default_match_id"]
        seed_bundle = load_seed_bundle(city_id=city_id, match_id=match_id)
        first_business_id = seed_bundle["businesses"][0]["id"]

        meta_response = client.get("/api/meta", params={"city_id": city_id, "match_id": match_id})
        assert meta_response.status_code == 200, city_id
        meta = meta_response.json()
        assert meta["businesses"], city_id
        assert meta["special_venues"], city_id
        assert meta["edges"], city_id
        assert meta["zones"][0]["name"], city_id
        if city_id != "dallas":
            airport_zone = next(zone for zone in meta["zones"] if zone["id"] == "airport_zone")
            assert "DFW" not in airport_zone["name"], city_id
            road_names = [edge["road_name"] for edge in meta["edges"][:4]]
            assert all(name not in {"Airport Connector", "North Gateway Express", "Inner Ring Freeway"} for name in road_names), city_id

        simulation_response = client.get(
            "/api/simulation",
            params={"day": 0, "step": 36, "scenario": "baseline", "layer": "total", "city_id": city_id, "match_id": match_id},
        )
        assert simulation_response.status_code == 200, city_id
        snapshot = simulation_response.json()
        assert snapshot["business_overlay"], city_id
        assert snapshot["special_overlay"], city_id

        business_response = client.get(
            f"/api/business/{first_business_id}",
            params={"day": 0, "scenario": "baseline", "city_id": city_id, "match_id": match_id},
        )
        assert business_response.status_code == 200, city_id

        zone_response = client.get(
            "/api/zone/stadium_zone",
            params={"day": 0, "scenario": "baseline", "city_id": city_id, "match_id": match_id},
        )
        assert zone_response.status_code == 200, city_id
