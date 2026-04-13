from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from apps.agents.schemas import ActiveFilters, BookingTurnResolution, CatalogInquiry, FilterResolution
from apps.agents.schemas import GoalState, TurnPolicy
from apps.bookings.services import (
    attempt_thread_pending_booking_confirmation,
    BookingFlowError,
    cancel_thread_pending_booking,
    capture_thread_booking_user_info,
    FIELD_PROMPTS,
    get_current_thread_result_context,
    get_pending_thread_booking,
    get_thread_booking_context,
    mark_thread_pending_booking,
    select_thread_pending_booking,
)
from apps.chats.models import ChatThread, ThreadFilter
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


def get_chat_model(*, resolver: bool = False):
    from django.conf import settings

    # Check if Ollama is enabled
    use_ollama = getattr(settings, "USE_OLLAMA", False)
    ollama_host = getattr(settings, "OLLAMA_HOST", "http://127.0.0.1:11434")
    ollama_model = getattr(settings, "OLLAMA_MODEL", "gemma4:e2b")

    if use_ollama:
        return ChatOllama(
            model=ollama_model,
            base_url=ollama_host,
            temperature=0,
        )

    model_name = (
        getattr(settings, "OPENAI_RESOLVER_MODEL", "gpt-4.1-mini")
        if resolver
        else getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    )
    return ChatOpenAI(model=model_name, temperature=0)


def generate_dynamic_thread_title(history_messages: list[str]) -> str:
    llm = get_chat_model(resolver=True)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a concise title generator. Based on the user's chat history, provide a 2 to 5 word title that best summarizes the main topic of the conversation. Do not use quotes, punctuation, or generic terms like 'Chat about'."),
        ("user", "Conversation history:\n{history}")
    ])
    
    chain = prompt | llm
    try:
        response = chain.invoke({"history": "\n".join(history_messages[-5:])})
        return response.content.strip(' "”\'')[:255]
    except Exception as e:
        logger.error(f"Failed to generate thread title: {e}")
        return "New thread"


