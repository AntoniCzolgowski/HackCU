from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .schemas import ReportRequest, WhatIfRequest
from .service import MatchFlowService


app = FastAPI(title="MatchFlow World Cup API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = MatchFlowService()


def _raise_http_from_value_error(error: ValueError) -> None:
    raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/matches")
def matches(city_id: str | None = Query(None)) -> dict:
    try:
        return service.get_matches(city_id=city_id)
    except ValueError as error:
        _raise_http_from_value_error(error)


@app.get("/api/meta")
def meta(city_id: str | None = Query(None), match_id: str | None = Query(None)) -> dict:
    try:
        return service.get_meta(city_id=city_id, match_id=match_id)
    except ValueError as error:
        _raise_http_from_value_error(error)


@app.get("/api/simulation")
def simulation(
    day: int = Query(0),
    step: int = Query(0),
    scenario: str = Query("baseline"),
    layer: str = Query("total"),
    city_id: str | None = Query(None),
    match_id: str | None = Query(None),
) -> dict:
    try:
        return service.get_snapshot(day=day, step=step, scenario_id=scenario, layer=layer, city_id=city_id, match_id=match_id)
    except ValueError as error:
        _raise_http_from_value_error(error)


@app.get("/api/business/{business_id}")
async def business_detail(
    business_id: str,
    day: int = Query(0),
    scenario: str = Query("baseline"),
    city_id: str | None = Query(None),
    match_id: str | None = Query(None),
) -> dict:
    try:
        return await service.get_business_detail(business_id=business_id, day=day, scenario_id=scenario, city_id=city_id, match_id=match_id)
    except ValueError as error:
        _raise_http_from_value_error(error)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown business: {error.args[0]}") from error


@app.get("/api/business/{business_id}/compare")
def business_compare(business_id: str, city_id: str | None = Query(None)) -> dict:
    try:
        return service.get_business_match_comparison(business_id=business_id, city_id=city_id)
    except ValueError as error:
        _raise_http_from_value_error(error)


@app.get("/api/zone/{zone_id}")
def zone_detail(
    zone_id: str,
    day: int = Query(0),
    scenario: str = Query("baseline"),
    city_id: str | None = Query(None),
    match_id: str | None = Query(None),
) -> dict:
    try:
        return service.get_zone_detail(zone_id=zone_id, day=day, scenario_id=scenario, city_id=city_id, match_id=match_id)
    except ValueError as error:
        _raise_http_from_value_error(error)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown special venue: {error.args[0]}") from error


@app.post("/api/business/{business_id}/report")
async def create_report(
    business_id: str,
    payload: ReportRequest,
    city_id: str | None = Query(None),
    match_id: str | None = Query(None),
) -> dict:
    try:
        return await service.create_business_report_job(
            business_id=business_id,
            day=payload.day,
            scenario_id=payload.scenario,
            visible_sections=payload.visible_sections,
            city_id=city_id,
            match_id=match_id,
        )
    except ValueError as error:
        _raise_http_from_value_error(error)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown business: {error.args[0]}") from error


@app.get("/api/reports/{job_id}")
def report_status(job_id: str) -> dict:
    try:
        return service.get_report_job(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown report job: {error.args[0]}") from error


@app.get("/api/reports/{job_id}/download")
def report_download(job_id: str) -> FileResponse:
    try:
        path = service.get_report_path(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown report job: {error.args[0]}") from error
    return FileResponse(path, filename=path.name, media_type="application/pdf")


@app.post("/api/what-if")
def what_if(payload: WhatIfRequest, city_id: str | None = Query(None), match_id: str | None = Query(None)) -> dict:
    try:
        return service.create_what_if(
            day=payload.day,
            step=payload.step,
            blocked_edge_ids=payload.blocked_edge_ids,
            duration_steps=payload.duration_steps,
            city_id=city_id,
            match_id=match_id,
        )
    except ValueError as error:
        _raise_http_from_value_error(error)


@app.get("/api/optimize-signals")
def optimize_signals(
    day: int = Query(0),
    step: int = Query(0),
    scenario: str = Query("baseline"),
    city_id: str | None = Query(None),
    match_id: str | None = Query(None),
) -> dict:
    try:
        return service.get_signal_plan(day=day, step=step, scenario_id=scenario, city_id=city_id, match_id=match_id)
    except ValueError as error:
        _raise_http_from_value_error(error)


@app.get("/api/provenance")
def provenance() -> dict:
    return service.get_provenance()
