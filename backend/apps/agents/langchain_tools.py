from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from apps.agents.schemas import ActiveFilters, FilterResolution
from apps.events.filter_tools import (
    get_all_event_types,
    get_available_movie_genres,
    get_available_movie_languages,
    get_available_movie_locations,
    get_available_movie_titles,
    get_available_movie_venues,
    get_available_sport_featured_athletes,
    get_available_sport_locations,
    get_available_sport_teams,
    get_available_sport_tournaments,
    get_available_sport_types,
    get_available_sport_venues,
)
from apps.events.resolver_utils import normalize_temporal_expression

logger = logging.getLogger(__name__)


@dataclass
class TurnResolution:
    updates: ActiveFilters
    tool_trace: list[str]


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
            "The user message is provided as JSON with user_message and allowed_domains.\n"
            "You must inspect the available city tools before deciding.\n"
            "Return only exact canonical city values from the tool outputs in active_filters_partial.cities.\n"
            "Map informal wording to the closest canonical city only when it is clearly the user's intent.\n"
            "Do not return lowercase variants. Do not invent cities. Do not infer venues or teams from a city mention."
        ),
    )


@lru_cache(maxsize=1)
def _build_temporal_agent():
    @tool("normalize_temporal_expression")
    def normalize_temporal_tool(text: str, reference_date: str) -> dict[str, object]:
        """Resolve relative dates and times using an ISO reference date."""
        return normalize_temporal_expression(text, reference_date=date.fromisoformat(reference_date))

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[normalize_temporal_tool],
        response_format=ToolStrategy(FilterResolution),
        system_prompt=(
            "You resolve temporal filters from the user request.\n"
            "You must call normalize_temporal_expression when the request mentions a day, date, period, or time.\n"
            "Return event_dates, start_time_from, and start_time_to in active_filters_partial when present.\n"
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

    @tool("get_movie_languages")
    def movie_languages() -> list[str]:
        """Return movie languages currently available."""
        return get_available_movie_languages()

    @tool("get_movie_venues")
    def movie_venues() -> list[str]:
        """Return movie venues currently available."""
        return get_available_movie_venues()

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[movie_titles, movie_genres, movie_languages, movie_venues],
        response_format=ToolStrategy(FilterResolution),
        system_prompt=(
            "You resolve movie-specific filters from the user request.\n"
            "You must rely on the tool outputs and return only exact canonical values from them.\n"
            "Only resolve values the user explicitly requested or clearly described.\n"
            "Do not infer a venue, title, genre, or language from a city mention alone.\n"
            "Return titles, genres, languages, and venue_names in active_filters_partial.\n"
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

    @tool("get_sport_teams")
    def sport_teams() -> list[str]:
        """Return sport teams currently available."""
        return get_available_sport_teams()

    @tool("get_sport_venues")
    def sport_venues() -> list[str]:
        """Return sport venues currently available."""
        return get_available_sport_venues()

    @tool("get_sport_featured_athletes")
    def sport_athletes() -> list[str]:
        """Return sport athletes currently available."""
        return get_available_sport_featured_athletes()

    return create_agent(
        model=get_chat_model(resolver=True),
        tools=[sport_types, sport_tournaments, sport_teams, sport_venues, sport_athletes],
        response_format=ToolStrategy(FilterResolution),
        system_prompt=(
            "You resolve sport-specific filters from the user request.\n"
            "You must rely on the tool outputs and return only exact canonical values from them.\n"
            "Only resolve a sport type, tournament, team, venue, or athlete when the user explicitly requests it or clearly describes it.\n"
            "Do not infer teams or venues from a city mention. For example, a message like 'Mumbai works better' updates city only and should not set teams or venues.\n"
            "Return sport_types, tournament_names, teams, venue_names, and featured_athletes in active_filters_partial.\n"
            "If the message contains no sport-specific filter intent, return no_input."
        ),
    )


def invoke_event_type_resolver(user_message: str) -> FilterResolution:
    return _invoke_filter_resolution_agent(
        agent=_build_event_type_agent(),
        user_content=json.dumps({"user_message": user_message}),
        trace_name="resolve_event_type",
        allowed_fields={"event_types"},
    )


def invoke_location_resolver(user_message: str, domains: list[str] | None = None) -> FilterResolution:
    resolution = _invoke_filter_resolution_agent(
        agent=_build_location_agent(),
        user_content=json.dumps({"user_message": user_message, "allowed_domains": domains or []}),
        trace_name="resolve_location",
        allowed_fields={"cities"},
    )
    if len(resolution.active_filters_partial.cities) > 2:
        return FilterResolution(status="no_input", message="Location was not explicitly narrowed.")
    return resolution


def invoke_temporal_resolver(user_message: str, reference_date: str) -> FilterResolution:
    normalized = normalize_temporal_expression(user_message, reference_date=date.fromisoformat(reference_date))
    has_temporal_filters = bool(
        normalized["dates"]
        or normalized["time_range"]["start"]
        or normalized["time_range"]["end"]
    )
    return FilterResolution(
        status="resolved" if has_temporal_filters else "no_input",
        message="Resolved temporal filters.",
        confidence=0.98 if has_temporal_filters else 0.0,
        active_filters_partial=ActiveFilters(
            event_dates=normalized["dates"],
            start_time_from=normalized["time_range"]["start"],
            start_time_to=normalized["time_range"]["end"],
        ),
    )


def invoke_movie_filter_resolver(user_message: str) -> FilterResolution:
    resolution = _invoke_filter_resolution_agent(
        agent=_build_movie_filter_agent(),
        user_content=json.dumps({"user_message": user_message}),
        trace_name="resolve_movie_filters",
        allowed_fields={"titles", "genres", "languages", "venue_names"},
    )
    return _sanitize_explicit_entity_fields(
        resolution=resolution,
        user_message=user_message,
        explicit_fields={"titles", "venue_names"},
    )


def invoke_sport_filter_resolver(user_message: str) -> FilterResolution:
    resolution = _invoke_filter_resolution_agent(
        agent=_build_sport_filter_agent(),
        user_content=json.dumps({"user_message": user_message}),
        trace_name="resolve_sport_filters",
        allowed_fields={"sport_types", "tournament_names", "teams", "venue_names", "featured_athletes"},
    )
    return _sanitize_explicit_entity_fields(
        resolution=resolution,
        user_message=user_message,
        explicit_fields={"teams", "venue_names", "featured_athletes"},
    )


def resolve_turn_filters(
    *,
    user_message: str,
    current_filters: ActiveFilters,
    reference_date: str,
) -> TurnResolution:
    trace: list[str] = []
    updates = ActiveFilters()

    event_type_resolution = invoke_event_type_resolver(user_message)
    trace.append("resolve_event_type")
    updates = _merge_active_filters(updates, _partial_from_resolution(event_type_resolution))

    effective_domains = updates.event_types or current_filters.event_types

    location_resolution = invoke_location_resolver(user_message, effective_domains or None)
    trace.append("resolve_location")
    updates = _merge_active_filters(updates, _partial_from_resolution(location_resolution))

    temporal_resolution = invoke_temporal_resolver(user_message, reference_date)
    trace.append("resolve_temporal")
    updates = _merge_active_filters(updates, _partial_from_resolution(temporal_resolution))

    if "movies" in effective_domains:
        movie_resolution = invoke_movie_filter_resolver(user_message)
        trace.append("resolve_movie_filters")
        updates = _merge_active_filters(updates, _partial_from_resolution(movie_resolution))

    if "sports" in effective_domains:
        sport_resolution = invoke_sport_filter_resolver(user_message)
        trace.append("resolve_sport_filters")
        updates = _merge_active_filters(updates, _partial_from_resolution(sport_resolution))

    return TurnResolution(updates=updates, tool_trace=trace)


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
    return FilterResolution(
        status=resolution.status,
        message=resolution.message,
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
