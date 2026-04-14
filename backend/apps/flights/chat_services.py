from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.agents.services import ChatTurnError
from apps.chats.models import ChatMessage, ChatThread, ThreadFilter
from apps.flights.booking_services import (
    attempt_thread_pending_flight_booking_confirmation,
    capture_thread_flight_booking_user_info,
    clear_thread_pending_flight_booking,
    get_missing_flight_booking_user_fields,
    get_pending_flight_booking,
    select_thread_pending_flight_booking,
)
from apps.flights.langchain_tools import resolve_flight_booking_turn, resolve_flight_turn_filters
from apps.flights.schemas import FlightBookingTurnResolution, FlightFilters
from apps.flights.services import search_flight_offers


def process_flight_chat_turn(*, user_message: str, thread_id: str) -> dict[str, Any]:
    reference_date = timezone.localdate().isoformat()
    thread = (
        ChatThread.objects.exclude(status=ChatThread.Status.DELETED)
        .select_related("filter_state")
        .filter(id=thread_id)
        .first()
    )
    if thread is None:
        raise ChatTurnError("Thread not found", status_code=404)
    _assert_thread_accepts_messages(thread)

    with transaction.atomic():
        thread_filter = _get_or_create_thread_filter(thread, lock=True)
        current_filters = FlightFilters.model_validate(thread_filter.active_filters or {})
        pending_booking_snapshot = dict(thread_filter.pending_booking or {})
        latest_result_context_snapshot = dict(thread_filter.latest_result_context or {})
        _append_message(thread, role=ChatMessage.Role.USER, content=user_message, metadata={})

    booking_resolution = FlightBookingTurnResolution(action="none")
    if pending_booking_snapshot.get("listing_code") or latest_result_context_snapshot.get("results"):
        booking_resolution = resolve_flight_booking_turn(
            user_message=user_message,
            pending_booking=pending_booking_snapshot,
            latest_result_context=latest_result_context_snapshot,
            missing_fields=get_missing_flight_booking_user_fields(pending_booking_snapshot.get("customer_info", {})),
        )

    if booking_resolution.action != "none":
        with transaction.atomic():
            thread.refresh_from_db()
            _assert_thread_accepts_messages(thread)
            thread_filter = _get_or_create_thread_filter(thread, lock=True)
            return _process_booking_resolution(
                thread=thread,
                thread_filter=thread_filter,
                current_filters=current_filters,
                booking_resolution=booking_resolution,
            )

    if get_pending_flight_booking(thread_filter=_get_or_create_thread_filter(thread, lock=False)).get("listing_code"):
        with transaction.atomic():
            thread.refresh_from_db()
            _assert_thread_accepts_messages(thread)
            thread_filter = _get_or_create_thread_filter(thread, lock=True)
            return _build_pending_soft_redirect_payload(
                thread=thread,
                thread_filter=thread_filter,
                assistant_content=booking_resolution.message
                or "We still have your selected flight. Share passenger details or say cancel to clear it.",
            )

    resolution = resolve_flight_turn_filters(
        current_filters=current_filters.model_dump(exclude_none=True, exclude_defaults=True),
        user_message=user_message,
        reference_date=reference_date,
    )
    merged_filters = _merge_filter_state(
        current_filters=current_filters,
        updates=resolution.active_filters_partial,
        clear_fields=resolution.clear_fields,
    )

    if resolution.status == "no_input":
        results_by_domain: dict[str, Any] = {}
        search_domains: list[str] = []
        assistant_content = resolution.message or "I can help with flights. Tell me origin, destination, and departure date."
        needs_clarification = False
        clarification_question = None
    elif resolution.status in {"ambiguous", "no_match"}:
        results_by_domain = {}
        search_domains = []
        assistant_content = resolution.message or "I couldn't match that flight request yet."
        needs_clarification = True
        clarification_question = assistant_content
    else:
        flight_result = search_flight_offers(merged_filters.model_dump(exclude_none=True, exclude_defaults=True))
        results_by_domain = {"flights": flight_result.to_dict()}
        search_domains = ["flights"]
        result_count = flight_result.count
        if result_count == 0:
            assistant_content = (
                "I couldn't find flights for the current filters. Try a different date, route, or airline."
            )
            needs_clarification = True
            clarification_question = assistant_content
        else:
            assistant_content = f"I found {result_count} flight options. You can pick one to continue."
            needs_clarification = False
            clarification_question = None

    with transaction.atomic():
        thread.refresh_from_db()
        _assert_thread_accepts_messages(thread)
        thread_filter = _get_or_create_thread_filter(thread, lock=True)
        thread.mode = ChatThread.Mode.FLIGHTS
        thread_filter.active_filters = _compact_filter_state(merged_filters.model_dump(exclude_none=True))
        thread_filter.latest_result_context = _build_latest_flight_result_context(
            thread=thread,
            results_by_domain=results_by_domain,
        )
        thread_filter.pending_booking = {}
        thread_filter.resolver_trace = ["resolve_flight_turn_filters"]
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
        assistant_message = _append_message(
            thread,
            role=ChatMessage.Role.ASSISTANT,
            content=assistant_content,
            metadata={
                "needs_clarification": needs_clarification,
                "clarification_question": clarification_question,
                "search_domains": search_domains,
                "results_by_domain": results_by_domain,
                "active_filters": thread_filter.active_filters,
                "latest_result_context": thread_filter.latest_result_context,
                "pending_booking": thread_filter.pending_booking,
            },
        )
        thread.last_message_preview = assistant_content[:500]
        thread.last_activity_at = timezone.now()
        thread.save(update_fields=["mode", "last_message_preview", "last_activity_at", "updated_at"])

    return {
        "thread": {
            "id": str(thread.id),
            "title": thread.title,
            "mode": thread.mode,
            "status": thread.status,
            "last_message_preview": thread.last_message_preview,
            "last_activity_at": thread.last_activity_at.isoformat(),
        },
        "assistant_message": {
            "id": str(assistant_message.id),
            "thread_id": str(thread.id),
            "position": assistant_message.position,
            "role": assistant_message.role,
            "content": assistant_message.content,
            "metadata": assistant_message.metadata,
            "created_at": assistant_message.created_at.isoformat(),
        },
        "active_filters": thread_filter.active_filters,
        "search_domains": search_domains,
        "results_by_domain": results_by_domain,
        "latest_result_context": thread_filter.latest_result_context,
        "pending_booking": thread_filter.pending_booking,
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
    }


