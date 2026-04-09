from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from apps.agents.schemas import ActiveFilters, CatalogInquiry, FilterResolution
from apps.events.filter_tools import (
    get_all_event_types,
    get_available_movie_cast_members,
    get_available_movie_certifications,
    get_available_movie_content_origins,
    get_available_movie_directors,
    get_available_movie_formats,
    get_available_movie_franchises,
    get_available_movie_genres,
    get_available_movie_languages,
    get_available_movie_locations,
    get_available_movie_titles,
    get_available_movie_venues,
    get_available_sport_away_teams,
    get_available_sport_competition_stages,
    get_available_sport_featured_athletes,
    get_available_sport_format_labels,
    get_available_sport_home_teams,
    get_available_sport_locations,
    get_available_sport_match_numbers,
    get_available_sport_organizers,
    get_available_sport_participant_names,
    get_available_sport_season_labels,
    get_available_sport_teams,
    get_available_sport_tournaments,
    get_available_sport_types,
    get_available_sport_venues,
)
from apps.events.resolver_utils import (
    build_calendar_date,
    build_date_range,
    build_time_window,
    get_named_time_bucket,
    get_temporal_reference,
    normalize_clock_time,
    resolve_weekday_date,
    shift_iso_date,
)

logger = logging.getLogger(__name__)


@dataclass
class TurnResolution:
    updates: ActiveFilters
    tool_trace: list[str]
    clear_fields: list[str] = field(default_factory=list)
    issues: list["ResolutionIssue"] = field(default_factory=list)


@dataclass
class ResolutionIssue:
    status: Literal["no_match", "ambiguous"]
    trace_name: str
    filter_label: str
    message: str
    candidates: list[str]


def get_chat_model(*, resolver: bool = False) -> ChatOpenAI:
    from django.conf import settings

    model_name = (
        getattr(settings, "OPENAI_RESOLVER_MODEL", "gpt-4.1-mini")
        if resolver
        else getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    )
    return ChatOpenAI(model=model_name, temperature=0)


@lru_cache(maxsize=1)
def _build_event_type_agent():
    @tool("get_all_event_types")
    def available_event_types() -> list[str]:
        """Return the event types currently available in the platform."""
        return get_all_event_types()

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[available_event_types],
        response_format=ToolStrategy(FilterResolution),
        system_prompt=(
            "You resolve event type filters for a booking request.\n"
            "You must call get_all_event_types before deciding.\n"
            "Return only canonical values returned by that tool in active_filters_partial.event_types.\n"
            "Do not invent labels. Do not explain outside the schema.\n"
            "If the user did not express a clear event type, return status no_input."
        ),
    )


@lru_cache(maxsize=1)
def _build_location_agent():
    @tool("get_movie_locations")
    def movie_locations() -> list[str]:
        """Return all available movie cities."""
        return get_available_movie_locations()

    @tool("get_sport_locations")
    def sport_locations() -> list[str]:
        """Return all available sport cities."""
        return get_available_sport_locations()

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[movie_locations, sport_locations],
        response_format=ToolStrategy(FilterResolution),
        system_prompt=(
            "You resolve city filters from the user request.\n"
            "The user message is provided as JSON with user_message, allowed_domains, and current_filters.\n"
            "You must inspect the available city tools before deciding.\n"
            "Return only exact canonical city values from the tool outputs in active_filters_partial.cities.\n"
            "Map informal wording to the closest canonical city only when it is clearly the user's intent.\n"
            "Do not return lowercase variants. Do not invent cities. Do not infer venues or teams from a city mention.\n"
            "If the user asks to remove, exclude, or go outside the current city filter, return status resolved with clear_fields set to ['cities'] and leave active_filters_partial.cities empty.\n"
            "If the user replaces one city with another, return only the replacement city value.\n"
        ),
    )