@lru_cache(maxsize=1)
def _build_event_type_agent():
    @tool("get_all_event_types")
    def available_event_types() -> list[str]:
        """Return the event types currently available in the platform."""
        return get_all_event_types()

    return create_react_agent(
        model=get_chat_model(resolver=True),
        tools=[available_event_types],
        response_format=FilterResolution,
        prompt=(
            "You resolve event type filters for a booking request.\n"
            "You must call get_all_event_types before deciding.\n"
            "Return only canonical values returned by that tool in active_filters_partial.event_types.\n"
            "Do not invent labels. Do not explain outside the schema.\n"
            "If the user did not express a clear event type in the current message, return status no_input.\n"
            "Pure location, date, time, venue, or other filter corrections such as 'Actually Mumbai again', 'No wait Pune', 'Delhi instead', or 'this week not Sunday' are not event-type changes and must return no_input.\n"
            "Do not widen the current domain just because multiple event types exist in the catalog.\n"
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

    return create_react_agent(
        model=get_chat_model(resolver=True),
        tools=[movie_locations, sport_locations],
        response_format=FilterResolution,
        prompt=(
            "You resolve city filters from the user request.\n"
            "The user message is provided as JSON with user_message, allowed_domains, and current_filters.\n"
            "You must inspect the available city tools before deciding.\n"
            "Return only exact canonical city values from the tool outputs in active_filters_partial.cities.\n"
            "Map informal wording to the closest canonical city only when it is clearly the user's intent.\n"
            "Do not return lowercase variants. Do not invent cities. Do not infer venues or teams from a city mention.\n"
            "If the user asks to remove, exclude, or go outside the current city filter, return status resolved with clear_fields set to ['cities'] and leave active_filters_partial.cities empty.\n"
            "If the user says 'all cities', 'any city', 'not just Mumbai', 'not only Mumbai', 'across all cities', or otherwise broadens beyond the current city restriction, return status resolved with clear_fields set to ['cities'] and leave active_filters_partial.cities empty.\n"
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

    return create_react_agent(
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
        response_format=FilterResolution,
        prompt=(
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

    return create_react_agent(
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
        response_format=FilterResolution,
        prompt=(
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

    return create_react_agent(
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
        response_format=FilterResolution,
        prompt=(
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

    return create_react_agent(
        model=get_chat_model(resolver=True),
        tools=[sport_types],
        response_format=CatalogInquiry,
        prompt=(
            "You detect when the user is asking an informational catalog question about available sports.\n"
            "The user message is provided as JSON with user_message.\n"
            "You must call get_sport_types before answering.\n"
            "Return status answer only when the user is asking what sports are available, what other sports exist, or asking for alternatives/options without selecting one.\n"
            "When you return answer, set inquiry_key to 'sport_types' and include the canonical sport type values from the tool in listed_values.\n"
            "Do not treat that question as a filter selection.\n"
            "If the user is choosing or changing a sport filter, return no_input."
        ),
    )


def _get_booking_thread_state(thread_id: str) -> tuple[ChatThread, ThreadFilter]:
    thread = ChatThread.objects.get(id=thread_id)
    thread_filter = ThreadFilter.objects.get(thread=thread)
    return thread, thread_filter


def _booking_tools():
    @tool("get_thread_booking_context")
    def thread_booking_context(thread_id: str) -> dict[str, object]:
        """Return the current booking stage context, filters, and latest visible results for the thread."""
        _thread, thread_filter = _get_booking_thread_state(thread_id)
        return get_thread_booking_context(thread_filter=thread_filter)

    @tool("get_current_thread_result_context")
    def current_thread_result_context(thread_id: str) -> dict[str, object]:
        """Return the ordered result context last shown to the user in the given thread."""
        _thread, thread_filter = _get_booking_thread_state(thread_id)
        return get_current_thread_result_context(thread_filter=thread_filter)

    @tool("get_pending_thread_booking")
    def pending_thread_booking(thread_id: str) -> dict[str, object]:
        """Return the current pending booking selection for the given thread."""
        _thread, thread_filter = _get_booking_thread_state(thread_id)
        return get_pending_thread_booking(thread_filter=thread_filter)

    @tool("mark_thread_pending_booking")
    def mark_pending_booking(thread_id: str, listing_code: str) -> dict[str, object]:
        """Mark a result from the current thread context as the pending booking selection."""
        _thread, thread_filter = _get_booking_thread_state(thread_id)
        return select_thread_pending_booking(thread_filter=thread_filter, listing_code=listing_code)

    @tool("clear_thread_pending_booking")
    def clear_pending_booking(thread_id: str) -> dict[str, object]:
        """Clear the pending booking selection for the given thread."""
        _thread, thread_filter = _get_booking_thread_state(thread_id)
        return cancel_thread_pending_booking(thread_filter=thread_filter)

    @tool("confirm_thread_pending_booking")
    def confirm_pending_booking(thread_id: str) -> dict[str, object]:
        """Confirm the pending selection or return the next required user-info prompt."""
        thread, thread_filter = _get_booking_thread_state(thread_id)
        return attempt_thread_pending_booking_confirmation(
            thread=thread,
            thread_filter=thread_filter,
            confirmed_via="chat_message",
            append_confirmation_message=False,
        )

    @tool("save_thread_booking_user_info")
    def save_pending_booking_user_info(thread_id: str, field_name: str, value: str) -> dict[str, object]:
        """Save one required user-info field for the pending booking in the current thread."""
        _thread, thread_filter = _get_booking_thread_state(thread_id)
        return capture_thread_booking_user_info(
            thread_filter=thread_filter,
            field_name=field_name,
            value=value,
        )

    return {
        "thread_booking_context": thread_booking_context,
        "current_thread_result_context": current_thread_result_context,
        "pending_thread_booking": pending_thread_booking,
        "mark_pending_booking": mark_pending_booking,
        "clear_pending_booking": clear_pending_booking,
        "confirm_pending_booking": confirm_pending_booking,
        "save_pending_booking_user_info": save_pending_booking_user_info,
    }


@lru_cache(maxsize=1)
def _build_booking_selection_chain():
    llm = get_chat_model(resolver=True)
    structured_llm = llm.with_structured_output(BookingTurnResolution)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You handle conversational event selection for booking inside an event booking thread.\n"
                "There is no pending booking before this turn.\n"
                "The user message is provided as JSON with user_message, active_filters, and latest_result_context.\n"
                "Use only latest_result_context.results to resolve references like 'book the second one', 'book the Mumbai one', 'book Kalki', or 'book the Chennai match'. Never invent or search outside it.\n"
                "Treat direct selection phrases as booking-selection requests, including examples like 'book the first one', 'pick the one in Guwahati', 'reserve Kalki', 'पहला वाला बुक करो', and 'इसको बुक करो'. Returning action none for those requests is incorrect.\n"
                "If the user is changing the search instead of choosing a visible result, return action none.\n"
                "Messages like 'Actually Mumbai again', 'No wait Pune', 'Delhi instead', 'this week not Sunday', 'Show cricket matches', 'show movies instead', or 'Bengaluru nahi Chennai' are search changes, not booking-selection requests, unless the user explicitly asks to book or pick a visible result.\n"
                "Do not treat a city, date, domain, or filter correction as a failed attempt to book from the currently visible results.\n"
                "If you can identify exactly one result, return action selection_pending with that listing_code.\n"
                "Never confirm a booking in this step. Never ask for user info in this step. Stop after selection and ask for confirmation.\n"
                "If the user confirms before selecting an event, return action no_match with a message telling them to choose an event first.\n"
                "If the message is not a booking-selection request, return action none.\n"
                "If multiple results could match, return action ambiguous with candidates and a clarification message.\n"
                "If the requested event cannot be matched to the current thread context, return action no_match.\n"
                "This step must work for multilingual or mixed-language user input too.\n"
                "Return a concise user-facing message in all handled actions.\n"
                "Do not invent listing codes."
            ),
            ("user", "{payload}"),
        ]
    )
    return prompt | structured_llm


def _invoke_booking_selection_resolution(*, thread_id: str, user_message: str) -> BookingTurnResolution:
    _thread, thread_filter = _get_booking_thread_state(thread_id)

    try:
        response = _build_booking_selection_chain().invoke(
            {
                "payload": json.dumps(
                    {
                        "user_message": user_message,
                        "active_filters": thread_filter.active_filters or {},
                        "latest_result_context": thread_filter.latest_result_context or {},
                    }
                )
            }
        )
    except Exception as exc:
        logger.warning("resolve_booking_selection failed: %s", exc)
        return BookingTurnResolution(action="none")

    if isinstance(response, BookingTurnResolution):
        resolution = response
    else:
        try:
            resolution = BookingTurnResolution.model_validate(response)
        except Exception as exc:
            logger.warning("resolve_booking_selection returned invalid structured response: %s", exc)
            return BookingTurnResolution(action="none")

    if resolution.action != "selection_pending":
        return resolution

    listing_code = resolution.listing_code.strip()
    if not listing_code:
        logger.warning("resolve_booking_selection returned selection_pending without listing_code")
        return BookingTurnResolution(
            action="no_match",
            message="Please choose one of the currently visible events to continue the booking.",
        )

    try:
        selected = select_thread_pending_booking(thread_filter=thread_filter, listing_code=listing_code)
    except BookingFlowError as exc:
        return BookingTurnResolution(action="no_match", message=str(exc))

    pending_booking = selected.get("pending_booking", {})
    return BookingTurnResolution(
        action="selection_pending",
        message=resolution.message or "I selected that event. Reply yes to confirm it or no to clear it.",
        listing_code=pending_booking.get("listing_code", listing_code),
        selected_event=pending_booking.get("event_snapshot", {}),
        booking={},
        candidates=[],
    )


@lru_cache(maxsize=1)
def _build_booking_confirmation_chain():
    llm = get_chat_model(resolver=True)
    structured_llm = llm.with_structured_output(BookingTurnResolution)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You handle booking confirmation for a thread that already has a pending booking awaiting confirmation.\n"
                "The user message is provided as JSON with user_message, active_filters, pending_booking, missing_fields, and latest_result_context.\n"
                "If the user says yes, confirm, go ahead, or otherwise approves the selected event in any language, return action booking_confirmed.\n"
                "If the selected event still needs user details first, still return booking_confirmed. The application will decide whether confirmation can proceed or if user info is missing.\n"
                "If the user explicitly rejects or cancels the selected event, return action booking_cleared.\n"
                "If the user says they want a different movie, different event, different match, another option, or wants to pick again without naming a replacement yet, return action booking_cleared so the app can restore the current results and let them choose again.\n"
                "Examples include 'I want a different movie', 'show me other movies', 'another one', 'not this, something else', 'different match', or 'pick a different one'.\n"
                "If the user asks to book a different visible result, resolve it only from latest_result_context.results and return action selection_pending with the chosen listing_code.\n"
                "If the user is changing the search instead of confirming the booking, return action none so the normal search flow can continue.\n"
                "Treat requests like 'show football instead', 'show movies instead', 'Mumbai nahi Delhi', 'in Bengaluru instead', or 'this week not Sunday' as search changes, not booking cancellation.\n"
                "Treat only explicit cancellation phrases like 'cancel this booking', 'don't book this', 'not this one', 'नहीं इसे बुक मत करो', or 'बुकिंग रद्द करो' as booking_cleared.\n"
                "If multiple visible results could match, return action ambiguous with candidates and a clarification message.\n"
                "If the requested event cannot be matched to the current thread context, return action no_match.\n"
                "This step must work for multilingual or mixed-language user input too.\n"
                "Return a concise user-facing message in all handled actions.\n"
                "Do not invent listing codes."
            ),
            ("user", "{payload}"),
        ]
    )
    return prompt | structured_llm


def _invoke_booking_confirmation_resolution(*, thread_id: str, user_message: str) -> BookingTurnResolution:
    thread, thread_filter = _get_booking_thread_state(thread_id)
    context = get_thread_booking_context(thread_filter=thread_filter)

    try:
        response = _build_booking_confirmation_chain().invoke(
            {
                "payload": json.dumps(
                    {
                        "user_message": user_message,
                        "active_filters": context.get("active_filters", {}),
                        "pending_booking": context.get("pending_booking", {}),
                        "missing_fields": context.get("missing_fields", []),
                        "latest_result_context": context.get("latest_result_context", {}),
                    }
                )
            }
        )
    except Exception as exc:
        logger.warning("resolve_booking_confirmation failed: %s", exc)
        return BookingTurnResolution(action="none")

    if isinstance(response, BookingTurnResolution):
        resolution = response
    else:
        try:
            resolution = BookingTurnResolution.model_validate(response)
        except Exception as exc:
            logger.warning("resolve_booking_confirmation returned invalid structured response: %s", exc)
            return BookingTurnResolution(action="none")

    if resolution.action == "selection_pending":
        listing_code = resolution.listing_code.strip()
        if not listing_code:
            return BookingTurnResolution(
                action="no_match",
                message="Please choose one of the currently visible events to continue the booking.",
            )
        try:
            selected = select_thread_pending_booking(thread_filter=thread_filter, listing_code=listing_code)
        except BookingFlowError as exc:
            return BookingTurnResolution(action="no_match", message=str(exc))
        pending_booking = selected.get("pending_booking", {})
        return BookingTurnResolution(
            action="selection_pending",
            message=resolution.message or "I selected that event. Reply yes to confirm it or no to clear it.",
            listing_code=pending_booking.get("listing_code", listing_code),
            selected_event=pending_booking.get("event_snapshot", {}),
            booking={},
            candidates=[],
        )

    if resolution.action == "booking_cleared":
        cancel_thread_pending_booking(thread_filter=thread_filter)
        return BookingTurnResolution(
            action="booking_cleared",
            message=resolution.message or "Okay, I cleared that booking selection.",
        )

    if resolution.action == "booking_confirmed":
        try:
            confirmation = attempt_thread_pending_booking_confirmation(
                thread=thread,
                thread_filter=thread_filter,
                confirmed_via="chat_message",
                append_confirmation_message=False,
            )
        except BookingFlowError as exc:
            return BookingTurnResolution(action="no_match", message=str(exc))

        if confirmation["status"] == "confirmed":
            return BookingTurnResolution(
                action="booking_confirmed",
                message=resolution.message or "Your booking is confirmed.",
                listing_code=thread_filter.pending_booking.get("listing_code", ""),
                booking=confirmation["booking"],
            )

        pending_booking = confirmation["pending_booking"]
        return BookingTurnResolution(
            action="awaiting_user_info",
            message=confirmation["message"],
            listing_code=pending_booking.get("listing_code", ""),
            requested_field=confirmation["next_required_field"],
            selected_event=pending_booking.get("event_snapshot", {}),
            booking={
                "thread_id": str(thread.id),
                "event_type": pending_booking.get("event_snapshot", {}).get("domain", ""),
                "status": pending_booking.get("status", ""),
                "event_title": pending_booking.get("event_snapshot", {}).get("title", ""),
                "customer_name": pending_booking.get("customer_info", {}).get("name", ""),
                "customer_email": pending_booking.get("customer_info", {}).get("email", ""),
                "customer_contact_number": pending_booking.get("customer_info", {}).get("contact_number", ""),
                "city": pending_booking.get("event_snapshot", {}).get("city", ""),
                "venue_name": pending_booking.get("event_snapshot", {}).get("venue_name", ""),
                "starts_at": pending_booking.get("event_snapshot", {}).get("start_at", ""),
            },
        )

    return resolution


@lru_cache(maxsize=1)
def _build_booking_user_info_chain():
    llm = get_chat_model(resolver=True)
    structured_llm = llm.with_structured_output(BookingTurnResolution)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You handle the missing-user-info stage for a pending booking.\n"
                "The user message is provided as JSON with user_message, active_filters, pending_booking, missing_fields, and latest_result_context.\n"
                "Inspect pending_booking.awaiting_field and missing_fields.\n"
                "If the user provides the missing value for pending_booking.awaiting_field in any language, return action booking_confirmed and place the raw user value in message exactly as provided.\n"
                "The application will validate and save that value, then decide whether more fields are needed or the booking can be confirmed.\n"
                "If the user wants to switch to a different visible result, resolve it only from latest_result_context.results and return action selection_pending with the newly selected listing_code.\n"
                "When the user switches events, do not treat it as a cancellation. The booking remains in progress with the new selected event.\n"
                "If the user explicitly rejects or cancels the pending booking, return action booking_cleared.\n"
                "If the user says they want a different movie, different event, different match, another option, or wants to pick again without naming a replacement yet, return action booking_cleared so the app can restore the current results and let them choose again.\n"
                "Examples include 'I want a different movie', 'show me other movies', 'another one', 'not this, something else', 'different match', or 'pick a different one'.\n"
                "If the user is clearly changing the search instead of answering the awaited field, return action none so the normal search flow can continue.\n"
                "Treat messages like 'show football instead', 'movies instead', 'Mumbai nahi Delhi', 'this week not Sunday', or 'kal ka dikhana' as search changes. Do not clear the booking for those; return action none.\n"
                "Treat only explicit cancellation phrases like 'cancel this booking', 'don't book this', 'not this one', 'नहीं इसे बुक मत करो', or 'बुकिंग रद्द करो' as booking_cleared.\n"
                "Examples of valid awaited-field answers include names, emails, and phone numbers in any language or script, such as 'Nandan Kumar', 'नंदन कुमार', 'nandan@example.com', or '9876543210'.\n"
                "If the message is unrelated to the awaited field and not a search change, return action awaiting_user_info with requested_field set to the current awaited field and remind the user what is still needed.\n"
                "This step must work for multilingual or mixed-language user input too.\n"
                "Return a concise user-facing message in all handled actions.\n"
                "Do not invent listing codes."
            ),
            ("user", "{payload}"),
        ]
    )
    return prompt | structured_llm


def _invoke_booking_user_info_resolution(*, thread_id: str, user_message: str) -> BookingTurnResolution:
    thread, thread_filter = _get_booking_thread_state(thread_id)
    context = get_thread_booking_context(thread_filter=thread_filter)
    pending_booking = context.get("pending_booking", {})
    awaited_field = str(pending_booking.get("awaiting_field", "") or "")

    try:
        response = _build_booking_user_info_chain().invoke(
            {
                "payload": json.dumps(
                    {
                        "user_message": user_message,
                        "active_filters": context.get("active_filters", {}),
                        "pending_booking": pending_booking,
                        "missing_fields": context.get("missing_fields", []),
                        "latest_result_context": context.get("latest_result_context", {}),
                    }
                )
            }
        )
    except Exception as exc:
        logger.warning("resolve_booking_user_info failed: %s", exc)
        return BookingTurnResolution(action="none")

    if isinstance(response, BookingTurnResolution):
        resolution = response
    else:
        try:
            resolution = BookingTurnResolution.model_validate(response)
        except Exception as exc:
            logger.warning("resolve_booking_user_info returned invalid structured response: %s", exc)
            return BookingTurnResolution(action="none")

    if resolution.action == "selection_pending":
        listing_code = resolution.listing_code.strip()
        if not listing_code:
            return BookingTurnResolution(
                action="no_match",
                message="Please choose one of the currently visible events to continue the booking.",
            )
        try:
            selected = select_thread_pending_booking(thread_filter=thread_filter, listing_code=listing_code)
        except BookingFlowError as exc:
            return BookingTurnResolution(action="no_match", message=str(exc))
        pending_booking = selected.get("pending_booking", {})
        return BookingTurnResolution(
            action="selection_pending",
            message=resolution.message or "I selected that event. Reply yes to confirm it or no to clear it.",
            listing_code=pending_booking.get("listing_code", listing_code),
            selected_event=pending_booking.get("event_snapshot", {}),
            booking={},
            candidates=[],
        )

    if resolution.action == "booking_cleared":
        cancel_thread_pending_booking(thread_filter=thread_filter)
        return BookingTurnResolution(
            action="booking_cleared",
            message=resolution.message or "Okay, I cleared that booking selection.",
        )

    if resolution.action == "booking_confirmed":
        raw_value = user_message.strip()
        if not awaited_field:
            return BookingTurnResolution(action="none")

        saved = capture_thread_booking_user_info(
            thread_filter=thread_filter,
            field_name=awaited_field,
            value=raw_value,
        )
        if saved["status"] == "invalid_user_info":
            return BookingTurnResolution(
                action="awaiting_user_info",
                message=saved["message"],
                listing_code=pending_booking.get("listing_code", ""),
                requested_field=awaited_field,
                selected_event=pending_booking.get("event_snapshot", {}),
                booking={},
            )

        try:
            confirmation = attempt_thread_pending_booking_confirmation(
                thread=thread,
                thread_filter=thread_filter,
                confirmed_via="chat_message",
                append_confirmation_message=False,
            )
        except BookingFlowError as exc:
            return BookingTurnResolution(action="no_match", message=str(exc))

        if confirmation["status"] == "confirmed":
            latest_pending = thread_filter.pending_booking or {}
            booking_payload = confirmation["booking"]
            confirmation_message = (
                f"Booking confirmed for {booking_payload['event_title']} in {booking_payload['city']} at "
                f"{booking_payload['venue_name']}. Your reference is {booking_payload['booking_reference']}."
            )
            return BookingTurnResolution(
                action="booking_confirmed",
                message=confirmation_message,
                listing_code=latest_pending.get("listing_code", ""),
                booking=booking_payload,
            )

        updated_pending = confirmation["pending_booking"]
        return BookingTurnResolution(
            action="awaiting_user_info",
            message=confirmation["message"],
            listing_code=updated_pending.get("listing_code", ""),
            requested_field=confirmation["next_required_field"],
            selected_event=updated_pending.get("event_snapshot", {}),
            booking={
                "thread_id": str(thread.id),
                "event_type": updated_pending.get("event_snapshot", {}).get("domain", ""),
                "status": updated_pending.get("status", ""),
                "event_title": updated_pending.get("event_snapshot", {}).get("title", ""),
                "customer_name": updated_pending.get("customer_info", {}).get("name", ""),
                "customer_email": updated_pending.get("customer_info", {}).get("email", ""),
                "customer_contact_number": updated_pending.get("customer_info", {}).get("contact_number", ""),
                "city": updated_pending.get("event_snapshot", {}).get("city", ""),
                "venue_name": updated_pending.get("event_snapshot", {}).get("venue_name", ""),
                "starts_at": updated_pending.get("event_snapshot", {}).get("start_at", ""),
            },
        )

    if resolution.action == "awaiting_user_info":
        return BookingTurnResolution(
            action="awaiting_user_info",
            message=resolution.message or FIELD_PROMPTS.get(awaited_field, "Please share the requested booking detail."),
            listing_code=pending_booking.get("listing_code", ""),
            requested_field=resolution.requested_field or awaited_field,
            selected_event=pending_booking.get("event_snapshot", {}),
            booking={},
        )

    return resolution


@lru_cache(maxsize=1)
def _build_turn_policy_chain():
    llm = get_chat_model(resolver=True)
    structured_llm = llm.with_structured_output(TurnPolicy)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You route conversational turns for an event discovery and booking assistant.\n"
                "The user message is provided as JSON with user_message, current_filters, pending_booking, latest_result_context, and goal_state.\n"
                "Return intent task_continue when the message should be handled by the normal search, filter, selection, booking confirmation, or booking user-info flows.\n"
                "That includes event changes, filter changes, booking changes, and follow-up questions about currently shown events.\n"
                "Return search_change when the user is changing filters, dates, domains, locations, or other search constraints.\n"
                "Standalone corrections like 'Actually Mumbai again', 'No wait Pune', 'Delhi instead', 'this week not Sunday', or 'Show cricket matches' after movie results are search_change turns, even when current results are visible.\n"
                "Only prefer booking-related intents when the user is explicitly trying to book, pick, reserve, confirm, cancel, or provide missing booking details.\n"
                "Return booking_change when the user is changing which visible event they want to book while a booking is in progress.\n"
                "Return follow_up_about_results when the user is asking about the current visible results rather than changing the search.\n"
                "Return temporary_distraction when the message is small talk, a joke request, casual banter, or a brief detour but the conversation should be softly guided back to the current event-planning task.\n"
                "Return out_of_scope when the user requests something unrelated to event discovery or booking, such as writing poems or doing unrelated work.\n"
                "Return meta_help when the user is asking how the assistant works or what it can do in the current planning context.\n"
                "Set should_keep_results true when there is enough current planning context that the assistant should keep showing the current event results while softly redirecting.\n"
                "For temporary_distraction, out_of_scope, or meta_help, message must be a concise user-facing soft redirection that acknowledges the detour and guides the user back to the active planning task or pending booking.\n"
                "Do not answer the off-topic request in full. Keep the redirect concise, supportive, and focused on the saved goal_state when available.\n"
                "Do not invent filters or results."
            ),
            ("user", "{payload}"),
        ]
    )
    return prompt | structured_llm


