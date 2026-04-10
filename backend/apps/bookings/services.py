from __future__ import annotations

import re
from datetime import datetime
from secrets import token_hex
from typing import Any

from django.utils import timezone

from apps.bookings.models import Booking
from apps.chats.models import ChatMessage, ChatThread, ThreadFilter
from apps.events.models import MovieEvent, SportEvent
from apps.events.services import search_movie_events, search_sport_events

REQUIRED_BOOKING_USER_FIELDS = ("name", "email", "contact_number")
FIELD_PROMPTS = {
    "name": "Please share your full name to complete the booking.",
    "email": "Please share your email address to complete the booking.",
    "contact_number": "Please share your contact number to complete the booking.",
}


def create_booking_from_listing(
    *,
    thread: ChatThread,
    thread_filter: ThreadFilter | None,
    listing_code: str,
    confirmed_via: str,
    append_confirmation_message: bool = True,
) -> tuple[Booking, bool]:
    """Create a booking for the given thread and listing code, or return the existing one."""
    event_type, event_obj, event_snapshot = resolve_event_by_listing_code(listing_code)
    if event_obj is None:
        raise BookingFlowError("No event found for the given listing_code", status_code=404)

    existing_booking = find_existing_booking(thread=thread, listing_code=listing_code)
    if existing_booking is not None:
        return existing_booking, True

    if thread.status == ChatThread.Status.BOOKED:
        raise BookingFlowError(
            "This thread already has a confirmed booking. Start a new thread to book another event.",
            status_code=409,
        )

    customer_info = (thread_filter.pending_booking or {}).get("customer_info", {}) if thread_filter else {}

    booking = Booking.objects.create(
        thread=thread,
        booking_reference=generate_booking_reference(),
        event_type=event_type,
        status=Booking.Status.CONFIRMED,
        movie_event=event_obj if event_type == Booking.EventType.MOVIE else None,
        sport_event=event_obj if event_type == Booking.EventType.SPORT else None,
        event_title=event_snapshot["title"],
        customer_name=customer_info.get("name", ""),
        customer_email=customer_info.get("email", ""),
        customer_contact_number=customer_info.get("contact_number", ""),
        city=event_snapshot["city"],
        venue_name=event_snapshot["venue_name"],
        starts_at=parse_starts_at(event_snapshot["start_at"]),
        filter_snapshot=(thread_filter.active_filters if thread_filter else {}),
        event_snapshot=event_snapshot,
        metadata={
            "confirmed_via": confirmed_via,
            "customer_info": customer_info,
        },
    )

    if append_confirmation_message:
        confirmation_message = (
            f"Booking confirmed for {booking.event_title} in {booking.city} at "
            f"{booking.venue_name}. Your reference is {booking.booking_reference}."
        )
        append_booking_confirmation_message(
            thread=thread,
            booking=booking,
            confirmation_message=confirmation_message,
            listing_code=listing_code,
        )
    else:
        thread.status = ChatThread.Status.BOOKED
        thread.last_message_preview = booking.event_title[:500]
        thread.last_activity_at = timezone.now()
        thread.save(update_fields=["status", "last_message_preview", "last_activity_at", "updated_at"])

    if thread_filter is not None:
        thread_filter.pending_booking = {}
        thread_filter.save(update_fields=["pending_booking", "updated_at"])

    return booking, False


def get_current_thread_result_context(*, thread_filter: ThreadFilter) -> dict[str, Any]:
    return thread_filter.latest_result_context or {}


def get_pending_thread_booking(*, thread_filter: ThreadFilter) -> dict[str, Any]:
    return thread_filter.pending_booking or {}


def get_thread_booking_context(*, thread_filter: ThreadFilter) -> dict[str, Any]:
    pending_booking = get_pending_thread_booking(thread_filter=thread_filter)
    return {
        "active_filters": thread_filter.active_filters or {},
        "latest_result_context": get_current_thread_result_context(thread_filter=thread_filter),
        "pending_booking": pending_booking,
        "missing_fields": get_missing_booking_user_fields(pending_booking.get("customer_info", {})),
    }


def mark_thread_pending_booking(*, thread_filter: ThreadFilter, listing_code: str) -> dict[str, Any]:
    context = get_current_thread_result_context(thread_filter=thread_filter)
    result_match = next(
        (result for result in context.get("results", []) if result.get("listing_code") == listing_code),
        None,
    )
    if result_match is None:
        raise BookingFlowError("That event is not available in the current thread result context.", status_code=404)

    pending_booking = {
        "status": "pending_confirmation",
        "listing_code": listing_code,
        "event_snapshot": result_match,
        "selected_at": timezone.now().isoformat(),
        "awaiting_field": None,
        "customer_info": {
            "name": "",
            "email": "",
            "contact_number": "",
        },
    }
    thread_filter.pending_booking = pending_booking
    thread_filter.save(update_fields=["pending_booking", "updated_at"])
    return pending_booking