@lru_cache(maxsize=1)
def _build_temporal_agent():
    @tool("get_temporal_reference")
    def temporal_reference_tool(reference_date: str) -> dict[str, object]:
        """Return the reference date plus week and month boundaries for calendar calculations."""
        return get_temporal_reference(reference_date=reference_date)

    @tool("resolve_weekday_date")
    def resolve_weekday_date_tool(reference_date: str, weekday_name: str, scope: str = "upcoming") -> str:
        """Resolve a weekday into an ISO date. Scope can be upcoming, this_week, or next_week."""
        return resolve_weekday_date(
            reference_date=reference_date,
            weekday_name=weekday_name,
            scope=scope,
        )

    @tool("build_calendar_date")
    def build_calendar_date_tool(year: int, month: int, day: int) -> str:
        """Build an ISO date from year, month, and day values."""
        return build_calendar_date(year=year, month=month, day=day)

    @tool("shift_iso_date")
    def shift_iso_date_tool(date_value: str, days: int) -> str:
        """Shift an ISO date by a positive or negative number of days."""
        return shift_iso_date(date_value=date_value, days=days)

    @tool("build_date_range")
    def build_date_range_tool(start_date: str | None = None, end_date: str | None = None) -> dict[str, str | None]:
        """Create a date range payload with date_from and date_to."""
        return build_date_range(start_date=start_date, end_date=end_date)

    @tool("normalize_clock_time")
    def normalize_clock_time_tool(time_text: str) -> dict[str, str]:
        """Normalize a time phrase like '7pm' or '7:30 pm' into HH:MM:SS."""
        return normalize_clock_time(time_text=time_text)

    @tool("build_time_window")
    def build_time_window_tool(anchor_time: str, radius_minutes: int = 60) -> dict[str, str]:
        """Build a practical time window around an anchor time."""
        return build_time_window(anchor_time=anchor_time, radius_minutes=radius_minutes)

    @tool("get_named_time_bucket")
    def get_named_time_bucket_tool(label: str) -> dict[str, str]:
        """Return a standard time range for a named period like morning, afternoon, evening, or night."""
        return get_named_time_bucket(label=label)

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[
            temporal_reference_tool,
            resolve_weekday_date_tool,
            build_calendar_date_tool,
            shift_iso_date_tool,
            build_date_range_tool,
            normalize_clock_time_tool,
            build_time_window_tool,
            get_named_time_bucket_tool,
        ],
        response_format=ToolStrategy(FilterResolution),
        system_prompt=(
            "You resolve temporal filters from the user request.\n"
            "The user message is provided as JSON with user_message, reference_date, and current_filters.\n"
            "You must use tools for any calendar or clock calculation. Do not do date math in your head.\n"
            "Use exact-date mode for discrete dates like 'today', 'tomorrow', 'this sunday', 'sunday or monday', or named weekdays.\n"
            "In exact-date mode, populate active_filters_partial.event_dates, set clear_fields to ['date_from', 'date_to'], and leave date_from/date_to empty.\n"
            "Use range mode for phrases like 'after', 'before', 'from', 'until', 'next week', 'this week', 'next month', or 'after 13th this month'.\n"
            "In range mode, populate date_from/date_to, set clear_fields to ['event_dates'], and leave event_dates empty.\n"
            "For 'after X', date_from should be the first included day after X unless the user explicitly says 'on or after'.\n"
            "For 'around 7pm' or similar exact times, normalize the time first and then build a practical window.\n"
            "For broad periods like evening or night, use the named time bucket tool.\n"
            "If the user asks to remove a date, day, date range, or time filter, return status resolved with the matching clear_fields and no replacement values.\n"
            "Never return event_dates together with date_from/date_to in the same response.\n"
            "Return only event_dates, date_from, date_to, start_time_from, and start_time_to in active_filters_partial.\n"
            "If the message contains no temporal intent, return status no_input.\n"
            "Return no_input if the message contains no temporal intent."
        ),
    )