@lru_cache(maxsize=1)
def _build_goal_state_chain():
    llm = get_chat_model(resolver=True)
    structured_llm = llm.with_structured_output(GoalState)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You maintain the active planning goal state for an event discovery and booking assistant.\n"
                "You are given JSON with the latest completed turn: user_message, assistant_message, active_filters, latest_result_context, pending_booking, search_domains, needs_clarification, clarification_question, booking_action, turn_policy_intent, and existing_goal_state.\n"
                "Return the single active goal after this turn.\n"
                "Use goal_type search when the user is browsing or refining events. Use booking when a booking is selected, being confirmed, or collecting user info. Use none only when there is no meaningful active planning context.\n"
                "Use goal_stage browsing_results for active event exploration with grounded results or filters, awaiting_clarification when the assistant still needs a missing clarification, pending_confirmation when an event is selected and awaiting yes/no, awaiting_user_info when the booking still needs customer details, and booking_confirmed when confirmation is complete.\n"
                "goal_summary must be a short user-facing summary of the active goal, such as 'Football matches in Mumbai' or 'Book Sunrisers Hyderabad vs Punjab Kings'.\n"
                "goal_summary must stay grounded in active_filters, search_domains, and pending_booking.\n"
                "If the active domain is sports, do not summarize the goal as movies.\n"
                "If the active domain is movies, do not summarize the goal as sports or matches.\n"
                "If pending_booking is present, prefer the selected event as the anchor for the goal summary.\n"
                "last_open_question should capture the next question or missing information the assistant expects from the user. Leave it empty only when nothing actionable is pending.\n"
                "If the latest turn was a temporary distraction or out_of_scope detour but the existing planning context remains active, preserve the underlying goal instead of replacing it with the distraction.\n"
                "Do not summarize the distraction itself as the goal."
            ),
            ("user", "{payload}"),
        ]
    )
    return prompt | structured_llm


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


