from __future__ import annotations

from typing import Any
from types import SimpleNamespace

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.agents.langchain_tools import (
    ResolutionIssue,
    generate_dynamic_thread_title,
    invoke_booking_agent,
    invoke_goal_state,
    invoke_turn_policy,
    resolve_turn_filters,
)
from apps.agents.schemas import ActiveFilters, BookingTurnResolution
from apps.bookings.services import (
    FIELD_PROMPTS,
    build_latest_result_context,
    get_missing_booking_user_fields,
    select_thread_pending_booking,
)
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

    with transaction.atomic():
        _assert_thread_accepts_messages(thread)
        thread_filter = _get_or_create_thread_filter(thread, lock=True)
        current_filters = ActiveFilters.model_validate(thread_filter.active_filters or {})
        pending_booking_before_turn = dict(thread_filter.pending_booking or {})
        existing_goal_state = _get_thread_goal_state(thread)
        has_pending_booking = bool((thread_filter.pending_booking or {}).get("listing_code"))

        _append_message(thread, role=ChatMessage.Role.USER, content=user_message, metadata={})

        pending_booking_snapshot = dict(thread_filter.pending_booking or {})
        latest_result_context_snapshot = dict(thread_filter.latest_result_context or {})

    resolver_plan = None
    if has_pending_booking:
        turn_policy = invoke_turn_policy(
            user_message=user_message,
            current_filters=current_filters,
            pending_booking=pending_booking_snapshot,
            latest_result_context=latest_result_context_snapshot,
            goal_state=existing_goal_state,
        )
        if turn_policy.intent in {"temporary_distraction", "out_of_scope", "meta_help"}:
            with transaction.atomic():
                thread.refresh_from_db()
                _assert_thread_accepts_messages(thread)
                thread_filter = _get_or_create_thread_filter(thread, lock=True)
                return _process_soft_redirect_turn(
                    thread=thread,
                    thread_filter=thread_filter,
                    current_filters=current_filters,
                    turn_policy=turn_policy,
                    user_message=user_message,
                    existing_goal_state=existing_goal_state,
                )
    else:
        from apps.agents.langchain_tools import invoke_resolver_invocation_plan

        resolver_plan = invoke_resolver_invocation_plan(
            user_message=user_message,
            current_filters=current_filters,
            pending_booking=pending_booking_snapshot,
            latest_result_context=latest_result_context_snapshot,
            turn_policy_intent="task_continue",
        )
        turn_policy = SimpleNamespace(
            intent=resolver_plan.intent,
            message=resolver_plan.message,
            should_keep_results=resolver_plan.should_keep_results,
        )
        if turn_policy.intent in {"temporary_distraction", "out_of_scope", "meta_help"}:
            with transaction.atomic():
                thread.refresh_from_db()
                _assert_thread_accepts_messages(thread)
                thread_filter = _get_or_create_thread_filter(thread, lock=True)
                return _process_soft_redirect_turn(
                    thread=thread,
                    thread_filter=thread_filter,
                    current_filters=current_filters,
                    turn_policy=turn_policy,
                    user_message=user_message,
                    existing_goal_state=existing_goal_state,
                )

    booking_resolution = BookingTurnResolution(action="none")
    if has_pending_booking and turn_policy.intent in {"task_continue", "booking_change", "follow_up_about_results"}:
        booking_resolution = invoke_booking_agent(thread_id=str(thread.id), user_message=user_message)
    elif not has_pending_booking and resolver_plan and resolver_plan.should_try_booking_agent:
        booking_resolution = invoke_booking_agent(thread_id=str(thread.id), user_message=user_message)

    if booking_resolution.action == "no_match" and not has_pending_booking:
        booking_resolution = BookingTurnResolution(action="none")

    if booking_resolution.action != "none":
        with transaction.atomic():
            thread.refresh_from_db()
            if thread.status == ChatThread.Status.ARCHIVED:
                raise ChatTurnError(
                    "This thread is archived and cannot accept new messages.",
                    status_code=409,
                )
            thread_filter = _get_or_create_thread_filter(thread, lock=True)

            booking_resolution = _reconcile_booking_resolution(
                user_message=user_message,
                booking_resolution=booking_resolution,
                thread_filter=thread_filter,
                pending_booking_before_turn=pending_booking_before_turn,
                current_filters=current_filters,
                reference_date=reference_date,
            )

            show_booking_results = booking_resolution.action == "booking_cleared"
            booking_results_by_domain = (
                _results_by_domain_from_latest_context(thread_filter.latest_result_context)
                if show_booking_results
                else {}
            )
            booking_search_domains = (
                list((thread_filter.latest_result_context or {}).get("search_domains", []))
                if show_booking_results
                else []
            )

            needs_clarification = booking_resolution.action in {"ambiguous", "no_match"}
            clarification_question = booking_resolution.message if needs_clarification else None
            goal_state = invoke_goal_state(
                user_message=user_message,
                assistant_message=booking_resolution.message,
                active_filters=thread_filter.active_filters or {},
                latest_result_context=thread_filter.latest_result_context,
                pending_booking=thread_filter.pending_booking,
                search_domains=booking_search_domains,
                needs_clarification=needs_clarification,
                clarification_question=clarification_question,
                booking_action=booking_resolution.action,
                turn_policy_intent=turn_policy.intent,
                existing_goal_state=existing_goal_state,
            )
            _persist_thread_goal_state(thread, goal_state.model_dump())
            assistant_message = _append_message(
                thread,
                role=ChatMessage.Role.ASSISTANT,
                content=booking_resolution.message,
                metadata={
                    "booking_action": booking_resolution.action,
                    "listing_code": booking_resolution.listing_code,
                    "requested_field": booking_resolution.requested_field,
                    "selected_event": booking_resolution.selected_event.model_dump(exclude_none=True, exclude_defaults=True)
                    or thread_filter.pending_booking.get("event_snapshot", {}),
                    "pending_booking": thread_filter.pending_booking,
                    "booking": booking_resolution.booking.model_dump(exclude_none=True, exclude_defaults=True),
                    "candidates": booking_resolution.candidates,
                    "results_by_domain": booking_results_by_domain,
                    "latest_result_context": thread_filter.latest_result_context,
                    "goal_state": goal_state.model_dump(),
                },
            )
            thread.last_message_preview = booking_resolution.message[:500]
            thread.last_activity_at = timezone.now()
            thread.save(update_fields=["last_message_preview", "last_activity_at", "updated_at", "metadata"])

            _update_dynamic_thread_title(thread)

            return {
                "thread": _serialize_thread(thread),
                "assistant_message": _serialize_message(assistant_message),
                "active_filters": thread_filter.active_filters,
                "latest_result_context": thread_filter.latest_result_context,
                "pending_booking": thread_filter.pending_booking,
                "search_domains": booking_search_domains,
                "results_by_domain": booking_results_by_domain,
                "needs_clarification": needs_clarification,
                "clarification_question": clarification_question,
                "goal_state": goal_state.model_dump(),
            }

    turn_resolution = resolve_turn_filters(
        current_filters=current_filters,
        user_message=user_message,
        reference_date=reference_date,
        pending_booking=pending_booking_snapshot,
        latest_result_context=latest_result_context_snapshot,
        turn_policy_intent=turn_policy.intent,
        resolver_plan=resolver_plan,
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
    ambiguity_issue = _get_ambiguity_issue(turn_resolution.issues)
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
        if ambiguity_issue is not None:
            clarification_question = _build_ambiguity_question(ambiguity_issue)
            if result_listing_codes:
                assistant_content = f"{assistant_content} {clarification_question}"
                needs_clarification = True
            else:
                assistant_content, needs_clarification, clarification_question = _build_issue_reply(
                    issue=ambiguity_issue,
                )

    with transaction.atomic():
        thread.refresh_from_db()
        _assert_thread_accepts_messages(thread)
        thread_filter = _get_or_create_thread_filter(thread, lock=True)

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
    goal_state = invoke_goal_state(
        user_message=user_message,
        assistant_message=assistant_content,
        active_filters=thread_filter.active_filters,
        latest_result_context=thread_filter.latest_result_context,
        pending_booking=thread_filter.pending_booking,
        search_domains=search_domains,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        booking_action=None,
        turn_policy_intent=turn_policy.intent,
        existing_goal_state=existing_goal_state,
    )
    assistant_metadata["goal_state"] = goal_state.model_dump()

    with transaction.atomic():
        thread.refresh_from_db()
        _assert_thread_accepts_messages(thread)
        thread_filter = _get_or_create_thread_filter(thread, lock=True)

        _persist_thread_goal_state(thread, goal_state.model_dump())
        assistant_message = _append_message(
            thread,
            role=ChatMessage.Role.ASSISTANT,
            content=assistant_content,
            metadata=assistant_metadata,
        )

        thread.last_message_preview = assistant_content[:500]
        thread.last_activity_at = timezone.now()
        thread.save(update_fields=["last_message_preview", "last_activity_at", "updated_at", "metadata"])

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
            "goal_state": goal_state.model_dump(),
        }