@lru_cache(maxsize=1)
def _build_movie_filter_agent():
    @tool("get_movie_titles")
    def movie_titles() -> list[str]:
        """Return movie titles currently available."""
        return get_available_movie_titles()

    @tool("get_movie_genres")
    def movie_genres() -> list[str]:
        """Return movie genres currently available."""
        return get_available_movie_genres()

    @tool("get_movie_cast_members")
    def movie_cast_members() -> list[str]:
        """Return movie cast members currently available."""
        return get_available_movie_cast_members()

    @tool("get_movie_directors")
    def movie_directors() -> list[str]:
        """Return movie directors currently available."""
        return get_available_movie_directors()

    @tool("get_movie_certifications")
    def movie_certifications() -> list[str]:
        """Return movie certifications currently available."""
        return get_available_movie_certifications()

    @tool("get_movie_languages")
    def movie_languages() -> list[str]:
        """Return movie languages currently available."""
        return get_available_movie_languages()

    @tool("get_movie_venues")
    def movie_venues() -> list[str]:
        """Return movie venues currently available."""
        return get_available_movie_venues()

    @tool("get_movie_formats")
    def movie_formats() -> list[str]:
        """Return movie formats currently available."""
        return get_available_movie_formats()

    @tool("get_movie_franchises")
    def movie_franchises() -> list[str]:
        """Return movie franchises currently available."""
        return get_available_movie_franchises()

    @tool("get_movie_content_origins")
    def movie_content_origins() -> list[str]:
        """Return movie content origin labels currently available."""
        return get_available_movie_content_origins()

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[
            movie_titles,
            movie_genres,
            movie_cast_members,
            movie_directors,
            movie_certifications,
            movie_languages,
            movie_venues,
            movie_formats,
            movie_franchises,
            movie_content_origins,
        ],
        response_format=ToolStrategy(FilterResolution),
        system_prompt=(
            "You resolve movie-specific filters from the user request.\n"
            "The user message is provided as JSON with user_message and current_filters.\n"
            "You must rely on the tool outputs and return only exact canonical values from them.\n"
            "Only resolve values the user explicitly requested or clearly described.\n"
            "Do not infer a venue, title, genre, or language from a city mention alone.\n"
            "If the user explicitly removes a movie filter like language, venue, genre, format, or title, return status resolved with the relevant clear_fields and no replacement value for that field.\n"
            "Return titles, genres, cast_members, directors, certifications, languages, venue_names, formats, franchises, and content_origins in active_filters_partial.\n"
            "If the message contains no movie-specific filter intent, return no_input."
        ),
    )


@lru_cache(maxsize=1)
def _build_sport_filter_agent():
    @tool("get_sport_types")
    def sport_types() -> list[str]:
        """Return sport types currently available."""
        return get_available_sport_types()

    @tool("get_sport_tournaments")
    def sport_tournaments() -> list[str]:
        """Return sport tournaments currently available."""
        return get_available_sport_tournaments()

    @tool("get_sport_season_labels")
    def sport_season_labels() -> list[str]:
        """Return sport season labels currently available."""
        return get_available_sport_season_labels()

    @tool("get_sport_competition_stages")
    def sport_competition_stages() -> list[str]:
        """Return sport competition stages currently available."""
        return get_available_sport_competition_stages()

    @tool("get_sport_format_labels")
    def sport_format_labels() -> list[str]:
        """Return sport format labels currently available."""
        return get_available_sport_format_labels()

    @tool("get_sport_home_teams")
    def sport_home_teams() -> list[str]:
        """Return sport home teams currently available."""
        return get_available_sport_home_teams()

    @tool("get_sport_away_teams")
    def sport_away_teams() -> list[str]:
        """Return sport away teams currently available."""
        return get_available_sport_away_teams()

    @tool("get_sport_teams")
    def sport_teams() -> list[str]:
        """Return sport teams currently available."""
        return get_available_sport_teams()

    @tool("get_sport_participant_names")
    def sport_participant_names() -> list[str]:
        """Return sport participant names currently available."""
        return get_available_sport_participant_names()

    @tool("get_sport_venues")
    def sport_venues() -> list[str]:
        """Return sport venues currently available."""
        return get_available_sport_venues()

    @tool("get_sport_featured_athletes")
    def sport_athletes() -> list[str]:
        """Return sport athletes currently available."""
        return get_available_sport_featured_athletes()

    @tool("get_sport_organizers")
    def sport_organizers() -> list[str]:
        """Return sport organizers currently available."""
        return get_available_sport_organizers()

    @tool("get_sport_match_numbers")
    def sport_match_numbers() -> list[int]:
        """Return sport match numbers currently available."""
        return get_available_sport_match_numbers()

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[
            sport_types,
            sport_tournaments,
            sport_season_labels,
            sport_competition_stages,
            sport_format_labels,
            sport_home_teams,
            sport_away_teams,
            sport_teams,
            sport_participant_names,
            sport_venues,
            sport_athletes,
            sport_organizers,
            sport_match_numbers,
        ],
        response_format=ToolStrategy(FilterResolution),
        system_prompt=(
            "You resolve sport-specific filters from the user request.\n"
            "The user message is provided as JSON with user_message and current_filters.\n"
            "You must rely on the tool outputs and return only exact canonical values from them.\n"
            "Only resolve a sport type, tournament, team, venue, or athlete when the user explicitly requests it or clearly describes it.\n"
            "Do not infer teams or venues from a city mention. For example, a message like 'Mumbai works better' updates city only and should not set teams or venues.\n"
            "If the user explicitly removes a sports filter like sport type, tournament, team, or venue, return status resolved with the relevant clear_fields and no replacement value for that field.\n"
            "Return sport_types, tournament_names, season_labels, competition_stages, format_labels, home_teams, away_teams, teams, participant_names, venue_names, featured_athletes, organizers, and match_numbers in active_filters_partial.\n"
            "If the message contains no sport-specific filter intent, return no_input."
        ),
    )