def select_thread_pending_booking(*, thread_filter: ThreadFilter, listing_code: str) -> dict[str, Any]:
    pending_booking = mark_thread_pending_booking(thread_filter=thread_filter, listing_code=listing_code)
    return {
        "status": "selection_pending",
        "message": "The event has been selected and is waiting for booking confirmation.",
        "pending_booking": pending_booking,
    }


def clear_thread_pending_booking(*, thread_filter: ThreadFilter) -> dict[str, Any]:
    thread_filter.pending_booking = {}
    thread_filter.save(update_fields=["pending_booking", "updated_at"])
    return {}


def cancel_thread_pending_booking(*, thread_filter: ThreadFilter) -> dict[str, Any]:
    clear_thread_pending_booking(thread_filter=thread_filter)
    return {
        "status": "booking_cleared",
        "message": "The selected event has been cleared for this thread.",
        "pending_booking": {},
    }


def confirm_thread_pending_booking(
    *,
    thread: ChatThread,
    thread_filter: ThreadFilter,
    confirmed_via: str,
    append_confirmation_message: bool = True,
) -> tuple[Booking, bool]:
    pending_booking = get_pending_thread_booking(thread_filter=thread_filter)
    listing_code = pending_booking.get("listing_code")
    if not listing_code:
        raise BookingFlowError("No pending booking is selected for this thread.", status_code=409)

    return create_booking_from_listing(
        thread=thread,
        thread_filter=thread_filter,
        listing_code=listing_code,
        confirmed_via=confirmed_via,
        append_confirmation_message=append_confirmation_message,
    )


def attempt_thread_pending_booking_confirmation(
    *,
    thread: ChatThread,
    thread_filter: ThreadFilter,
    confirmed_via: str,
    append_confirmation_message: bool = True,
) -> dict[str, Any]:
    pending_booking = get_pending_thread_booking(thread_filter=thread_filter)
    listing_code = pending_booking.get("listing_code")
    if not listing_code:
        raise BookingFlowError("No pending booking is selected for this thread.", status_code=409)

    missing_fields = get_missing_booking_user_fields(pending_booking.get("customer_info", {}))
    if missing_fields:
        next_field = missing_fields[0]
        updated_pending_booking = {
            **pending_booking,
            "status": "awaiting_user_info",
            "awaiting_field": next_field,
        }
        thread_filter.pending_booking = updated_pending_booking
        thread_filter.save(update_fields=["pending_booking", "updated_at"])
        return {
            "status": "missing_user_info",
            "next_required_field": next_field,
            "message": FIELD_PROMPTS[next_field],
            "pending_booking": updated_pending_booking,
        }

    booking, already_confirmed = confirm_thread_pending_booking(
        thread=thread,
        thread_filter=thread_filter,
        confirmed_via=confirmed_via,
        append_confirmation_message=append_confirmation_message,
    )
    return {
        "status": "confirmed",
        "booking": serialize_booking(booking),
        "already_confirmed": already_confirmed,
    }


def save_thread_booking_user_info(*, thread_filter: ThreadFilter, field_name: str, value: str) -> dict[str, Any]:
    pending_booking = get_pending_thread_booking(thread_filter=thread_filter)
    listing_code = pending_booking.get("listing_code")
    if not listing_code:
        raise BookingFlowError("No pending booking is selected for this thread.", status_code=409)

    field_name = field_name.strip()
    if field_name not in REQUIRED_BOOKING_USER_FIELDS:
        raise BookingFlowError(f"Unsupported booking info field: {field_name}", status_code=400)

    normalized_value = _normalize_booking_user_value(field_name=field_name, value=value)
    customer_info = {
        "name": "",
        "email": "",
        "contact_number": "",
        **(pending_booking.get("customer_info", {}) or {}),
    }
    customer_info[field_name] = normalized_value

    updated_pending_booking = {
        **pending_booking,
        "status": "awaiting_user_info",
        "customer_info": customer_info,
        "awaiting_field": None,
    }
    thread_filter.pending_booking = updated_pending_booking
    thread_filter.save(update_fields=["pending_booking", "updated_at"])
    return updated_pending_booking


def capture_thread_booking_user_info(*, thread_filter: ThreadFilter, field_name: str, value: str) -> dict[str, Any]:
    try:
        pending_booking = save_thread_booking_user_info(
            thread_filter=thread_filter,
            field_name=field_name,
            value=value,
        )
    except BookingFlowError as exc:
        return {
            "status": "invalid_user_info",
            "message": str(exc),
            "pending_booking": get_pending_thread_booking(thread_filter=thread_filter),
            "field_name": field_name,
        }

    return {
        "status": "saved",
        "message": "The booking information has been saved.",
        "pending_booking": pending_booking,
        "field_name": field_name,
    }