def _process_booking_resolution(
    *,
    thread: ChatThread,
    thread_filter: ThreadFilter,
    current_filters: FlightFilters,
    booking_resolution: FlightBookingTurnResolution,
) -> dict[str, Any]:
    search_domains: list[str] = []
    results_by_domain: dict[str, Any] = {}
    needs_clarification = booking_resolution.action in {"ambiguous", "no_match"}
    clarification_question = booking_resolution.message if needs_clarification else None
    assistant_content = booking_resolution.message.strip()
    booking_action = booking_resolution.action
    selected_offer_snapshot: dict[str, Any] = {}
    booking_payload: dict[str, Any] = {}

    if booking_resolution.action == "selection_pending":
        listing_code = booking_resolution.listing_code.strip()
        if not listing_code:
            booking_action = "no_match"
            needs_clarification = True
            clarification_question = "Please pick a flight from the visible results."
            assistant_content = clarification_question
        else:
            try:
                pending_booking = select_thread_pending_flight_booking(
                    thread_filter=thread_filter,
                    listing_code=listing_code,
                )
                selected_offer_snapshot = pending_booking.get("event_snapshot", {})
                assistant_content = (
                    assistant_content
                    or "Great choice. Reply yes to confirm this flight, or share passenger name to continue booking."
                )
            except ChatTurnError as exc:
                booking_action = "no_match"
                needs_clarification = True
                clarification_question = str(exc)
                assistant_content = clarification_question
    elif booking_resolution.action == "booking_cleared":
        clear_thread_pending_flight_booking(thread_filter=thread_filter)
        has_filters = bool(_compact_filter_state(current_filters.model_dump(exclude_none=True)))
        if has_filters:
            search_result = search_flight_offers(current_filters.model_dump(exclude_none=True, exclude_defaults=True))
            results_by_domain = {"flights": search_result.to_dict()}
            search_domains = ["flights"] if search_result.count else []
            thread_filter.latest_result_context = _build_latest_flight_result_context(
                thread=thread,
                results_by_domain=results_by_domain,
            )
            thread_filter.save(update_fields=["latest_result_context", "updated_at"])
            if search_result.count:
                assistant_content = (
                    assistant_content
                    or f"Selection cleared. I found {search_result.count} flights from your current filters."
                )
            else:
                assistant_content = assistant_content or "Selection cleared."
        else:
            assistant_content = assistant_content or "Selection cleared."
    elif booking_resolution.action == "awaiting_user_info":
        pending_booking = get_pending_flight_booking(thread_filter=thread_filter)
        requested_field = str(pending_booking.get("awaiting_field") or "").strip() or booking_resolution.requested_field.strip()
        captured_value = booking_resolution.captured_value.strip()
        if requested_field and captured_value:
            capture_result = capture_thread_flight_booking_user_info(
                thread_filter=thread_filter,
                field_name=requested_field,
                value=captured_value,
            )
            if capture_result.get("status") == "invalid_user_info":
                booking_action = "no_match"
                needs_clarification = True
                clarification_question = capture_result.get("message") or "Please share valid passenger info."
                assistant_content = clarification_question

        if booking_action != "no_match":
            try:
                confirm_result = attempt_thread_pending_flight_booking_confirmation(
                    thread=thread,
                    thread_filter=thread_filter,
                    confirmed_via="chat_flight_flow",
                )
                if confirm_result["status"] == "missing_user_info":
                    booking_action = "awaiting_user_info"
                    needs_clarification = False
                    clarification_question = None
                    assistant_content = assistant_content or confirm_result["message"]
                else:
                    booking_action = "booking_confirmed"
                    booking_payload = confirm_result["booking"]
                    assistant_content = (
                        f"Flight booking confirmed. Your reference is {booking_payload['booking_reference']}."
                    )
            except ChatTurnError as exc:
                booking_action = "no_match"
                needs_clarification = True
                clarification_question = str(exc)
                assistant_content = clarification_question
        selected_offer_snapshot = (
            get_pending_flight_booking(thread_filter=thread_filter).get("event_snapshot", {})
            or pending_booking.get("event_snapshot", {})
        )
    elif booking_resolution.action == "booking_confirmed":
        try:
            confirm_result = attempt_thread_pending_flight_booking_confirmation(
                thread=thread,
                thread_filter=thread_filter,
                confirmed_via="chat_flight_flow",
            )
            if confirm_result["status"] == "missing_user_info":
                booking_action = "awaiting_user_info"
                assistant_content = confirm_result["message"]
            else:
                booking_action = "booking_confirmed"
                booking_payload = confirm_result["booking"]
                assistant_content = f"Flight booking confirmed. Your reference is {booking_payload['booking_reference']}."
        except ChatTurnError as exc:
            booking_action = "no_match"
            needs_clarification = True
            clarification_question = str(exc)
            assistant_content = clarification_question
    elif booking_resolution.action in {"ambiguous", "no_match"}:
        assistant_content = assistant_content or "Please pick a flight from the latest shown results."
    else:
        booking_action = "none"
        assistant_content = assistant_content or "I can help with flights."

    pending_booking_state = get_pending_flight_booking(thread_filter=thread_filter)
    if not selected_offer_snapshot:
        selected_offer_snapshot = pending_booking_state.get("event_snapshot", {})

    thread.mode = ChatThread.Mode.FLIGHTS
    thread_filter.resolver_trace = ["resolve_flight_booking_turn"]
    thread_filter.version += 1
    thread_filter.last_resolved_at = timezone.now()
    thread_filter.save(update_fields=["resolver_trace", "version", "last_resolved_at", "updated_at"])

    assistant_message = _append_message(
        thread,
        role=ChatMessage.Role.ASSISTANT,
        content=assistant_content,
        metadata={
            "booking_action": booking_action,
            "listing_code": pending_booking_state.get("listing_code", booking_resolution.listing_code),
            "requested_field": pending_booking_state.get("awaiting_field")
            or booking_resolution.requested_field,
            "selected_event": selected_offer_snapshot,
            "pending_booking": pending_booking_state,
            "booking": booking_payload or booking_resolution.booking.model_dump(exclude_none=True, exclude_defaults=True),
            "candidates": booking_resolution.candidates,
            "search_domains": search_domains,
            "results_by_domain": results_by_domain,
            "active_filters": thread_filter.active_filters,
            "latest_result_context": thread_filter.latest_result_context,
            "needs_clarification": needs_clarification,
            "clarification_question": clarification_question,
            "booking_reference": booking_payload.get("booking_reference") if booking_payload else "",
        },
    )

    thread.last_message_preview = assistant_content[:500]
    thread.last_activity_at = timezone.now()
    thread.save(
        update_fields=[
            "mode",
            "status",
            "last_message_preview",
            "last_activity_at",
            "updated_at",
        ]
    )

    return {
        "thread": {
            "id": str(thread.id),
            "title": thread.title,
            "mode": thread.mode,
            "status": thread.status,
            "last_message_preview": thread.last_message_preview,
            "last_activity_at": thread.last_activity_at.isoformat(),
        },
        "assistant_message": {
            "id": str(assistant_message.id),
            "thread_id": str(thread.id),
            "position": assistant_message.position,
            "role": assistant_message.role,
            "content": assistant_message.content,
            "metadata": assistant_message.metadata,
            "created_at": assistant_message.created_at.isoformat(),
        },
        "active_filters": thread_filter.active_filters,
        "search_domains": search_domains,
        "results_by_domain": results_by_domain,
        "latest_result_context": thread_filter.latest_result_context,
        "pending_booking": pending_booking_state,
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
    }