@lru_cache(maxsize=1)
def _build_sport_catalog_agent():
    @tool("get_sport_types")
    def sport_types() -> list[str]:
        """Return sport types currently available."""
        return get_available_sport_types()

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[sport_types],
        response_format=ToolStrategy(CatalogInquiry),
        system_prompt=(
            "You detect when the user is asking an informational catalog question about available sports.\n"
            "The user message is provided as JSON with user_message.\n"
            "You must call get_sport_types before answering.\n"
            "Return status answer only when the user is asking what sports are available, what other sports exist, or asking for alternatives/options without selecting one.\n"
            "When you return answer, set inquiry_key to 'sport_types' and include the canonical sport type values from the tool in listed_values.\n"
            "Do not treat that question as a filter selection.\n"
            "If the user is choosing or changing a sport filter, return no_input."
        ),
    )


def invoke_event_type_resolver(user_message: str) -> FilterResolution:
    return _invoke_filter_resolution_agent(
        agent=_build_event_type_agent(),
        user_content=json.dumps({"user_message": user_message}),
        trace_name="resolve_event_type",
        allowed_fields={"event_types"},
    )


def invoke_location_resolver(
    user_message: str,
    domains: list[str] | None = None,
    current_filters: ActiveFilters | None = None,
) -> FilterResolution:
    resolution = _invoke_filter_resolution_agent(
        agent=_build_location_agent(),
        user_content=json.dumps(
            {
                "user_message": user_message,
                "allowed_domains": domains or [],
                "current_filters": (current_filters or ActiveFilters()).model_dump(),
            }
        ),
        trace_name="resolve_location",
        allowed_fields={"cities"},
    )
    if len(resolution.active_filters_partial.cities) > 2:
        return FilterResolution(status="no_input", message="Location was not explicitly narrowed.")
    return resolution


def invoke_temporal_resolver(user_message: str, reference_date: str, current_filters: ActiveFilters | None = None) -> FilterResolution:
    resolution = _invoke_filter_resolution_agent(
        agent=_build_temporal_agent(),
        user_content=json.dumps(
            {
                "user_message": user_message,
                "reference_date": reference_date,
                "current_filters": (current_filters or ActiveFilters()).model_dump(),
            }
        ),
        trace_name="resolve_temporal",
        allowed_fields={
            "event_dates",
            "date_from",
            "date_to",
            "start_time_from",
            "start_time_to",
        },
    )
    return _sanitize_temporal_resolution(resolution)


def invoke_movie_filter_resolver(user_message: str, current_filters: ActiveFilters | None = None) -> FilterResolution:
    resolution = _invoke_filter_resolution_agent(
        agent=_build_movie_filter_agent(),
        user_content=json.dumps(
            {
                "user_message": user_message,
                "current_filters": (current_filters or ActiveFilters()).model_dump(),
            }
        ),
        trace_name="resolve_movie_filters",
        allowed_fields={
            "titles",
            "genres",
            "cast_members",
            "directors",
            "certifications",
            "languages",
            "venue_names",
            "formats",
            "franchises",
            "content_origins",
        },
    )
    return _sanitize_explicit_entity_fields(
        resolution=resolution,
        user_message=user_message,
        explicit_fields={"titles", "venue_names", "cast_members", "directors", "franchises"},
    )


