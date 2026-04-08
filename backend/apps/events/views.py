from json import JSONDecodeError

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.events.services import parse_request_filters, search_movie_events, search_sport_events


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


@csrf_exempt
def movie_search_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        filters, limit, offset = parse_request_filters(request.body)
    except (JSONDecodeError, ValueError) as exc:
        return _json_error(f"Invalid movie search payload: {exc}")

    result = search_movie_events(filters, limit=limit, offset=offset)
    return JsonResponse(result.to_dict())


@csrf_exempt
def sport_search_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        filters, limit, offset = parse_request_filters(request.body)
    except (JSONDecodeError, ValueError) as exc:
        return _json_error(f"Invalid sport search payload: {exc}")

    result = search_sport_events(filters, limit=limit, offset=offset)
    return JsonResponse(result.to_dict())