def invoke_booking_agent(*, thread_id: str, user_message: str) -> BookingTurnResolution:
    _thread, thread_filter = _get_booking_thread_state(thread_id)
    pending_booking = thread_filter.pending_booking or {}
    awaiting_field = pending_booking.get("awaiting_field")
    has_pending_selection = bool(pending_booking.get("listing_code"))
    if awaiting_field:
        return _invoke_booking_user_info_resolution(thread_id=thread_id, user_message=user_message)
    elif has_pending_selection:
        return _invoke_booking_confirmation_resolution(thread_id=thread_id, user_message=user_message)
    else:
        return _invoke_booking_selection_resolution(thread_id=thread_id, user_message=user_message)

    try:
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "thread_id": thread_id,
                                "user_message": user_message,
                                "pending_booking": pending_booking,
                            }
                        ),
                    }
                ]
            }
        )
    except BookingFlowError as exc:
        return BookingTurnResolution(action="no_match", message=str(exc))
    except Exception as exc:
        logger.warning("resolve_booking_turn failed: %s", exc)
        return BookingTurnResolution(action="none")

    structured_response = response.get("structured_response")
    if isinstance(structured_response, BookingTurnResolution):
        return structured_response
    if structured_response is not None:
        try:
            return BookingTurnResolution.model_validate(structured_response)
        except Exception as exc:
            logger.warning("resolve_booking_turn returned invalid structured response: %s", exc)

    return BookingTurnResolution(action="none")