def invoke_sport_filter_resolver(user_message: str, current_filters: ActiveFilters | None = None) -> FilterResolution:
    resolution = _invoke_filter_resolution_agent(
        agent=_build_sport_filter_agent(),
        user_content=json.dumps(
            {
                "user_message": user_message,
                "current_filters": (current_filters or ActiveFilters()).model_dump(),
            }
        ),
        trace_name="resolve_sport_filters",
        allowed_fields={
            "sport_types",
            "tournament_names",
            "season_labels",
            "competition_stages",
            "format_labels",
            "home_teams",
            "away_teams",
            "teams",
            "participant_names",
            "venue_names",
            "featured_athletes",
            "organizers",
            "match_numbers",
        },
    )
    return _sanitize_explicit_entity_fields(
        resolution=resolution,
        user_message=user_message,
        explicit_fields={
            "home_teams",
            "away_teams",
            "teams",
            "participant_names",
            "venue_names",
            "featured_athletes",
            "organizers",
        },
    )


def invoke_sport_catalog_inquiry(user_message: str) -> CatalogInquiry:
    try:
        response = _build_sport_catalog_agent().invoke(
            {"messages": [{"role": "user", "content": json.dumps({"user_message": user_message})}]}
        )
    except Exception as exc:
        logger.warning("resolve_sport_catalog_inquiry failed: %s", exc)
        return CatalogInquiry(status="no_input")

    structured_response = response.get("structured_response")
    if isinstance(structured_response, CatalogInquiry):
        return structured_response
    if structured_response is not None:
        try:
            return CatalogInquiry.model_validate(structured_response)
        except Exception as exc:
            logger.warning("resolve_sport_catalog_inquiry returned invalid structured response: %s", exc)

    return CatalogInquiry(status="no_input")


def resolve_turn_filters(
    *,
    user_message: str,
    current_filters: ActiveFilters,
    reference_date: str,
) -> TurnResolution:
    trace: list[str] = []
    updates = ActiveFilters()
    clear_fields: list[str] = []
    issues: list[ResolutionIssue] = []
    current_domains = current_filters.event_types
    domain_switched = False
    movie_resolution: FilterResolution | None = None
    sport_resolution: FilterResolution | None = None

    event_type_resolution = invoke_event_type_resolver(user_message)
    trace.append("resolve_event_type")
    if _should_apply_event_type_resolution(
        resolution=event_type_resolution,
        current_domains=current_domains,
    ):
        updates = _merge_active_filters(updates, _partial_from_resolution(event_type_resolution))
        domain_switched = bool(updates.event_types and updates.event_types != current_domains)
        _append_resolution_issue(
            issues=issues,
            resolution=event_type_resolution,
            trace_name="resolve_event_type",
            filter_label="event type",
        )

    effective_domains = updates.event_types or current_domains

    if not effective_domains:
        movie_resolution = invoke_movie_filter_resolver(user_message, current_filters=current_filters)
        trace.append("resolve_movie_filters")
        sport_resolution = invoke_sport_filter_resolver(user_message, current_filters=current_filters)
        trace.append("resolve_sport_filters")

        inferred_domains = _infer_domains_from_specific_resolvers(
            movie_resolution=movie_resolution,
            sport_resolution=sport_resolution,
        )
        if inferred_domains:
            effective_domains = inferred_domains
            updates = _merge_active_filters(
                updates,
                ActiveFilters(event_types=inferred_domains),
            )
            clear_fields.extend(["event_types"])
            if inferred_domains == ["movies"]:
                updates = _merge_active_filters(updates, _partial_from_resolution(movie_resolution))
                clear_fields = _merge_clear_fields(clear_fields, movie_resolution.clear_fields)
            if inferred_domains == ["sports"]:
                updates = _merge_active_filters(updates, _partial_from_resolution(sport_resolution))
                clear_fields = _merge_clear_fields(clear_fields, sport_resolution.clear_fields)

    location_resolution = invoke_location_resolver(user_message, effective_domains or None, current_filters)
    location_resolution = _apply_location_clear_fallback(
        resolution=location_resolution,
        user_message=user_message,
        current_filters=current_filters,
    )
    trace.append("resolve_location")
    updates = _merge_active_filters(updates, _partial_from_resolution(location_resolution))
    clear_fields = _merge_clear_fields(clear_fields, location_resolution.clear_fields)
    _append_resolution_issue(
        issues=issues,
        resolution=location_resolution,
        trace_name="resolve_location",
        filter_label="location",
    )

    temporal_resolution = invoke_temporal_resolver(user_message, reference_date, current_filters)
    trace.append("resolve_temporal")
    updates = _merge_active_filters(updates, _partial_from_resolution(temporal_resolution))
    clear_fields = _merge_clear_fields(clear_fields, temporal_resolution.clear_fields)

    if "movies" in effective_domains:
        if movie_resolution is None:
            movie_resolution = invoke_movie_filter_resolver(user_message, current_filters=current_filters)
            trace.append("resolve_movie_filters")
        updates = _merge_active_filters(updates, _partial_from_resolution(movie_resolution))
        clear_fields = _merge_clear_fields(clear_fields, movie_resolution.clear_fields)
        _append_resolution_issue(
            issues=issues,
            resolution=movie_resolution,
            trace_name="resolve_movie_filters",
            filter_label="movie filters",
        )

    if "sports" in effective_domains:
        if not domain_switched and _should_run_sport_catalog_inquiry(user_message):
            sport_catalog_inquiry = invoke_sport_catalog_inquiry(user_message)
            if sport_catalog_inquiry.status == "answer":
                trace.append("resolve_sport_catalog_inquiry")
                updates = _merge_active_filters(
                    updates,
                    ActiveFilters(sport_types=sport_catalog_inquiry.listed_values),
                )
                return TurnResolution(updates=updates, tool_trace=trace, clear_fields=clear_fields, issues=issues)

        if sport_resolution is None:
            sport_resolution = invoke_sport_filter_resolver(user_message, current_filters=current_filters)
            trace.append("resolve_sport_filters")
        updates = _merge_active_filters(updates, _partial_from_resolution(sport_resolution))
        clear_fields = _merge_clear_fields(clear_fields, sport_resolution.clear_fields)
        _append_resolution_issue(
            issues=issues,
            resolution=sport_resolution,
            trace_name="resolve_sport_filters",
            filter_label="sports filters",
        )

    return TurnResolution(updates=updates, tool_trace=trace, clear_fields=clear_fields, issues=issues)