def append_booking_confirmation_message(
    *,
    thread: ChatThread,
    booking: Booking,
    confirmation_message: str,
    listing_code: str,
) -> None:
    """Update the thread to booked state and append a confirmation assistant message."""
    thread.status = ChatThread.Status.BOOKED
    thread.last_message_preview = confirmation_message[:500]
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=["status", "last_message_preview", "last_activity_at", "updated_at"])

    next_position = (thread.messages.order_by("-position").values_list("position", flat=True).first() or 0) + 1
    ChatMessage.objects.create(
        thread=thread,
        position=next_position,
        role=ChatMessage.Role.ASSISTANT,
        content=confirmation_message,
        metadata={
            "booking_id": str(booking.id),
            "booking_reference": booking.booking_reference,
            "listing_code": listing_code,
        },
    )


def build_latest_result_context(
    *,
    thread: ChatThread,
    search_domains: list[str],
    results_by_domain: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Capture the ordered result context last shown in the thread for later booking resolution."""
    ordered_results: list[dict[str, Any]] = []
    for domain in search_domains:
        domain_results = results_by_domain.get(domain, {})
        for index, result in enumerate(domain_results.get("results", []), start=1):
            ordered_results.append(
                {
                    "position": len(ordered_results) + 1,
                    "domain": domain,
                    "listing_code": result["listing_code"],
                    "title": result.get("title", ""),
                    "city": result.get("city", ""),
                    "venue_name": result.get("venue_name", ""),
                    "event_date": result.get("event_date", ""),
                    "start_at": result.get("start_at", ""),
                    "min_price": result.get("min_price"),
                    "max_price": result.get("max_price"),
                    "sport_type": result.get("sport_type"),
                    "genres": result.get("genres", []),
                    "display_index_within_domain": index,
                }
            )

    return {
        "thread_id": str(thread.id),
        "captured_at": timezone.now().isoformat(),
        "search_domains": search_domains,
        "results": ordered_results,
    }


def find_existing_booking(*, thread: ChatThread, listing_code: str) -> Booking | None:
    for booking in thread.bookings.all().order_by("-confirmed_at"):
        event_snapshot = booking.event_snapshot or {}
        if event_snapshot.get("listing_code") == listing_code:
            return booking
    return None


def resolve_event_by_listing_code(listing_code: str):
    movie_result = search_movie_events({"listing_codes": [listing_code]}, limit=1, offset=0)
    if movie_result.results:
        movie_event = MovieEvent.objects.get(listing_code=listing_code)
        return Booking.EventType.MOVIE, movie_event, movie_result.results[0]

    sport_result = search_sport_events({"listing_codes": [listing_code]}, limit=1, offset=0)
    if sport_result.results:
        sport_event = SportEvent.objects.get(listing_code=listing_code)
        return Booking.EventType.SPORT, sport_event, sport_result.results[0]

    return None, None, None


def generate_booking_reference() -> str:
    return f"ATD-{token_hex(4).upper()}"


def parse_starts_at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def serialize_booking(booking: Booking) -> dict[str, object]:
    return {
        "id": str(booking.id),
        "thread_id": str(booking.thread_id) if booking.thread_id else None,
        "booking_reference": booking.booking_reference,
        "event_type": booking.event_type,
        "status": booking.status,
        "event_title": booking.event_title,
        "customer_name": booking.customer_name,
        "customer_email": booking.customer_email,
        "customer_contact_number": booking.customer_contact_number,
        "city": booking.city,
        "venue_name": booking.venue_name,
        "starts_at": booking.starts_at.isoformat(),
        "confirmed_at": booking.confirmed_at.isoformat(),
        "filter_snapshot": booking.filter_snapshot,
        "event_snapshot": booking.event_snapshot,
    }


def get_missing_booking_user_fields(customer_info: dict[str, Any] | None) -> list[str]:
    normalized_info = customer_info or {}
    return [field_name for field_name in REQUIRED_BOOKING_USER_FIELDS if not str(normalized_info.get(field_name, "")).strip()]


def _normalize_booking_user_value(*, field_name: str, value: str) -> str:
    cleaned_value = value.strip()
    if not cleaned_value:
        raise BookingFlowError(f"Please provide a valid {field_name.replace('_', ' ')}.", status_code=400)

    if field_name == "name":
        if len(cleaned_value) < 2:
            raise BookingFlowError("Please provide your full name.", status_code=400)
        return cleaned_value

    if field_name == "email":
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned_value):
            raise BookingFlowError("Please provide a valid email address.", status_code=400)
        return cleaned_value.lower()

    if field_name == "contact_number":
        digits = re.sub(r"\D", "", cleaned_value)
        if not 10 <= len(digits) <= 15:
            raise BookingFlowError("Please provide a valid contact number.", status_code=400)
        return cleaned_value

    raise BookingFlowError(f"Unsupported booking info field: {field_name}", status_code=400)


class BookingFlowError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
