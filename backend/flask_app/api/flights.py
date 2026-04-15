from __future__ import annotations

from flask import Blueprint, jsonify, request

from apps.flights.services import (
    get_available_airlines,
    get_available_cabin_classes,
    get_available_destination_cities,
    get_available_origin_cities,
    parse_request_filters,
    search_flight_offers,
)


flights_api = Blueprint("flights_api", __name__, url_prefix="/api/flights")


@flights_api.post("/search/")
def flight_search_view():
    try:
        filters, limit, offset = parse_request_filters(request.get_data())
    except Exception as exc:
        return jsonify({"error": f"Invalid flight search payload: {exc}"}), 400

    result = search_flight_offers(filters, limit=limit, offset=offset)
    return jsonify(result.to_dict())


@flights_api.get("/tools/origins/")
def flight_origins_view():
    values = get_available_origin_cities()
    return jsonify({"count": len(values), "values": values})


@flights_api.get("/tools/destinations/")
def flight_destinations_view():
    values = get_available_destination_cities()
    return jsonify({"count": len(values), "values": values})


@flights_api.get("/tools/airlines/")
def flight_airlines_view():
    values = get_available_airlines()
    return jsonify({"count": len(values), "values": values})


@flights_api.get("/tools/cabin-classes/")
def flight_cabin_classes_view():
    values = get_available_cabin_classes()
    return jsonify({"count": len(values), "values": values})