def _invoke_filter_resolution_agent(*, agent, user_content: str, trace_name: str, allowed_fields: set[str]) -> FilterResolution:
    try:
        response = agent.invoke({"messages": [{"role": "user", "content": user_content}]})
    except Exception as exc:
        logger.warning("%s failed: %s", trace_name, exc)
        return FilterResolution(status="no_input", message=f"{trace_name} unavailable.")

    structured_response = response.get("structured_response")
    if isinstance(structured_response, FilterResolution):
        return _constrain_resolution(structured_response, allowed_fields)
    if structured_response is not None:
        try:
            return _constrain_resolution(FilterResolution.model_validate(structured_response), allowed_fields)
        except Exception as exc:
            logger.warning("%s returned invalid structured response: %s", trace_name, exc)

    return FilterResolution(status="no_input", message=f"{trace_name} returned no data.")


def _partial_from_resolution(resolution: FilterResolution) -> ActiveFilters:
    if resolution.status != "resolved":
        return ActiveFilters()
    return resolution.active_filters_partial


def _constrain_resolution(resolution: FilterResolution, allowed_fields: set[str]) -> FilterResolution:
    partial_payload = {
        key: value
        for key, value in resolution.active_filters_partial.model_dump().items()
        if key in allowed_fields and value not in (None, [], "")
    }
    clear_fields = [field_name for field_name in resolution.clear_fields if field_name in allowed_fields]
    return FilterResolution(
        status=resolution.status,
        message=resolution.message,
        clear_fields=clear_fields,
        confidence=resolution.confidence,
        candidates=resolution.candidates,
        active_filters_partial=ActiveFilters.model_validate(partial_payload),
    )


def _sanitize_explicit_entity_fields(
    *,
    resolution: FilterResolution,
    user_message: str,
    explicit_fields: set[str],
) -> FilterResolution:
    partial = resolution.active_filters_partial.model_dump()
    for field_name in explicit_fields:
        values = partial.get(field_name) or []
        partial[field_name] = [
            value for value in values if _looks_explicit_in_message(user_message, value)
        ]

    sanitized_partial = ActiveFilters.model_validate(partial)
    has_filters = any(value not in (None, [], "") for value in sanitized_partial.model_dump().values())
    return FilterResolution(
        status=resolution.status if has_filters else "no_input",
        message=resolution.message,
        clear_fields=resolution.clear_fields,
        confidence=resolution.confidence,
        candidates=resolution.candidates,
        active_filters_partial=sanitized_partial,
    )


def _merge_active_filters(base: ActiveFilters, updates: ActiveFilters) -> ActiveFilters:
    merged = base.model_dump()
    for key, value in updates.model_dump().items():
        if value in (None, [], ""):
            continue
        merged[key] = value
    return ActiveFilters.model_validate(merged)


