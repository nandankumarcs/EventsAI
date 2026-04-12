from __future__ import annotations

from typing import Any

from django.db.models import Max
from django.utils import timezone

from apps.agents.langchain_tools import (
    ResolutionIssue,
    generate_dynamic_thread_title,
    invoke_booking_agent,
    resolve_turn_filters,
)
from apps.agents.schemas import ActiveFilters
from apps.bookings.services import build_latest_result_context
from apps.chats.models import ChatMessage, ChatThread, ThreadFilter
from apps.events.services import diversify_sport_results, search_movie_events, search_sport_events

MOVIE_FILTER_KEYS = {
    "titles",
    "genres",
    "cast_members",
    "directors",
    "certifications",
    "formats",
    "franchises",
    "content_origins",
}

SPORT_FILTER_KEYS = {
    "sport_types",
    "tournament_names",
    "season_labels",
    "competition_stages",
    "format_labels",
    "home_teams",
    "away_teams",
    "teams",
    "participant_names",
    "featured_athletes",
    "organizers",
    "match_numbers",
}

SHARED_SWITCH_CLEAR_KEYS = {
    "languages",
    "venue_names",
}


class ChatTurnError(Exception):
    status_code = 400

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


def process_chat_turn(*, user_message: str, thread_id: str | None = None) -> dict[str, Any]:
    reference_date = timezone.localdate().isoformat()
    thread, _created = _get_or_create_thread(user_message=user_message, thread_id=thread_id)
    _assert_thread_accepts_messages(thread)
    thread_filter = _get_or_create_thread_filter(thread)
    current_filters = ActiveFilters.model_validate(thread_filter.active_filters or {})
    pending_booking_before_turn = dict(thread_filter.pending_booking or {})

    _append_message(thread, role=ChatMessage.Role.USER, content=user_message, metadata={})

    booking_resolution = invoke_booking_agent(thread_id=str(thread.id), user_message=user_message)
    thread_filter.refresh_from_db()
    booking_resolution = _reconcile_booking_resolution(
        user_message=user_message,
        booking_resolution=booking_resolution,
        thread_filter=thread_filter,
        pending_booking_before_turn=pending_booking_before_turn,
        current_filters=current_filters,
        reference_date=reference_date,
    )
    if booking_resolution.action != "none":
        booking_results_by_domain = (
            _results_by_domain_from_latest_context(thread_filter.latest_result_context)
            if booking_resolution.action == "booking_cleared"
            else {}
        )
        thread.refresh_from_db()
        thread_filter.refresh_from_db()
        assistant_message = _append_message(
            thread,
            role=ChatMessage.Role.ASSISTANT,
            content=booking_resolution.message,
            metadata={
                "booking_action": booking_resolution.action,
                "listing_code": booking_resolution.listing_code,
                "requested_field": booking_resolution.requested_field,
                "selected_event": booking_resolution.selected_event
                or thread_filter.pending_booking.get("event_snapshot", {}),
                "pending_booking": thread_filter.pending_booking,
                "booking": booking_resolution.booking,
                "candidates": booking_resolution.candidates,
                "results_by_domain": booking_results_by_domain,
                "latest_result_context": thread_filter.latest_result_context,
            },
        )
        thread.last_message_preview = booking_resolution.message[:500]
        thread.last_activity_at = timezone.now()
        thread.save(update_fields=["last_message_preview", "last_activity_at", "updated_at"])
        
        _update_dynamic_thread_title(thread)
        
        return {
            "thread": _serialize_thread(thread),
            "assistant_message": _serialize_message(assistant_message),
            "active_filters": thread_filter.active_filters,
            "latest_result_context": thread_filter.latest_result_context,
            "pending_booking": thread_filter.pending_booking,
            "search_domains": [],
            "results_by_domain": booking_results_by_domain,
            "needs_clarification": booking_resolution.action in {"ambiguous", "no_match"},
            "clarification_question": booking_resolution.message if booking_resolution.action in {"ambiguous", "no_match"} else None,
        }

    turn_resolution = resolve_turn_filters(
        current_filters=current_filters,
        user_message=user_message,
        reference_date=reference_date,
    )
    filters_to_clear = _derive_filters_to_clear(
        current_filters=current_filters,
        updates=turn_resolution.updates,
    )
    filters_to_clear = sorted(set([*filters_to_clear, *turn_resolution.clear_fields]))

    merged_filters = _merge_filter_state(
        current_filters=current_filters,
        updates=turn_resolution.updates,
        filters_to_clear=filters_to_clear,
    )

    blocking_issue = _get_blocking_issue(turn_resolution.issues)
    if blocking_issue is not None:
        search_domains = []
        results_by_domain = {}
        result_listing_codes = []
        assistant_content, needs_clarification, clarification_question = _build_issue_reply(
            issue=blocking_issue,
        )
    else:
        search_domains = _derive_search_domains(merged_filters)
        results_by_domain = _fetch_results_by_domain(merged_filters, search_domains)
        result_listing_codes = [
            item["listing_code"]
            for domain_results in results_by_domain.values()
            for item in domain_results["results"]
        ]
        assistant_content, needs_clarification, clarification_question = _build_grounded_reply(
            filters=merged_filters,
            search_domains=search_domains,
            results_by_domain=results_by_domain,
            fallback_message="",
        )

    thread_filter.active_filters = _compact_filter_state(merged_filters.model_dump())
    thread_filter.latest_result_context = build_latest_result_context(
        thread=thread,
        search_domains=search_domains,
        results_by_domain=results_by_domain,
    )
    thread_filter.pending_booking = {}
    thread_filter.resolver_trace = turn_resolution.tool_trace
    thread_filter.version += 1
    thread_filter.last_resolved_at = timezone.now()
    thread_filter.save(
        update_fields=[
            "active_filters",
            "latest_result_context",
            "pending_booking",
            "resolver_trace",
            "version",
            "last_resolved_at",
            "updated_at",
        ]
    )

    assistant_metadata = {
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
        "search_domains": search_domains,
        "result_listing_codes": result_listing_codes,
        "results_by_domain": results_by_domain,
        "active_filters": thread_filter.active_filters,
        "latest_result_context": thread_filter.latest_result_context,
        "pending_booking": thread_filter.pending_booking,
        "resolution_issues": [
            {
                "status": issue.status,
                "trace_name": issue.trace_name,
                "filter_label": issue.filter_label,
                "message": issue.message,
                "candidates": issue.candidates,
            }
            for issue in turn_resolution.issues
        ],
    }
    assistant_message = _append_message(
        thread,
        role=ChatMessage.Role.ASSISTANT,
        content=assistant_content,
        metadata=assistant_metadata,
    )

    thread.last_message_preview = assistant_content[:500]
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=["last_message_preview", "last_activity_at", "updated_at"])

    _update_dynamic_thread_title(thread)

    return {
        "thread": _serialize_thread(thread),
        "assistant_message": _serialize_message(assistant_message),
        "active_filters": thread_filter.active_filters,
        "search_domains": search_domains,
        "results_by_domain": results_by_domain,
        "latest_result_context": thread_filter.latest_result_context,
        "pending_booking": thread_filter.pending_booking,
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
    }


