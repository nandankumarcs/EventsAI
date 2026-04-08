import json
from json import JSONDecodeError

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.agents.services import ChatTurnError, process_chat_turn


@csrf_exempt
def chat_turn_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        return JsonResponse({"error": f"Invalid chat payload: {exc}"}, status=400)

    message = (payload.get("message") or "").strip()
    thread_id = payload.get("thread_id")

    if not message:
        return JsonResponse({"error": "message is required"}, status=400)

    try:
        result = process_chat_turn(user_message=message, thread_id=thread_id)
    except ChatTurnError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status_code)
    return JsonResponse(result)