def invoke_turn_policy(
    *,
    user_message: str,
    current_filters: ActiveFilters,
    pending_booking: dict[str, object] | None = None,
    latest_result_context: dict[str, object] | None = None,
    goal_state: dict[str, object] | None = None,
) -> TurnPolicy:
    try:
        response = _build_turn_policy_chain().invoke(
            {
                "payload": json.dumps(
                    {
                        "user_message": user_message,
                        "current_filters": current_filters.model_dump(),
                        "pending_booking": pending_booking or {},
                        "latest_result_context": latest_result_context or {},
                        "goal_state": goal_state or {},
                    }
                )
            }
        )
    except Exception as exc:
        logger.warning("resolve_turn_policy failed: %s", exc)
        return TurnPolicy(intent="task_continue")

    if isinstance(response, TurnPolicy):
        return response
    try:
        return TurnPolicy.model_validate(response)
    except Exception as exc:
        logger.warning("resolve_turn_policy returned invalid structured response: %s", exc)
        return TurnPolicy(intent="task_continue")


def invoke_goal_state(
    *,
    user_message: str,
    assistant_message: str,
    active_filters: dict[str, object],
    latest_result_context: dict[str, object] | None,
    pending_booking: dict[str, object] | None,
    search_domains: list[str],
    needs_clarification: bool,
    clarification_question: str | None,
    booking_action: str | None,
    turn_policy_intent: str,
    existing_goal_state: dict[str, object] | None = None,
) -> GoalState:
    try:
        response = _build_goal_state_chain().invoke(
            {
                "payload": json.dumps(
                    {
                        "user_message": user_message,
                        "assistant_message": assistant_message,
                        "active_filters": active_filters,
                        "latest_result_context": latest_result_context or {},
                        "pending_booking": pending_booking or {},
                        "search_domains": search_domains,
                        "needs_clarification": needs_clarification,
                        "clarification_question": clarification_question,
                        "booking_action": booking_action,
                        "turn_policy_intent": turn_policy_intent,
                        "existing_goal_state": existing_goal_state or {},
                    }
                )
            }
        )
    except Exception as exc:
        logger.warning("resolve_goal_state failed: %s", exc)
        return _ground_goal_state(
            GoalState.model_validate(existing_goal_state or {}),
            active_filters=active_filters,
            latest_result_context=latest_result_context,
            pending_booking=pending_booking,
            search_domains=search_domains,
            clarification_question=clarification_question,
        )

    if isinstance(response, GoalState):
        return _ground_goal_state(
            response,
            active_filters=active_filters,
            latest_result_context=latest_result_context,
            pending_booking=pending_booking,
            search_domains=search_domains,
            clarification_question=clarification_question,
        )
    try:
        return _ground_goal_state(
            GoalState.model_validate(response),
            active_filters=active_filters,
            latest_result_context=latest_result_context,
            pending_booking=pending_booking,
            search_domains=search_domains,
            clarification_question=clarification_question,
        )
    except Exception as exc:
        logger.warning("resolve_goal_state returned invalid structured response: %s", exc)
        return _ground_goal_state(
            GoalState.model_validate(existing_goal_state or {}),
            active_filters=active_filters,
            latest_result_context=latest_result_context,
            pending_booking=pending_booking,
            search_domains=search_domains,
            clarification_question=clarification_question,
        )


