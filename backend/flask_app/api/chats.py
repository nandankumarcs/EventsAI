from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, select

from apps.agents.services import ChatTurnError
from apps.chats.services import process_unified_chat_turn
from flask_app.db import get_session
from flask_app.orm.models import Booking, ChatMessage, ChatThread, FlightBooking, ThreadFilter

chats_api = Blueprint("chats_api", __name__, url_prefix="/api/chats")


@chats_api.route("/threads/", methods=["GET", "POST"])
def thread_list_create_view():
    if request.method == "GET":
        try:
            limit = int(request.args.get("limit", 20))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            return jsonify({"error": "Invalid pagination parameters"}), 400

        session = get_session()

        total_count = session.execute(
            select(func.count()).select_from(ChatThread).where(ChatThread.status != "deleted")
        ).scalar_one()

        threads = session.execute(
            select(ChatThread)
            .where(ChatThread.status != "deleted")
            .order_by(ChatThread.last_activity_at.desc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()

        payload = {
            "count": int(total_count),
            "has_more": offset + limit < int(total_count),
            "threads": [_serialize_thread_summary(session, thread) for thread in threads],
        }
        return jsonify(payload)

    try:
        payload = json.loads((request.data or b"{}").decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return jsonify({"error": f"Invalid thread payload: {exc}"}), 400

    title = (payload.get("title") or "").strip() or "New thread"
    mode = payload.get("mode") or "unknown"
    if mode not in {"unknown", "entertainment", "flights"}:
        return jsonify({"error": "Invalid thread mode"}), 400

    session = get_session()
    now = datetime.now().astimezone()
    with session.begin():
        thread = ChatThread(
            title=title[:255],
            summary="",
            mode=mode,
            status="active",
            last_message_preview="",
            last_activity_at=now,
            meta={},
            created_at=now,
            updated_at=now,
        )
        session.add(thread)
        session.flush()

        thread_filter = ThreadFilter(
            thread_id=thread.id,
            active_filters={},
            latest_result_context={},
            pending_booking={},
            resolver_trace=[],
            version=1,
            last_resolved_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(thread_filter)

    return jsonify({"thread": _serialize_thread_detail(session, thread)}), 201


@chats_api.route("/threads/<uuid:thread_id>/", methods=["GET", "DELETE"])
def thread_detail_view(thread_id: UUID):
    session = get_session()

    thread = session.execute(
        select(ChatThread).where(ChatThread.id == thread_id).where(ChatThread.status != "deleted")
    ).scalar_one_or_none()
    if thread is None:
        return jsonify({"error": "Thread not found"}), 404

    if request.method == "DELETE":
        now = datetime.now().astimezone()
        with session.begin():
            locked_thread = session.execute(
                select(ChatThread).where(ChatThread.id == thread.id).with_for_update()
            ).scalar_one()
            locked_thread.status = "deleted"
            locked_thread.updated_at = now
        return jsonify({"success": True})

    return jsonify({"thread": _serialize_thread_detail(session, thread)})


@chats_api.route("/chat/", methods=["POST"])
def chat_turn_view():
    try:
        payload = json.loads((request.data or b"").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return jsonify({"error": f"Invalid chat payload: {exc}"}), 400

    message = (payload.get("message") or "").strip()
    thread_id = payload.get("thread_id")

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        result = process_unified_chat_turn(user_message=message, thread_id=thread_id)
    except ChatTurnError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(result)


def _serialize_thread_summary(session, thread: ChatThread) -> dict[str, object]:
    filter_state = session.execute(select(ThreadFilter).where(ThreadFilter.thread_id == thread.id)).scalar_one_or_none()
    pending_booking = (filter_state.pending_booking if filter_state else {}) or {}
    customer_info = (pending_booking.get("customer_info") or {}) if isinstance(pending_booking, dict) else {}

    if not customer_info:
        booking = session.execute(
            select(Booking).where(Booking.thread_id == thread.id).order_by(Booking.confirmed_at.desc()).limit(1)
        ).scalar_one_or_none()
        if booking:
            customer_info = {
                "name": booking.customer_name,
                "email": booking.customer_email,
                "contact_number": booking.customer_contact_number,
            }

    if not customer_info:
        flight_booking = session.execute(
            select(FlightBooking)
            .where(FlightBooking.thread_id == thread.id)
            .order_by(FlightBooking.confirmed_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if flight_booking:
            customer_info = {
                "name": flight_booking.passenger_name,
                "email": flight_booking.passenger_email,
                "contact_number": flight_booking.passenger_contact_number,
            }

    message_count = session.execute(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.thread_id == thread.id)
    ).scalar_one()

    goal_state = {}
    if isinstance(thread.meta, dict):
        goal_state = thread.meta.get("goal_state") if isinstance(thread.meta.get("goal_state"), dict) else {}

    return {
        "id": str(thread.id),
        "title": thread.title,
        "mode": thread.mode,
        "status": thread.status,
        "summary": thread.summary,
        "last_message_preview": thread.last_message_preview,
        "last_activity_at": thread.last_activity_at.isoformat(),
        "message_count": int(message_count),
        "active_filters": (filter_state.active_filters if filter_state else {}) or {},
        "latest_result_context": (filter_state.latest_result_context if filter_state else {}) or {},
        "pending_booking": pending_booking,
        "goal_state": goal_state,
        "customer_info": customer_info,
    }


def _serialize_thread_detail(session, thread: ChatThread) -> dict[str, object]:
    messages = session.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread.id)
        .order_by(ChatMessage.position.asc(), ChatMessage.created_at.asc())
    ).scalars().all()

    return {
        **_serialize_thread_summary(session, thread),
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
        "messages": [
            {
                "id": str(message.id),
                "position": message.position,
                "role": message.role,
                "content": message.content,
                "tool_name": message.tool_name,
                "metadata": message.meta,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ],
    }