def _build_pending_soft_redirect_payload(
    *,
    thread: ChatThread,
    thread_filter: ThreadFilter,
    assistant_content: str,
) -> dict[str, Any]:
    thread.mode = ChatThread.Mode.FLIGHTS
    thread_filter.resolver_trace = ["resolve_flight_booking_turn"]
    thread_filter.version += 1
    thread_filter.last_resolved_at = timezone.now()
    thread_filter.save(update_fields=["resolver_trace", "version", "last_resolved_at", "updated_at"])

    assistant_message = _append_message(
        thread,
        role=ChatMessage.Role.ASSISTANT,
        content=assistant_content,
        metadata={
            "booking_action": "none",
            "selected_event": (thread_filter.pending_booking or {}).get("event_snapshot", {}),
            "pending_booking": thread_filter.pending_booking,
            "search_domains": [],
            "results_by_domain": {},
            "active_filters": thread_filter.active_filters,
            "latest_result_context": thread_filter.latest_result_context,
            "needs_clarification": False,
            "clarification_question": None,
        },
    )
    thread.last_message_preview = assistant_content[:500]
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=["mode", "last_message_preview", "last_activity_at", "updated_at"])

    return {
        "thread": {
            "id": str(thread.id),
            "title": thread.title,
            "mode": thread.mode,
            "status": thread.status,
            "last_message_preview": thread.last_message_preview,
            "last_activity_at": thread.last_activity_at.isoformat(),
        },
        "assistant_message": {
            "id": str(assistant_message.id),
            "thread_id": str(thread.id),
            "position": assistant_message.position,
            "role": assistant_message.role,
            "content": assistant_message.content,
            "metadata": assistant_message.metadata,
            "created_at": assistant_message.created_at.isoformat(),
        },
        "active_filters": thread_filter.active_filters,
        "search_domains": [],
        "results_by_domain": {},
        "latest_result_context": thread_filter.latest_result_context,
        "pending_booking": thread_filter.pending_booking,
        "needs_clarification": False,
        "clarification_question": None,
    }