def _ground_goal_state(
    goal_state: GoalState,
    *,
    active_filters: dict[str, object],
    latest_result_context: dict[str, object] | None,
    pending_booking: dict[str, object] | None,
    search_domains: list[str],
    clarification_question: str | None,
) -> GoalState:
    pending_booking = pending_booking or {}
    active_filters = active_filters or {}
    latest_result_context = latest_result_context or {}

    normalized = goal_state.model_copy(deep=True)
    grounded_summary = _build_grounded_goal_summary(
        active_filters=active_filters,
        latest_result_context=latest_result_context,
        pending_booking=pending_booking,
        search_domains=search_domains,
    )

    if pending_booking.get("listing_code"):
        normalized.goal_type = "booking"
        if grounded_summary:
            normalized.goal_summary = grounded_summary
        if normalized.goal_stage == "no_goal":
            normalized.goal_stage = "awaiting_user_info" if pending_booking.get("awaiting_field") else "pending_confirmation"
        if not normalized.last_open_question:
            normalized.last_open_question = clarification_question or ""
        return normalized

    if search_domains:
        normalized.goal_type = "search"
        if grounded_summary:
            normalized.goal_summary = grounded_summary
        if normalized.goal_stage == "no_goal":
            normalized.goal_stage = "awaiting_clarification" if clarification_question else "browsing_results"
        if not normalized.last_open_question and clarification_question:
            normalized.last_open_question = clarification_question
        return normalized

    return normalized


