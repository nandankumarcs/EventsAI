from __future__ import annotations

from typing import Any
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
    clear_fields: list[str] = Field(default_factory=list)
    confidence: float | None = None
    candidates: list[str] = Field(default_factory=list)


class CatalogInquiry(BaseModel):
    status: Literal["answer", "no_input"] = "no_input"
    inquiry_key: str = ""
    message: str = ""
    listed_values: list[str] = Field(default_factory=list)


class SearchSummary(BaseModel):
    domain: Literal["movies", "sports"]
    count: int
    listing_codes: list[str] = Field(default_factory=list)
    result_titles: list[str] = Field(default_factory=list)


class BookingSelectedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_code: str = ""
    title: str = ""
    city: str = ""
    venue_name: str = ""
    event_date: str = ""
    start_at: str = ""
    domain: str = ""
    position: int | None = None
    min_price: int | None = None
    max_price: int | None = None
    sport_type: str | None = None


class BookingSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    thread_id: str | None = None
    booking_reference: str = ""
    event_type: str = ""
    status: str = ""
    event_title: str = ""
    customer_name: str = ""
    customer_email: str = ""
    customer_contact_number: str = ""
    city: str = ""
    venue_name: str = ""
    starts_at: str = ""
    confirmed_at: str = ""


class BookingTurnResolution(BaseModel):
    action: Literal[
        "none",
        "selection_pending",
        "awaiting_user_info",
        "booking_confirmed",
        "booking_cleared",
        "ambiguous",
        "no_match",
    ] = "none"
    message: str = ""
    listing_code: str = ""
    requested_field: str = ""
    selected_event: BookingSelectedEvent = Field(default_factory=BookingSelectedEvent)
    booking: BookingSummaryPayload = Field(default_factory=BookingSummaryPayload)
    candidates: list[str] = Field(default_factory=list)


class GoalState(BaseModel):
    goal_type: Literal["none", "search", "booking"] = "none"
    goal_stage: Literal[
        "no_goal",
        "browsing_results",
        "awaiting_clarification",
        "pending_confirmation",
        "awaiting_user_info",
        "booking_confirmed",
    ] = "no_goal"
    goal_summary: str = ""
    last_open_question: str = ""


class TurnPolicy(BaseModel):
    intent: Literal[
        "task_continue",
        "search_change",
        "booking_change",
        "follow_up_about_results",
        "temporary_distraction",
        "out_of_scope",
        "meta_help",
    ] = "task_continue"
    message: str = ""
    should_keep_results: bool = False


class TurnUpdate(BaseModel):
    assistant_message: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    filter_updates: ActiveFilters = Field(default_factory=ActiveFilters)
    filters_to_clear: list[str] = Field(default_factory=list)
    search_domains: list[Literal["movies", "sports"]] = Field(default_factory=list)
    result_listing_codes: list[str] = Field(default_factory=list)
    tool_trace: list[str] = Field(default_factory=list)
