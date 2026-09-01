from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UpcomingMatchResponse(BaseModel):
    id: int
    vlr_id: int | None

    team1_id: int
    team1_name: str

    team2_id: int
    team2_name: str

    event_name: str | None
    stage: str | None
    status: str
    scheduled_at: datetime


class ForecastCreate(BaseModel):
    match_id: int

    source_type: Literal[
        "human",
        "model",
        "market",
    ]

    source_key: str = Field(
        min_length=1,
        max_length=150,
    )

    team1_win_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    rationale: str | None = Field(
        default=None,
        max_length=1000,
    )


class ForecastResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    match_id: int

    team1_id: int
    team2_id: int

    source_type: str
    source_key: str

    team1_win_probability: float
    rationale: str | None

    created_at: datetime
    lock_time: datetime