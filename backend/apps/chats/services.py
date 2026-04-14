from __future__ import annotations

from typing import Any, Literal

from django.db import transaction
from django.utils import timezone
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from apps.agents.langchain_tools import get_chat_model
from apps.agents.services import ChatTurnError, process_chat_turn
from apps.chats.models import ChatThread, ThreadFilter
from apps.flights.chat_services import process_flight_chat_turn


class ThreadModeDecision(BaseModel):
    mode: Literal["entertainment", "flights"]
    rationale: str = ""
    confidence: float | None = None


def process_unified_chat_turn(*, user_message: str, thread_id: str | None = None) -> dict[str, Any]:
    thread = _get_or_create_thread(thread_id=thread_id)
    _assert_thread_accepts_messages(thread)

    decision = invoke_thread_mode_decision(user_message=user_message, thread=thread)
    _maybe_switch_thread_mode(thread=thread, decision=decision)

    if thread.mode == ChatThread.Mode.FLIGHTS:
        return process_flight_chat_turn(user_message=user_message, thread_id=str(thread.id))
    return process_chat_turn(user_message=user_message, thread_id=str(thread.id))


def _maybe_switch_thread_mode(*, thread: ChatThread, decision: ThreadModeDecision) -> None:
    desired_mode = ChatThread.Mode.FLIGHTS if decision.mode == "flights" else ChatThread.Mode.ENTERTAINMENT
    if thread.mode == ChatThread.Mode.UNKNOWN:
        with transaction.atomic():
            thread.refresh_from_db(fields=["mode", "updated_at"])
            thread.mode = desired_mode
            thread.save(update_fields=["mode", "updated_at"])
        return

    if thread.mode == desired_mode:
        return

    confidence = decision.confidence if decision.confidence is not None else 0.0
    if confidence < 0.75:
        return

    with transaction.atomic():
        thread.refresh_from_db()
        thread_filter = ThreadFilter.objects.select_for_update().get(thread=thread)
        thread.mode = desired_mode
        thread.save(update_fields=["mode", "updated_at"])
        thread_filter.active_filters = {}
        thread_filter.latest_result_context = {}
        thread_filter.pending_booking = {}
        thread_filter.resolver_trace = ["mode_switch"]
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


def _get_or_create_thread(*, thread_id: str | None) -> ChatThread:
    if thread_id:
        thread = (
            ChatThread.objects.exclude(status=ChatThread.Status.DELETED)
            .select_related("filter_state")
            .filter(id=thread_id)
            .first()
        )
        if thread is None:
            raise ChatTurnError("Thread not found", status_code=404)
        return thread

    with transaction.atomic():
        thread = ChatThread.objects.create(
            title="New thread",
            mode=ChatThread.Mode.UNKNOWN,
            last_message_preview="",
            last_activity_at=timezone.now(),
        )
        ThreadFilter.objects.get_or_create(thread=thread)
        return thread


def _assert_thread_accepts_messages(thread: ChatThread) -> None:
    if thread.status == ChatThread.Status.ARCHIVED:
        raise ChatTurnError("This thread is archived and cannot accept new messages.", status_code=409)
    if thread.status == ChatThread.Status.DELETED:
        raise ChatTurnError("This thread has been deleted.", status_code=409)
