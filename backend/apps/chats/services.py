from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from apps.agents.langchain_tools import get_chat_model
from apps.agents.services import ChatTurnError, process_chat_turn
from flask_app.db import get_session
from apps.flights.chat_services import process_flight_chat_turn
from flask_app.orm.models import ChatThread, ThreadFilter


class ThreadModeDecision(BaseModel):
    mode: Literal["entertainment", "flights"]
    rationale: str = ""
    confidence: float | None = None


def process_unified_chat_turn(*, user_message: str, thread_id: str | None = None) -> dict[str, Any]:
    # Phase 1: Get/create thread and determine mode
    session = get_session()
    thread = _get_or_create_thread_nested(thread_id=thread_id, session=session)
    _assert_thread_accepts_messages(thread)

    decision = invoke_thread_mode_decision(user_message=user_message, thread=thread)
    _maybe_switch_thread_mode(thread=thread, decision=decision, session=session)

    # Re-fetch thread after potential mode switch
    thread = session.execute(
        select(ChatThread).where(ChatThread.id == thread.id)
    ).scalar_one()
    current_mode = thread.mode
    current_thread_id = str(thread.id)

    # Phase 2: Route to appropriate handler
    if current_mode == "flights":
        return process_flight_chat_turn(user_message=user_message, thread_id=current_thread_id)
    return process_chat_turn(user_message=user_message, thread_id=current_thread_id)


def _maybe_switch_thread_mode(*, thread: ChatThread, decision: ThreadModeDecision, session) -> None:
    desired_mode = "flights" if decision.mode == "flights" else "entertainment"
    now = datetime.now(timezone.utc)

    if thread.mode == "unknown":
        locked_thread = session.execute(
            select(ChatThread).where(ChatThread.id == thread.id).with_for_update()
        ).scalar_one()
        locked_thread.mode = desired_mode
        locked_thread.updated_at = now
        return

    if thread.mode == desired_mode:
        return

    confidence = decision.confidence if decision.confidence is not None else 0.0
    if confidence < 0.75:
        return

    locked_thread = session.execute(
        select(ChatThread).where(ChatThread.id == thread.id).with_for_update()
    ).scalar_one()
    thread_filter = session.execute(
        select(ThreadFilter).where(ThreadFilter.thread_id == locked_thread.id).with_for_update()
    ).scalar_one()

    locked_thread.mode = desired_mode
    locked_thread.updated_at = now

    thread_filter.active_filters = {}
    thread_filter.latest_result_context = {}
    thread_filter.pending_booking = {}
    thread_filter.resolver_trace = ["mode_switch"]
    thread_filter.version = int(thread_filter.version or 0) + 1
    thread_filter.last_resolved_at = now
    thread_filter.updated_at = now


def invoke_thread_mode_decision(*, user_message: str, thread: ChatThread) -> ThreadModeDecision:
    llm = get_chat_model(resolver=True)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Route this chat turn to either entertainment mode or flights mode.\n"
                "Return flights only if the user intent is clearly flight travel search or flight booking.\n"
                "Return entertainment for movie/sports planning, event booking, or non-flight planning.\n"
                "If the user is switching domains mid-thread, reflect that by returning the new mode.\n"
                "Always include confidence as a 0 to 1 float.\n"
                "Use only the schema. No extra text.",
            ),
            (
                "user",
                "Thread title: {thread_title}\n"
                "Current thread mode: {thread_mode}\n"
                "User message: {user_message}",
            ),
        ]
    )
    chain = prompt | llm.with_structured_output(ThreadModeDecision)
    return chain.invoke(
        {
            "thread_title": thread.title,
            "thread_mode": thread.mode,
            "user_message": user_message,
        }
    )


def _get_thread_by_id(*, thread_id: str, session) -> ChatThread:
    from uuid import UUID
    thread_uuid = UUID(thread_id) if isinstance(thread_id, str) else thread_id
    thread = session.execute(
        select(ChatThread).where(ChatThread.id == thread_uuid).where(ChatThread.status != "deleted")
    ).scalar_one_or_none()
    if thread is None:
        raise ChatTurnError("Thread not found", status_code=404)
    return thread


def _get_or_create_thread(*, thread_id: str | None, session=None) -> ChatThread:
    from uuid import UUID
    if session is None:
        session = get_session()
    now = datetime.now(timezone.utc)
    if thread_id:
        return _get_thread_by_id(thread_id=thread_id, session=session)

    with session.begin():
        thread = ChatThread(
            title="New thread",
            summary="",
            mode="unknown",
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
    return thread


def _get_or_create_thread_nested(*, thread_id: str | None, session) -> ChatThread:
    """Version for use inside an existing transaction - does not call session.begin()."""
    from uuid import UUID
    now = datetime.now(timezone.utc)
    if thread_id:
        return _get_thread_by_id(thread_id=thread_id, session=session)

    # Already inside transaction, don't call session.begin()
    thread = ChatThread(
        title="New thread",
        summary="",
        mode="unknown",
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
    return thread


def _assert_thread_accepts_messages(thread: ChatThread) -> None:
    if thread.status == "archived":
        raise ChatTurnError("This thread is archived and cannot accept new messages.", status_code=409)
    if thread.status == "deleted":
        raise ChatTurnError("This thread has been deleted.", status_code=409)
