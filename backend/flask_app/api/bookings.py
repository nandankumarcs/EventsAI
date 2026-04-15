from __future__ import annotations

import json
from uuid import UUID

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from apps.bookings.services import BookingFlowError, create_booking_from_listing, serialize_booking
from flask_app.db import get_session
from flask_app.orm.models import Booking, ChatThread, ThreadFilter

bookings_api = Blueprint("bookings_api", __name__, url_prefix="/api/bookings")


@bookings_api.route("/", methods=["GET"])
def booking_list_view():
    session = get_session()
    bookings = session.execute(select(Booking)).scalars().all()
    payload = [serialize_booking(booking) for booking in bookings]
    return jsonify({"count": len(payload), "bookings": payload})


@bookings_api.route("/confirm/", methods=["POST"])
def booking_confirm_view():
    try:
        payload = json.loads((request.data or b"").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return jsonify({"error": f"Invalid booking payload: {exc}"}), 400

    thread_id = payload.get("thread_id")
    listing_code = (payload.get("listing_code") or "").strip()
    if not thread_id or not listing_code:
        return jsonify({"error": "thread_id and listing_code are required"}), 400

    session = get_session()
    thread = session.execute(select(ChatThread).where(ChatThread.id == thread_id)).scalar_one_or_none()
    if thread is None:
        return jsonify({"error": "Not found"}), 404

    thread_filter = session.execute(select(ThreadFilter).where(ThreadFilter.thread_id == thread.id)).scalar_one_or_none()

    try:
        booking, already_confirmed = create_booking_from_listing(
            thread=thread,
            thread_filter=thread_filter,
            listing_code=listing_code,
            confirmed_via="chat_button",
        )
    except BookingFlowError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return (
        jsonify({"booking": serialize_booking(booking), "already_confirmed": already_confirmed}),
        200 if already_confirmed else 201,
    )


@bookings_api.route("/<uuid:booking_id>/", methods=["DELETE"])
def booking_delete_view(booking_id: UUID):
    session = get_session()
    booking = session.execute(select(Booking).where(Booking.id == booking_id)).scalar_one_or_none()
    if booking is None:
        return jsonify({"error": "Booking not found"}), 404

    with session.begin():
        session.delete(booking)

    return jsonify({"success": True}), 200
