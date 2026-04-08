import json
from json import JSONDecodeError

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from apps.chats.models import ChatThread, ThreadFilter


@csrf_exempt
def thread_list_create_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        threads = [
            _serialize_thread_summary(thread)
            for thread in ChatThread.objects.select_related("filter_state").prefetch_related("messages")
        ]
        return JsonResponse({"count": len(threads), "threads": threads})

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


def thread_detail_view(request: HttpRequest, thread_id) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    thread = get_object_or_404(
        ChatThread.objects.select_related("filter_state").prefetch_related("messages"),
        id=thread_id,
    )
    return JsonResponse({"thread": _serialize_thread_detail(thread)})


def _serialize_thread_summary(thread: ChatThread) -> dict[str, object]:
    return {
        "id": str(thread.id),
        "title": thread.title,
        "status": thread.status,
        "summary": thread.summary,
        "last_message_preview": thread.last_message_preview,
        "last_activity_at": thread.last_activity_at.isoformat(),
        "message_count": thread.messages.count(),
        "active_filters": getattr(getattr(thread, "filter_state", None), "active_filters", {}),
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
