from json import JSONDecodeError

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.flights.services import (
    get_available_airlines,
    get_available_cabin_classes,
    get_available_destination_cities,
    get_available_origin_cities,
    parse_request_filters,
    search_flight_offers,
)


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


@csrf_exempt
def flight_search_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        filters, limit, offset = parse_request_filters(request.body)
    except (JSONDecodeError, ValueError) as exc:
        return _json_error(f"Invalid flight search payload: {exc}")

    result = search_flight_offers(filters, limit=limit, offset=offset)
    return JsonResponse(result.to_dict())


def flight_origins_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_origin_cities()
    return JsonResponse({"count": len(values), "values": values})


def flight_destinations_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_destination_cities()
    return JsonResponse({"count": len(values), "values": values})


def flight_airlines_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_airlines()
    return JsonResponse({"count": len(values), "values": values})


def flight_cabin_classes_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    values = get_available_cabin_classes()
    return JsonResponse({"count": len(values), "values": values})