def _get_or_create_thread_filter(thread: ChatThread, *, lock: bool) -> ThreadFilter:
    queryset = ThreadFilter.objects.select_for_update() if lock else ThreadFilter.objects
    thread_filter = queryset.filter(thread=thread).first()
    if thread_filter is None:
        thread_filter = ThreadFilter.objects.create(thread=thread)
    return thread_filter


def _next_message_position(thread: ChatThread) -> int:
    max_position = thread.messages.aggregate(max_position=Max("position"))["max_position"] or 0
    return max_position + 1


def _append_message(
    thread: ChatThread,
    *,
    role: str,
    content: str,
    metadata: dict[str, Any],
) -> ChatMessage:
    return ChatMessage.objects.create(
        thread=thread,
        position=_next_message_position(thread),
        role=role,
        content=content,
        metadata=metadata,
    )


def _assert_thread_accepts_messages(thread: ChatThread) -> None:
    if thread.status == ChatThread.Status.ARCHIVED:
        raise ChatTurnError("This thread is archived and cannot accept new messages.", status_code=409)
    if thread.status == ChatThread.Status.DELETED:
        raise ChatTurnError("This thread has been deleted.", status_code=409)


def _merge_filter_state(
    *,
    current_filters: FlightFilters,
    updates: FlightFilters,
    clear_fields: list[str],
) -> FlightFilters:
    payload = current_filters.model_dump(exclude_none=True)
    updates_payload = updates.model_dump(exclude_none=True, exclude_defaults=True)
    for clear_field in clear_fields:
        payload.pop(clear_field, None)
    for key, value in updates_payload.items():
        if value in (None, [], ""):
            continue
        payload[key] = value
    return FlightFilters.model_validate(payload)


def _compact_filter_state(raw_filters: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in raw_filters.items():
        if value in (None, "", [], {}):
            continue
        compact[key] = value
    return compact


def _build_latest_flight_result_context(*, thread: ChatThread, results_by_domain: dict[str, Any]) -> dict[str, Any]:
    flights_payload = results_by_domain.get("flights", {})
    raw_results = flights_payload.get("results", [])
    results = []
    for idx, item in enumerate(raw_results, start=1):
        results.append(
            {
                "position": idx,
                "domain": "flights",
                "listing_code": item.get("listing_code", ""),
                "title": item.get("title", ""),
                "city": item.get("destination_city", ""),
                "venue_name": item.get("airline_name", ""),
                "event_date": item.get("departure_date", ""),
                "start_at": item.get("departure_at", ""),
                "origin_city": item.get("origin_city", ""),
                "destination_city": item.get("destination_city", ""),
                "airline_name": item.get("airline_name", ""),
                "flight_number": item.get("flight_number", ""),
                "cabin_class": item.get("cabin_class", ""),
                "stops": item.get("stops", 0),
                "currency": item.get("currency"),
                "total_amount": item.get("total_amount"),
                "min_price": item.get("total_amount"),
            }
        )
    return {
        "thread_id": str(thread.id),
        "captured_at": timezone.now().isoformat(),
        "search_domains": ["flights"] if raw_results else [],
        "results": results,
    }
