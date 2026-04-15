from __future__ import annotations

import re
from datetime import datetime, timezone
from secrets import token_hex
from typing import Any

from sqlalchemy import func, select

from apps.agents.services import ChatTurnError
from flask_app.db import get_session
from flask_app.orm.models import ChatMessage, ChatThread, ThreadFilter, FlightBooking, FlightOffer

REQUIRED_FLIGHT_BOOKING_USER_FIELDS = ("name", "email", "contact_number")
FLIGHT_FIELD_PROMPTS = {
    "name": "Please share passenger full name to continue this flight booking.",
    "email": "Please share passenger email address to continue this flight booking.",
    "contact_number": "Please share passenger contact number to continue this flight booking.",
}


def get_pending_flight_booking(*, thread_filter: ThreadFilter) -> dict[str, Any]:
    return thread_filter.pending_booking or {}


def get_missing_flight_booking_user_fields(customer_info: dict[str, Any] | None) -> list[str]:
    normalized = customer_info or {}
    missing: list[str] = []
    for field_name in REQUIRED_FLIGHT_BOOKING_USER_FIELDS:
        if not str(normalized.get(field_name, "")).strip():
            missing.append(field_name)
    return missing


def select_thread_pending_flight_booking(*, thread_filter: ThreadFilter, listing_code: str) -> dict[str, Any]:
    context = thread_filter.latest_result_context or {}
    selected = next(
        (result for result in context.get("results", []) if result.get("listing_code") == listing_code),
        None,
    )
    if selected is None:
        raise ChatTurnError("That flight is not available in the current results.", status_code=404)

    existing_pending = get_pending_flight_booking(thread_filter=thread_filter)
    existing_customer_info = existing_pending.get("customer_info", {}) or {}
    pending_booking = {
        "status": "pending_confirmation",
        "listing_code": listing_code,
        "event_snapshot": selected,
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "awaiting_field": None,
        "customer_info": {
            "name": existing_customer_info.get("name", ""),
            "email": existing_customer_info.get("email", ""),
            "contact_number": existing_customer_info.get("contact_number", ""),
        },
    }
    thread_filter.pending_booking = pending_booking
    thread_filter.updated_at = datetime.now(timezone.utc)
    session = get_session()
    session.flush()
    return pending_booking


def clear_thread_pending_flight_booking(*, thread_filter: ThreadFilter) -> dict[str, Any]:
    thread_filter.pending_booking = {}
    thread_filter.updated_at = datetime.now(timezone.utc)
    session = get_session()
    session.flush()
    return {}


def save_thread_flight_booking_user_info(*, thread_filter: ThreadFilter, field_name: str, value: str) -> dict[str, Any]:
    pending_booking = get_pending_flight_booking(thread_filter=thread_filter)
    listing_code = pending_booking.get("listing_code")
    if not listing_code:
        raise ChatTurnError("No flight is currently selected for booking.", status_code=409)

    normalized_field_name = field_name.strip()
    if normalized_field_name not in REQUIRED_FLIGHT_BOOKING_USER_FIELDS:
        raise ChatTurnError(f"Unsupported passenger info field: {normalized_field_name}", status_code=400)

    normalized_value = _normalize_user_value(field_name=normalized_field_name, value=value)
    customer_info = {
        "name": "",
        "email": "",
        "contact_number": "",
        **(pending_booking.get("customer_info", {}) or {}),
    }
    customer_info[normalized_field_name] = normalized_value

    updated_pending_booking = {
        **pending_booking,
        "status": "awaiting_user_info",
        "customer_info": customer_info,
        "awaiting_field": None,
    }
    thread_filter.pending_booking = updated_pending_booking
    thread_filter.updated_at = datetime.now(timezone.utc)
    session = get_session()
    session.flush()
    return updated_pending_booking


def capture_thread_flight_booking_user_info(*, thread_filter: ThreadFilter, field_name: str, value: str) -> dict[str, Any]:
    try:
        pending_booking = save_thread_flight_booking_user_info(
            thread_filter=thread_filter,
            field_name=field_name,
            value=value,
        )
    except ChatTurnError as exc:
        return {
            "status": "invalid_user_info",
            "message": str(exc),
            "pending_booking": get_pending_flight_booking(thread_filter=thread_filter),
            "field_name": field_name,
        }

    return {
        "status": "saved",
        "message": "Passenger information saved.",
        "pending_booking": pending_booking,
        "field_name": field_name,
    }


def attempt_thread_pending_flight_booking_confirmation(
    *,
    thread: ChatThread,
    thread_filter: ThreadFilter,
    confirmed_via: str,
) -> dict[str, Any]:
    pending_booking = get_pending_flight_booking(thread_filter=thread_filter)
    listing_code = pending_booking.get("listing_code")
    if not listing_code:
        raise ChatTurnError("No flight is currently selected for booking.", status_code=409)

    missing_fields = get_missing_flight_booking_user_fields(pending_booking.get("customer_info", {}))
    if missing_fields:
        next_field = missing_fields[0]
        updated_pending_booking = {
            **pending_booking,
            "status": "awaiting_user_info",
            "awaiting_field": next_field,
        }
        thread_filter.pending_booking = updated_pending_booking
        thread_filter.updated_at = datetime.now(timezone.utc)
        session = get_session()
        session.flush()
        return {
            "status": "missing_user_info",
            "next_required_field": next_field,
            "message": FLIGHT_FIELD_PROMPTS[next_field],
            "pending_booking": updated_pending_booking,
        }

    booking, already_confirmed = create_flight_booking_from_pending(
        thread=thread,
        thread_filter=thread_filter,
        confirmed_via=confirmed_via,
    )
    return {
        "status": "confirmed",
        "booking": serialize_flight_booking(booking),
        "already_confirmed": already_confirmed,
    }