def _process_soft_redirect_turn(
    *,
    thread: ChatThread,
    thread_filter: ThreadFilter,
    current_filters: ActiveFilters,
    turn_policy,
    user_message: str,
    existing_goal_state: dict[str, Any],
) -> dict[str, Any]:
    has_pending_booking = bool((thread_filter.pending_booking or {}).get("listing_code"))
    current_filter_payload = _compact_filter_state(current_filters.model_dump())
    has_current_filters = bool(current_filter_payload)
    search_domains = _derive_search_domains(current_filters) if has_current_filters else []
    results_by_domain = (
        _fetch_results_by_domain(current_filters, search_domains)
        if has_current_filters and turn_policy.should_keep_results and not has_pending_booking
        else {}
    )
    latest_result_context = (
        build_latest_result_context(
            thread=thread,
            search_domains=search_domains,
            results_by_domain=results_by_domain,
        )
        if results_by_domain
        else (thread_filter.latest_result_context or {})
    )

    assistant_content = (turn_policy.message or "").strip()
    if results_by_domain:
        grounded_reply, _needs_clarification, _clarification_question = _build_grounded_reply(
            filters=current_filters,
            search_domains=search_domains,
            results_by_domain=results_by_domain,
            fallback_message="",
        )
        assistant_content = f"{assistant_content} {grounded_reply}".strip()

    if not assistant_content:
        assistant_content = "I can help with finding and booking events. Tell me what kind of movie or match you want."

    goal_state = invoke_goal_state(
        user_message=user_message,
        assistant_message=assistant_content,
        active_filters=thread_filter.active_filters,
        latest_result_context=latest_result_context,
        pending_booking=thread_filter.pending_booking,
        search_domains=search_domains,
        needs_clarification=False,
        clarification_question=None,
        booking_action=None,
        turn_policy_intent=turn_policy.intent,
        existing_goal_state=existing_goal_state,
    )
    _persist_thread_goal_state(thread, goal_state.model_dump())

    thread_filter.latest_result_context = latest_result_context
    thread_filter.resolver_trace = ["resolve_turn_policy"]
    thread_filter.version += 1
    thread_filter.last_resolved_at = timezone.now()
    thread_filter.save(
        update_fields=[
            "latest_result_context",
            "resolver_trace",
            "version",
            "last_resolved_at",
            "updated_at",
        ]
    )

    assistant_message = _append_message(
        thread,
        role=ChatMessage.Role.ASSISTANT,
        content=assistant_content,
        metadata={
            "needs_clarification": False,
            "clarification_question": None,
            "search_domains": search_domains,
            "result_listing_codes": [
                item["listing_code"]
                for domain_results in results_by_domain.values()
                for item in domain_results["results"]
            ],
            "results_by_domain": results_by_domain,
            "active_filters": thread_filter.active_filters,
            "latest_result_context": latest_result_context,
            "pending_booking": thread_filter.pending_booking,
            "turn_policy_intent": turn_policy.intent,
            "soft_redirect_message": turn_policy.message,
            "goal_state": goal_state.model_dump(),
        },
    )

    thread.last_message_preview = assistant_content[:500]
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=["last_message_preview", "last_activity_at", "updated_at", "metadata"])

    _update_dynamic_thread_title(thread)

    return {
        "thread": _serialize_thread(thread),
        "assistant_message": _serialize_message(assistant_message),
        "active_filters": thread_filter.active_filters,
        "search_domains": search_domains,
        "results_by_domain": results_by_domain,
        "latest_result_context": latest_result_context,
        "pending_booking": thread_filter.pending_booking,
        "needs_clarification": False,
        "clarification_question": None,
        "goal_state": goal_state.model_dump(),
    }


