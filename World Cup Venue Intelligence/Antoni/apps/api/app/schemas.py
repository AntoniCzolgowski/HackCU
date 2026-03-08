from __future__ import annotations

from pydantic import BaseModel, Field


class WhatIfRequest(BaseModel):
    day: int
    step: int = Field(alias="timestep")
    blocked_edge_ids: list[str] = Field(default_factory=list, alias="blocked_edges")
    duration_steps: int | None = None

    model_config = {
        "populate_by_name": True,
    }


class ReportRequest(BaseModel):
    day: int = 0
    scenario: str = "baseline"
    visible_sections: dict[str, bool] = Field(default_factory=dict)