def create_flight_booking_from_pending(
    *,
    thread: ChatThread,
    thread_filter: ThreadFilter,
    confirmed_via: str,
) -> tuple[FlightBooking, bool]:
    session = get_session()
    now = datetime.now(timezone.utc)
    pending_booking = get_pending_flight_booking(thread_filter=thread_filter)
    listing_code = pending_booking.get("listing_code")
    if not listing_code:
        raise ChatTurnError("No flight is currently selected for booking.", status_code=409)

    existing = session.execute(
        select(FlightBooking).where(
            FlightBooking.thread_id == thread.id,
            FlightBooking.listing_code == listing_code,
        ).order_by(FlightBooking.confirmed_at.desc())
    ).scalar_one_or_none()
    if existing is not None:
        return existing, True

    if thread.status == "booked":
        raise ChatTurnError(
            "This thread already has a confirmed booking. Start a new thread to book another flight.",
            status_code=409,
        )

    offer_snapshot = pending_booking.get("event_snapshot", {}) or {}
    offer = session.execute(
        select(FlightOffer).where(FlightOffer.listing_code == listing_code)
    ).scalar_one_or_none()
    if offer is None:
        raise ChatTurnError("Selected flight could not be found.", status_code=404)

    customer_info = pending_booking.get("customer_info", {}) or {}
    booking = FlightBooking(
        thread_id=thread.id,
        booking_reference=generate_flight_booking_reference(),
        status="confirmed",
        listing_code=listing_code,
        offer_id=offer.id,
        route=f"{offer.origin_city} to {offer.destination_city}",
        origin_city=offer.origin_city,
        origin_iata=offer.origin_iata,
        destination_city=offer.destination_city,
        destination_iata=offer.destination_iata,
        departure_at=offer.departure_at,
        arrival_at=offer.arrival_at,
        departure_date=offer.departure_date,
        airline_name=offer.airline_name,
        flight_number=offer.flight_number,
        cabin_class=offer.cabin_class,
        stops=offer.stops,
        currency=offer.currency,
        total_amount=offer.total_amount,
        passenger_name=customer_info.get("name", ""),
        passenger_email=customer_info.get("email", ""),
        passenger_contact_number=customer_info.get("contact_number", ""),
        filter_snapshot=thread_filter.active_filters or {},
        offer_snapshot=offer_snapshot,
        meta={"confirmed_via": confirmed_via},
        confirmed_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(booking)

    thread.status = "booked"
    thread.last_activity_at = now
    thread.updated_at = now

    thread_filter.pending_booking = {}
    thread_filter.updated_at = now
    session.flush()
    return booking, False


def append_flight_booking_confirmation_message(
    *,
    thread: ChatThread,
    booking: FlightBooking,
    listing_code: str,
) -> ChatMessage:
    session = get_session()
    now = datetime.now(timezone.utc)
    confirmation_message = (
        f"Flight booking confirmed for {booking.route} on {booking.departure_date.isoformat()} "
        f"with {booking.airline_name} {booking.flight_number}. Your reference is {booking.booking_reference}."
    )
    max_position = session.execute(
        select(func.coalesce(func.max(ChatMessage.position), 0)).where(ChatMessage.thread_id == thread.id)
    ).scalar()
    next_position = max_position + 1
    message = ChatMessage(
        thread_id=thread.id,
        position=next_position,
        role="assistant",
        content=confirmation_message,
        meta={
            "booking_reference": booking.booking_reference,
            "listing_code": listing_code,
            "booking_type": "flight",
            "booking_action": "booking_confirmed",
            "booking": serialize_flight_booking(booking),
        },
        created_at=now,
        updated_at=now,
    )
    session.add(message)
    thread.last_message_preview = confirmation_message[:500]
    thread.last_activity_at = now
    thread.updated_at = now
    session.flush()
    return message


def serialize_flight_booking(booking: FlightBooking) -> dict[str, Any]:
    return {
        "id": str(booking.id),
        "thread_id": str(booking.thread_id) if booking.thread_id else None,
        "booking_reference": booking.booking_reference,
        "status": booking.status,
        "listing_code": booking.listing_code,
        "route": booking.route,
        "departure_at": booking.departure_at.isoformat(),
        "airline_name": booking.airline_name,
        "flight_number": booking.flight_number,
        "passenger_name": booking.passenger_name,
        "passenger_email": booking.passenger_email,
        "passenger_contact_number": booking.passenger_contact_number,
        "confirmed_at": booking.confirmed_at.isoformat(),
    }


def generate_flight_booking_reference() -> str:
    return f"FLT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{token_hex(3).upper()}"


def _normalize_user_value(*, field_name: str, value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ChatTurnError(f"{field_name} cannot be empty.", status_code=400)

    if field_name == "email":
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
            raise ChatTurnError("Please provide a valid email address.", status_code=400)
        return normalized.lower()

    if field_name == "contact_number":
        compact = re.sub(r"\s+", "", normalized)
        if not re.match(r"^[+]?[0-9\-()]{7,20}$", compact):
            raise ChatTurnError("Please provide a valid contact number.", status_code=400)
        return compact

    if field_name == "name":
        if len(normalized) < 2:
            raise ChatTurnError("Please provide the passenger full name.", status_code=400)
        return normalized

    return normalized