def _merge_clear_fields(base: list[str], extra: list[str]) -> list[str]:
    return list(dict.fromkeys([*base, *extra]))


def _append_resolution_issue(
    *,
    issues: list[ResolutionIssue],
    resolution: FilterResolution,
    trace_name: str,
    filter_label: str,
) -> None:
    if resolution.status not in {"no_match", "ambiguous"}:
        return

    issues.append(
        ResolutionIssue(
            status=resolution.status,
            trace_name=trace_name,
            filter_label=filter_label,
            message=resolution.message,
            candidates=list(resolution.candidates or []),
        )
    )


def _should_apply_event_type_resolution(
    *,
    resolution: FilterResolution,
    current_domains: list[str],
) -> bool:
    if len(current_domains) != 1:
        return True

    current_domain = current_domains[0]
    resolved_domains = resolution.active_filters_partial.event_types

    if resolution.status == "resolved":
        return bool(resolved_domains and resolved_domains != [current_domain])

    return False


def _sanitize_temporal_resolution(resolution: FilterResolution) -> FilterResolution:
    partial = resolution.active_filters_partial.model_dump()
    clear_fields = list(resolution.clear_fields)

    has_event_dates = bool(partial.get("event_dates"))
    has_date_range = bool(partial.get("date_from") or partial.get("date_to"))

    if has_event_dates:
        partial["date_from"] = None
        partial["date_to"] = None
        clear_fields = _merge_clear_fields(clear_fields, ["date_from", "date_to"])
    elif has_date_range:
        partial["event_dates"] = []
        clear_fields = _merge_clear_fields(clear_fields, ["event_dates"])

    sanitized_partial = ActiveFilters.model_validate(partial)
    has_filters = any(value not in (None, [], "") for value in sanitized_partial.model_dump().values())
    return FilterResolution(
        status=resolution.status if has_filters or clear_fields else "no_input",
        message=resolution.message,
        clear_fields=clear_fields,
        confidence=resolution.confidence,
        candidates=resolution.candidates,
        active_filters_partial=sanitized_partial,
    )


def _apply_location_clear_fallback(
    *,
    resolution: FilterResolution,
    user_message: str,
    current_filters: ActiveFilters,
) -> FilterResolution:
    if resolution.clear_fields or resolution.status == "resolved":
        return resolution

    normalized_message = _normalize_text(user_message)
    removal_phrases = ("outside", "not in", "without", "exclude")
    if not any(phrase in normalized_message for phrase in removal_phrases):
        return resolution

    for city in current_filters.cities:
        if _normalize_text(city) in normalized_message:
            return FilterResolution(status="resolved", clear_fields=["cities"])

    return resolution


def _should_run_sport_catalog_inquiry(user_message: str) -> bool:
    normalized_message = _normalize_text(user_message)
    if "sport" not in normalized_message:
        return False

    inquiry_cues = (
        "what",
        "which",
        "other",
        "available",
        "options",
        "alternatives",
        "do we have",
        "do you have",
    )
    return any(cue in normalized_message for cue in inquiry_cues)


def _infer_domains_from_specific_resolvers(
    *,
    movie_resolution: FilterResolution,
    sport_resolution: FilterResolution,
) -> list[str]:
    movie_has_filters = _resolution_has_filters(movie_resolution)
    sport_has_filters = _resolution_has_filters(sport_resolution)

    if movie_has_filters and not sport_has_filters:
        return ["movies"]
    if sport_has_filters and not movie_has_filters:
        return ["sports"]
    return []


def _resolution_has_filters(resolution: FilterResolution) -> bool:
    return any(
        value not in (None, [], "")
        for value in resolution.active_filters_partial.model_dump().values()
    )


def _looks_explicit_in_message(user_message: str, candidate_value: str) -> bool:
    normalized_message = _normalize_text(user_message)
    normalized_candidate = _normalize_text(candidate_value)

    if normalized_candidate in normalized_message:
        return True

    candidate_tokens = normalized_candidate.split()
    if len(candidate_tokens) < 2:
        return False

    matched_tokens = [
        token for token in candidate_tokens
        if re.search(rf"\b{re.escape(token)}\b", normalized_message)
    ]
    return len(matched_tokens) >= 2


def _normalize_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip()