def _reconcile_booking_resolution(
    *,
    booking_resolution,
    **_: Any,
):
    return booking_resolution


def _results_by_domain_from_latest_context(latest_result_context: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not latest_result_context:
        return {}

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in latest_result_context.get("results", []):
        domain = item.get("domain")
        if not domain:
            continue
        grouped.setdefault(domain, []).append(
            {
                "id": item.get("listing_code", ""),
                "listing_code": item.get("listing_code", ""),
                "title": item.get("title", ""),
                "city": item.get("city", ""),
                "venue_name": item.get("venue_name", ""),
                "event_date": item.get("event_date", ""),
                "start_at": item.get("start_at", ""),
                "min_price": item.get("min_price"),
                "max_price": item.get("max_price"),
                "genres": item.get("genres", []),
                "sport_type": item.get("sport_type"),
            }
        )

    return {
        domain: {
            "count": len(results),
            "limit": len(results),
            "offset": 0,
            "filters": {},
            "results": results,
        }
        for domain, results in grouped.items()
    }

def _get_or_create_thread(*, user_message: str, thread_id: str | None) -> tuple[ChatThread, bool]:
    if thread_id:
        return ChatThread.objects.get(id=thread_id), False

    title = user_message.strip()[:80] or "New thread"
    thread = ChatThread.objects.create(
        title=title,
        last_message_preview=user_message[:500],
        last_activity_at=timezone.now(),
    )
    return thread, True


def _assert_thread_accepts_messages(thread: ChatThread) -> None:
    if thread.status == ChatThread.Status.BOOKED:
        raise ChatTurnError(
            "This thread already has a confirmed booking. Start a new thread to plan another event.",
            status_code=409,
        )
    if thread.status == ChatThread.Status.ARCHIVED:
        raise ChatTurnError(
            "This thread is archived and cannot accept new messages.",
            status_code=409,
        )


def _get_or_create_thread_filter(thread: ChatThread) -> ThreadFilter:
    thread_filter, _created = ThreadFilter.objects.get_or_create(thread=thread)
    return thread_filter


def _update_dynamic_thread_title(thread: ChatThread) -> None:
    # Extract max 5 recent user messages to keep the LLM fast
    recent_user_messages = list(
        thread.messages.filter(role=ChatMessage.Role.USER)
        .order_by("-position")[:5]
        .values_list("content", flat=True)
    )
    recent_user_messages.reverse()
    
    if not recent_user_messages:
        return
        
    try:
        new_title = generate_dynamic_thread_title(recent_user_messages)
        if new_title and new_title.lower() != "new thread":
            thread.title = new_title
            thread.save(update_fields=["title", "updated_at"])
            # Refresh if necessary
            thread.refresh_from_db(fields=["title", "updated_at"])
    except Exception:
        pass


def _append_message(
    thread: ChatThread,
    *,
    role: str,
    content: str,
    metadata: dict[str, Any],
) -> ChatMessage:
    next_position = (thread.messages.aggregate(max_position=Max("position"))["max_position"] or 0) + 1
    return ChatMessage.objects.create(
        thread=thread,
        position=next_position,
        role=role,
        content=content,
        metadata=metadata,
    )


def _merge_filter_state(
    *,
    current_filters: ActiveFilters,
    updates: ActiveFilters,
    filters_to_clear: list[str],
) -> ActiveFilters:
    merged = current_filters.model_dump()

    for key in filters_to_clear:
        merged.pop(key, None)

    update_payload = updates.model_dump()
    for key, value in update_payload.items():
        if value in (None, [], ""):
            continue
        merged[key] = value

    event_types = merged.get("event_types", [])
    if event_types == ["movies"]:
        for key in SPORT_FILTER_KEYS:
            merged.pop(key, None)
    if event_types == ["sports"]:
        for key in MOVIE_FILTER_KEYS:
            merged.pop(key, None)

    return ActiveFilters.model_validate(merged)


def _derive_search_domains(filters: ActiveFilters) -> list[str]:
    if filters.event_types:
        return filters.event_types
    return ["movies", "sports"]


def _derive_filters_to_clear(*, current_filters: ActiveFilters, updates: ActiveFilters) -> list[str]:
    if not updates.event_types:
        return []

    previous_domains = current_filters.event_types
    next_domains = updates.event_types
    if previous_domains == next_domains:
        return []

    keys_to_clear: set[str] = set(SHARED_SWITCH_CLEAR_KEYS)
    if next_domains == ["movies"]:
        keys_to_clear.update(SPORT_FILTER_KEYS)
    if next_domains == ["sports"]:
        keys_to_clear.update(MOVIE_FILTER_KEYS)
    return sorted(keys_to_clear)


def _fetch_results_by_domain(filters: ActiveFilters, domains: list[str]) -> dict[str, dict[str, Any]]:
    payload = _compact_filter_state(filters.model_dump(exclude={"event_types"}))
    results: dict[str, dict[str, Any]] = {}

    if "movies" in domains:
        results["movies"] = search_movie_events(payload, limit=5, offset=0).to_dict()
    if "sports" in domains:
        sport_limit = 20 if len(filters.sport_types) > 1 else 5
        sport_results = search_sport_events(payload, limit=sport_limit, offset=0).to_dict()
        if len(filters.sport_types) > 1:
            sport_results["results"] = diversify_sport_results(sport_results["results"], limit=5)
            sport_results["limit"] = 5
        results["sports"] = sport_results

    return results


def _compact_filter_state(filters: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, value in filters.items():
        if value in (None, "", []):
            continue
        compacted[key] = value
    return compacted


def _build_grounded_reply(
    *,
    filters: ActiveFilters,
    search_domains: list[str],
    results_by_domain: dict[str, dict[str, Any]],
    fallback_message: str,
) -> tuple[str, bool, str | None]:
    total_results = sum(domain["count"] for domain in results_by_domain.values())
    if total_results == 0:
        descriptor = _build_filter_descriptor(filters, search_domains)
        question = "Would you like to try a different date, time, or location?"
        return (
            f"I found no {descriptor} matching your current filters. {question}",
            True,
            question,
        )

    labels: list[str] = []
    for domain in search_domains:
        domain_results = results_by_domain.get(domain, {})
        if not domain_results.get("results"):
            continue
        titles = [item["title"] for item in domain_results["results"][:3]]
        domain_label = "movie" if domain == "movies" else "sports event"
        labels.append(f"{domain_label} options such as {', '.join(titles)}")

    if labels:
        descriptor = _build_filter_descriptor(filters, search_domains)
        return (
            f"I found {descriptor}, including {'. '.join(labels)}. Would you like to explore one of these or narrow the search further?",
            False,
            None,
        )

    return fallback_message, False, None
def _get_blocking_issue(issues: list[ResolutionIssue]) -> ResolutionIssue | None:
    if not issues:
        return None

    for status in ("ambiguous", "no_match"):
        for issue in issues:
            if issue.status == status:
                return issue
    return None


def _build_issue_reply(*, issue: ResolutionIssue) -> tuple[str, bool, str | None]:
    if issue.status == "ambiguous":
        if issue.candidates:
            options = ", ".join(issue.candidates[:4])
            question = f"Did you mean {options}?"
            return (
                f"I found multiple possible matches for the {issue.filter_label}. {question}",
                True,
                question,
            )

        question = f"Could you clarify which {issue.filter_label} you want?"
        return (
            f"I found multiple possible matches for the {issue.filter_label}. {question}",
            True,
            question,
        )

    question = f"Would you like to try a different {issue.filter_label}?"
    message = issue.message or f"I could not match that {issue.filter_label} to the available catalog."
    return (
        f"{message} {question}",
        True,
        question,
    )


def _build_filter_descriptor(filters: ActiveFilters, search_domains: list[str]) -> str:
    parts: list[str] = []
    if search_domains == ["sports"] and len(filters.sport_types) == 1:
        parts.append(f"{filters.sport_types[0].lower()} matches")
    elif search_domains == ["movies"]:
        parts.append("movie options")
    else:
        parts.append("event options")

    if filters.cities:
        parts.append(f"in {filters.cities[0]}")
    if filters.event_dates:
        if len(filters.event_dates) == 1:
            parts.append(f"on {filters.event_dates[0]}")
        else:
            parts.append(f"on {filters.event_dates[0]} or {filters.event_dates[1]}")
    if filters.start_time_from and filters.start_time_to:
        parts.append(
            f"between {filters.start_time_from[:5]} and {filters.start_time_to[:5]}"
        )
    return " ".join(parts)


def _serialize_thread(thread: ChatThread) -> dict[str, Any]:
    return {
        "id": str(thread.id),
        "title": thread.title,
        "status": thread.status,
        "last_message_preview": thread.last_message_preview,
        "last_activity_at": thread.last_activity_at.isoformat(),
    }


def _serialize_message(message: ChatMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "thread_id": str(message.thread_id),
        "position": message.position,
        "role": message.role,
        "content": message.content,
        "metadata": message.metadata,
        "created_at": message.created_at.isoformat(),
    }