def _build_grounded_goal_summary(
    *,
    active_filters: dict[str, object],
    latest_result_context: dict[str, object],
    pending_booking: dict[str, object],
    search_domains: list[str],
) -> str:
    event_snapshot = pending_booking.get("event_snapshot", {}) if pending_booking else {}
    if event_snapshot.get("listing_code"):
        domain = str(event_snapshot.get("domain", "")).strip()
        title = str(event_snapshot.get("title", "")).strip()
        city = str(event_snapshot.get("city", "")).strip()
        venue_name = str(event_snapshot.get("venue_name", "")).strip()
        event_date = str(event_snapshot.get("event_date", "")).strip()
        domain_label = "movie" if domain == "movies" else "match" if domain == "sports" else "event"
        parts = [f"Book {title} {domain_label}".strip()]
        if city:
            parts.append(f"in {city}")
        if venue_name:
            parts.append(f"at {venue_name}")
        if event_date:
            parts.append(f"on {event_date}")
        return " ".join(part for part in parts if part).strip()

    domains = search_domains or list(active_filters.get("event_types", []) or [])
    cities = list(active_filters.get("cities", []) or [])
    sport_types = list(active_filters.get("sport_types", []) or [])

    if domains == ["sports"]:
        if sport_types and cities:
            return f"{sport_types[0]} matches in {cities[0]}"
        if sport_types:
            return f"{sport_types[0]} matches"
        if cities:
            return f"Sports in {cities[0]}"
        return "Sports events"

    if domains == ["movies"]:
        if cities:
            return f"Movies in {cities[0]}"
        return "Movies"

    return ""


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
