from json import JSONDecodeError
from datetime import date

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.events.filter_tools import (
    get_all_event_types,
    get_available_movie_genres,
    get_available_movie_languages,
    get_available_movie_locations,
    get_available_movie_titles,
    get_available_movie_venues,
    get_available_sport_featured_athletes,
    get_available_sport_locations,
    get_available_sport_teams,
    get_available_sport_tournaments,
    get_available_sport_types,
    get_available_sport_venues,
)
from apps.events.resolver_utils import normalize_temporal_expression
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


def event_types_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_all_event_types()
    return JsonResponse({"count": len(values), "values": values})


def movie_locations_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_movie_locations()
    return JsonResponse({"count": len(values), "values": values})


def sport_locations_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_sport_locations()
    return JsonResponse({"count": len(values), "values": values})


def movie_languages_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_movie_languages()
    return JsonResponse({"count": len(values), "values": values})


def movie_genres_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_movie_genres()
    return JsonResponse({"count": len(values), "values": values})


def movie_titles_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_movie_titles()
    return JsonResponse({"count": len(values), "values": values})


def movie_venues_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_movie_venues()
    return JsonResponse({"count": len(values), "values": values})


def sport_types_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_sport_types()
    return JsonResponse({"count": len(values), "values": values})


def sport_tournaments_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_sport_tournaments()
    return JsonResponse({"count": len(values), "values": values})


def sport_teams_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_sport_teams()
    return JsonResponse({"count": len(values), "values": values})


def sport_venues_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_sport_venues()
    return JsonResponse({"count": len(values), "values": values})


def sport_featured_athletes_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_sport_featured_athletes()
    return JsonResponse({"count": len(values), "values": values})


@csrf_exempt
def temporal_normalization_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        filters, _limit, _offset = parse_request_filters(request.body)
    except (JSONDecodeError, ValueError) as exc:
        return _json_error(f"Invalid temporal payload: {exc}")

    text = filters.get("text")
    reference_date = filters.get("reference_date")
    if not text:
        return _json_error("Temporal normalization requires a text field.")

    normalized = normalize_temporal_expression(
        text,
        reference_date=None if not reference_date else date.fromisoformat(reference_date),
    )
    return JsonResponse(normalized)
