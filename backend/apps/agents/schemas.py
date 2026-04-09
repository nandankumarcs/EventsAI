from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ActiveFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_types: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    venue_names: list[str] = Field(default_factory=list)
    event_dates: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    start_time_from: str | None = None
    start_time_to: str | None = None
    languages: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    cast_members: list[str] = Field(default_factory=list)
    directors: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    franchises: list[str] = Field(default_factory=list)
    content_origins: list[str] = Field(default_factory=list)
    sport_types: list[str] = Field(default_factory=list)
    tournament_names: list[str] = Field(default_factory=list)
    season_labels: list[str] = Field(default_factory=list)
    competition_stages: list[str] = Field(default_factory=list)
    format_labels: list[str] = Field(default_factory=list)
    home_teams: list[str] = Field(default_factory=list)
    away_teams: list[str] = Field(default_factory=list)
    teams: list[str] = Field(default_factory=list)
    participant_names: list[str] = Field(default_factory=list)
    featured_athletes: list[str] = Field(default_factory=list)
    organizers: list[str] = Field(default_factory=list)
    match_numbers: list[int] = Field(default_factory=list)


class FilterResolution(BaseModel):
    status: Literal["resolved", "no_match", "ambiguous", "no_input"] = "no_input"
    message: str = ""
    active_filters_partial: ActiveFilters = Field(default_factory=ActiveFilters)
    confidence: float | None = None
    candidates: list[str] = Field(default_factory=list)


class SearchSummary(BaseModel):
    domain: Literal["movies", "sports"]
    count: int
    listing_codes: list[str] = Field(default_factory=list)
    result_titles: list[str] = Field(default_factory=list)


class TurnUpdate(BaseModel):
    assistant_message: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    filter_updates: ActiveFilters = Field(default_factory=ActiveFilters)
    filters_to_clear: list[str] = Field(default_factory=list)
    search_domains: list[Literal["movies", "sports"]] = Field(default_factory=list)
    result_listing_codes: list[str] = Field(default_factory=list)
    tool_trace: list[str] = Field(default_factory=list)