def _reconcile_booking_resolution(
    *,
    booking_resolution,
    thread_filter: ThreadFilter,
    pending_booking_before_turn: dict[str, Any],
    **_: Any,
):
    latest_results = (thread_filter.latest_result_context or {}).get("results", [])
    had_pending_selection = bool((pending_booking_before_turn or {}).get("listing_code"))

    if (
        booking_resolution.action == "ambiguous"
        and not had_pending_selection
        and len(latest_results) == 1
    ):
        selected = select_thread_pending_booking(
            thread_filter=thread_filter,
            listing_code=latest_results[0]["listing_code"],
        )
        pending_booking = selected.get("pending_booking", {})
        return type(booking_resolution)(
            action="selection_pending",
            message="I selected the only matching event from the current results. Reply yes to confirm it or no to clear it.",
            listing_code=pending_booking.get("listing_code", ""),
            selected_event=pending_booking.get("event_snapshot", {}),
            booking={},
            candidates=[],
        )

    if booking_resolution.action == "awaiting_user_info":
        pending_booking = dict(thread_filter.pending_booking or {})
        requested_field = booking_resolution.requested_field or pending_booking.get("awaiting_field", "")
        if requested_field and pending_booking.get("awaiting_field") != requested_field:
            pending_booking["status"] = "awaiting_user_info"
            pending_booking["awaiting_field"] = requested_field
            thread_filter.pending_booking = pending_booking
            thread_filter.save(update_fields=["pending_booking", "updated_at"])

    if (
        booking_resolution.action == "selection_pending"
        and had_pending_selection
        and pending_booking_before_turn.get("awaiting_field")
    ):
        pending_booking = dict(thread_filter.pending_booking or {})
        missing_fields = get_missing_booking_user_fields(pending_booking.get("customer_info", {}))
        if missing_fields:
            next_field = missing_fields[0]
            pending_booking["status"] = "awaiting_user_info"
            pending_booking["awaiting_field"] = next_field
            thread_filter.pending_booking = pending_booking
            thread_filter.save(update_fields=["pending_booking", "updated_at"])
            return type(booking_resolution)(
                action="awaiting_user_info",
                message=FIELD_PROMPTS[next_field],
                listing_code=pending_booking.get("listing_code", ""),
                requested_field=next_field,
                selected_event=pending_booking.get("event_snapshot", {}),
                booking={
                    "thread_id": str(thread_filter.thread_id),
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
                candidates=[],
            )

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


def _get_or_create_thread_filter(thread: ChatThread, *, lock: bool = False) -> ThreadFilter:
    thread_filter, _created = ThreadFilter.objects.get_or_create(thread=thread)
    if lock:
        thread_filter = ThreadFilter.objects.select_for_update().get(pk=thread_filter.pk)
    return thread_filter


def _get_thread_goal_state(thread: ChatThread) -> dict[str, Any]:
    metadata = thread.metadata or {}
    goal_state = metadata.get("goal_state")
    return goal_state if isinstance(goal_state, dict) else {}


def _persist_thread_goal_state(thread: ChatThread, goal_state: dict[str, Any]) -> None:
    metadata = dict(thread.metadata or {})
    metadata["goal_state"] = goal_state
    thread.metadata = metadata


def _update_dynamic_thread_title(thread: ChatThread) -> None:
    goal_summary = str(_get_thread_goal_state(thread).get("goal_summary", "")).strip()
    if goal_summary:
        next_title = goal_summary[:255]
        if next_title and thread.title != next_title:
            thread.title = next_title
            thread.save(update_fields=["title", "updated_at"])
            thread.refresh_from_db(fields=["title", "updated_at"])
        return

    thread_filter = ThreadFilter.objects.filter(thread=thread).first()
    pending_booking = dict((thread_filter.pending_booking or {}) if thread_filter else {})
    pending_snapshot = dict((pending_booking.get("event_snapshot") or {}) if pending_booking else {})
    pending_title = str(pending_snapshot.get("title", "") or "").strip()
    if pending_title:
        next_title = f"Book {pending_title}"[:255]
        if next_title and thread.title != next_title:
            thread.title = next_title
            thread.save(update_fields=["title", "updated_at"])
            thread.refresh_from_db(fields=["title", "updated_at"])
        return

    active_filters = dict((thread_filter.active_filters or {}) if thread_filter else {})
    if active_filters:
        event_types = [str(item) for item in (active_filters.get("event_types") or []) if str(item).strip()]
        cities = [str(item) for item in (active_filters.get("cities") or []) if str(item).strip()]
        sport_types = [str(item) for item in (active_filters.get("sport_types") or []) if str(item).strip()]
        titles = [str(item) for item in (active_filters.get("titles") or []) if str(item).strip()]

        parts: list[str] = []
        if titles:
            parts.append(titles[0])
        elif sport_types:
            parts.append(sport_types[0])
        elif event_types:
            parts.append(event_types[0])

        if cities:
            parts.append(cities[0])

        if parts:
            next_title = " ".join(parts)[:255]
            if next_title and thread.title != next_title:
                thread.title = next_title
                thread.save(update_fields=["title", "updated_at"])
                thread.refresh_from_db(fields=["title", "updated_at"])
            return

    from django.conf import settings

    if not getattr(settings, "ENABLE_DYNAMIC_THREAD_TITLE_GENERATION", False):
        return

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
        question = (
            "You can refine by date, city, sport, or genre next (for example, "
            "'show basketball in another city this weekend' or 'show action movies tonight')."
        )
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
        next_action_hint = "Next, you can ask me to book by position (for example, 'book the 2nd one'), book by event title, or refine filters by city/date/sport/genre."
        return (
            f"I found {descriptor}, including {'. '.join(labels)}. {next_action_hint}",
            False,
            None,
        )

    return fallback_message, False, None
def _get_blocking_issue(issues: list[ResolutionIssue]) -> ResolutionIssue | None:
    if not issues:
        return None

    for issue in issues:
        if issue.status == "no_match":
            return issue
    return None


def _get_ambiguity_issue(issues: list[ResolutionIssue]) -> ResolutionIssue | None:
    for issue in issues:
        if issue.status == "ambiguous":
            return issue
    return None


def _build_ambiguity_question(issue: ResolutionIssue) -> str:
    if issue.candidates:
        options = ", ".join(issue.candidates[:4])
        return f"Did you mean {options}?"

    return f"Could you clarify which {issue.filter_label} you want?"


def _build_issue_reply(*, issue: ResolutionIssue) -> tuple[str, bool, str | None]:
    if issue.status == "ambiguous":
        question = _build_ambiguity_question(issue)
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
        "goal_state": _get_thread_goal_state(thread),
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
