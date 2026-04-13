import json
from json import JSONDecodeError

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.chats.models import ChatThread, ThreadFilter


@csrf_exempt
def thread_list_create_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        try:
            limit = int(request.GET.get("limit", 20))
            offset = int(request.GET.get("offset", 0))
        except ValueError:
            return JsonResponse({"error": "Invalid pagination parameters"}, status=400)

        queryset = (
            ChatThread.objects.exclude(status=ChatThread.Status.DELETED)
            .select_related("filter_state")
            .prefetch_related("messages")
            .order_by("-last_activity_at")
        )
        total_count = queryset.count()
        subset = queryset[offset : offset + limit]

        threads = [_serialize_thread_summary(thread) for thread in subset]
        has_more = offset + limit < total_count

        return JsonResponse({"count": total_count, "has_more": has_more, "threads": threads})

    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        return JsonResponse({"error": f"Invalid thread payload: {exc}"}, status=400)

    title = (payload.get("title") or "").strip() or "New thread"
    thread = ChatThread.objects.create(
        title=title[:255],
        last_message_preview="",
    )
    ThreadFilter.objects.get_or_create(thread=thread)

    return JsonResponse({"thread": _serialize_thread_detail(thread)}, status=201)


@csrf_exempt
def thread_detail_view(request: HttpRequest, thread_id) -> JsonResponse:
    if request.method not in ("GET", "DELETE"):
        return HttpResponseNotAllowed(["GET", "DELETE"])

    thread = (
        ChatThread.objects.exclude(status=ChatThread.Status.DELETED)
        .select_related("filter_state")
        .prefetch_related("messages")
        .filter(id=thread_id)
        .first()
    )
    if thread is None:
        return JsonResponse({"error": "Thread not found"}, status=404)

    if request.method == "DELETE":
        thread.status = ChatThread.Status.DELETED
        thread.save(update_fields=["status"])
        return JsonResponse({"success": True})

    return JsonResponse({"thread": _serialize_thread_detail(thread)})


def _serialize_thread_summary(thread: ChatThread) -> dict[str, object]:
    filter_state = getattr(thread, "filter_state", None)
    pending_booking = getattr(filter_state, "pending_booking", {})
    customer_info = pending_booking.get("customer_info", {})
    if not customer_info:
        booking = thread.bookings.order_by("-confirmed_at").first()
        if booking:
            customer_info = {
                "name": booking.customer_name,
                "email": booking.customer_email,
                "contact_number": booking.customer_contact_number,
            }

    return {
        "id": str(thread.id),
        "title": thread.title,
        "status": thread.status,
        "summary": thread.summary,
        "last_message_preview": thread.last_message_preview,
        "last_activity_at": thread.last_activity_at.isoformat(),
        "message_count": thread.messages.count(),
        "active_filters": getattr(filter_state, "active_filters", {}),
        "latest_result_context": getattr(filter_state, "latest_result_context", {}),
        "pending_booking": pending_booking,
        "goal_state": (thread.metadata or {}).get("goal_state", {}),
        "customer_info": customer_info,
    }


def _serialize_thread_detail(thread: ChatThread) -> dict[str, object]:
    return {
        **_serialize_thread_summary(thread),
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
        "messages": [
            {
                "id": str(message.id),
                "position": message.position,
                "role": message.role,
                "content": message.content,
                "tool_name": message.tool_name,
                "metadata": message.metadata,
                "created_at": message.created_at.isoformat(),
            }
            for message in thread.messages.order_by("position", "created_at")
        ],
    }
