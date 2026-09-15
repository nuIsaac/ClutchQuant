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

    # Internal model/market jobs write directly; public submissions cannot
    # claim those namespaces. Human identity authentication is separate work.
    source_type: Literal["human"]

    source_key: str = Field(
        min_length=1,
        max_length=150,
        pattern=r"^human:[A-Za-z0-9][A-Za-z0-9_.:-]*$",
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
    model_run_id: str | None = None
    match_id: int

    team1_id: int
    team2_id: int

    source_type: str
    source_key: str

    team1_win_probability: float
    rationale: str | None

    created_at: datetime
    lock_time: datetime



class ForecastScoreResponse(BaseModel):
    forecast_id: int
    match_id: int

    source_type: str
    source_key: str

    team1_id: int
    team1_name: str
    team2_id: int
    team2_name: str

    team1_win_probability: float

    team1_score: int
    team2_score: int
    team1_outcome: int

    brier_score: float
    log_loss: float


class ResearchPreviewResponse(BaseModel):
    source_key: str
    team1_win_probability: float = Field(ge=0, le=1)
    computed_at: datetime
    history_count: int
    dataset_sha256: str
    base_dataset_sha256: str
    base_exported_at: datetime
    team1_unseen: bool
    team2_unseen: bool
    team1_rating: float
    team2_rating: float
    team1_history_count: int
    team2_history_count: int
    availability: Literal["UNKNOWN"]
    used_for_prospective_scoring: Literal[False]


class UpcomingForecastResponse(UpcomingMatchResponse):
    forecasts: list[ForecastResponse]
    current_preview: ResearchPreviewResponse | None = None
