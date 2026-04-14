from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import Q, QuerySet

from apps.flights.models import FlightOffer

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass
class FlightSearchResult:
    count: int
    limit: int
    offset: int
    filters: dict[str, Any]
    results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "limit": self.limit,
            "offset": self.offset,
            "filters": self.filters,
            "results": self.results,
        }


def parse_request_filters(payload: bytes) -> tuple[dict[str, Any], int, int]:
    data = json.loads(payload or b"{}")
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object.")

    filters = data.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("`filters` must be an object.")

    limit = _parse_int(data.get("limit", DEFAULT_LIMIT), field_name="limit", minimum=1, maximum=MAX_LIMIT)
    offset = _parse_int(data.get("offset", 0), field_name="offset", minimum=0)
    return filters, limit, offset


def search_flight_offers(
    filters: dict[str, Any] | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> FlightSearchResult:
    filters = filters or {}
    queryset = FlightOffer.objects.filter(is_published=True).order_by(
        "departure_date",
        "departure_at",
        "origin_city",
        "destination_city",
    )
    queryset = _apply_flight_filters(queryset, filters)
    return _build_result(queryset, filters, limit, offset)


def get_available_origin_cities() -> list[str]:
    return _distinct_values(FlightOffer.objects.filter(is_published=True), "origin_city")


def get_available_destination_cities() -> list[str]:
    return _distinct_values(FlightOffer.objects.filter(is_published=True), "destination_city")


def get_available_airlines() -> list[str]:
    return _distinct_values(FlightOffer.objects.filter(is_published=True), "airline_name")


def get_available_cabin_classes() -> list[str]:
    return _distinct_values(FlightOffer.objects.filter(is_published=True), "cabin_class")


def _build_result(
    queryset: QuerySet[FlightOffer],
    filters: dict[str, Any],
    limit: int,
    offset: int,
) -> FlightSearchResult:
    normalized_limit = max(1, min(limit, MAX_LIMIT))
    normalized_offset = max(0, offset)
    page = list(queryset[normalized_offset : normalized_offset + normalized_limit])
    return FlightSearchResult(
        count=queryset.count(),
        limit=normalized_limit,
        offset=normalized_offset,
        filters=filters,
        results=[_serialize_flight_offer(item) for item in page],
    )


def _apply_flight_filters(queryset: QuerySet[FlightOffer], filters: dict[str, Any]) -> QuerySet[FlightOffer]:
    queryset = _filter_in(queryset, "listing_code", filters.get("listing_codes"))
    queryset = _filter_in(queryset, "origin_city", filters.get("origin_cities"))
    queryset = _filter_in(queryset, "destination_city", filters.get("destination_cities"))
    queryset = _filter_in(queryset, "origin_iata", filters.get("origin_iatas"))
    queryset = _filter_in(queryset, "destination_iata", filters.get("destination_iatas"))
    queryset = _filter_in(queryset, "airline_name", filters.get("airlines"))
    queryset = _filter_in(queryset, "cabin_class", filters.get("cabin_classes"))
    queryset = _filter_in(queryset, "stops", filters.get("stops"))
    queryset = _filter_date_in(queryset, "departure_date", filters.get("departure_dates"))
    queryset = _filter_date_range(queryset, "departure_date", filters.get("departure_date_from"), filters.get("departure_date_to"))
    queryset = _filter_numeric_range(queryset, "total_amount", filters.get("price_min"), filters.get("price_max"))

    if filters.get("refundable_only"):
        queryset = queryset.filter(refundable=True)

    search_text = filters.get("search_text")
    if search_text:
        for token in [part.strip() for part in str(search_text).split() if part.strip()]:
            queryset = queryset.filter(
                Q(origin_city__icontains=token)
                | Q(destination_city__icontains=token)
                | Q(origin_airport_name__icontains=token)
                | Q(destination_airport_name__icontains=token)
                | Q(airline_name__icontains=token)
                | Q(flight_number__icontains=token)
            )

    return queryset


def _filter_in(queryset: QuerySet[FlightOffer], field_name: str, values: Any) -> QuerySet[FlightOffer]:
    normalized_values = _normalize_list(values)
    if not normalized_values:
        return queryset
    return queryset.filter(**{f"{field_name}__in": normalized_values})


def _filter_date_in(queryset: QuerySet[FlightOffer], field_name: str, values: Any) -> QuerySet[FlightOffer]:
    normalized_values = [_parse_date(value) for value in _normalize_list(values)]
    normalized_values = [value for value in normalized_values if value]
    if not normalized_values:
        return queryset
    return queryset.filter(**{f"{field_name}__in": normalized_values})


def _filter_date_range(
    queryset: QuerySet[FlightOffer],
    field_name: str,
    start_value: Any,
    end_value: Any,
) -> QuerySet[FlightOffer]:
    start_date = _parse_date(start_value)
    end_date = _parse_date(end_value)
    if start_date:
        queryset = queryset.filter(**{f"{field_name}__gte": start_date})
    if end_date:
        queryset = queryset.filter(**{f"{field_name}__lte": end_date})
    return queryset


def _filter_numeric_range(
    queryset: QuerySet[FlightOffer],
    field_name: str,
    minimum: Any,
    maximum: Any,
) -> QuerySet[FlightOffer]:
    normalized_min = _parse_decimal(minimum)
    normalized_max = _parse_decimal(maximum)
    if normalized_min is not None:
        queryset = queryset.filter(**{f"{field_name}__gte": normalized_min})
    if normalized_max is not None:
        queryset = queryset.filter(**{f"{field_name}__lte": normalized_max})
    return queryset


def _serialize_flight_offer(item: FlightOffer) -> dict[str, Any]:
    title = f"{item.origin_city} to {item.destination_city}"
    return {
        "id": item.listing_code,
        "listing_code": item.listing_code,
        "title": title,
        "city": item.destination_city,
        "venue_name": item.airline_name,
        "event_date": item.departure_date.isoformat(),
        "start_at": item.departure_at.isoformat(),
        "provider": item.provider,
        "provider_offer_id": item.provider_offer_id,
        "origin_iata": item.origin_iata,
        "origin_airport_name": item.origin_airport_name,
        "origin_city": item.origin_city,
        "origin_state": item.origin_state,
        "destination_iata": item.destination_iata,
        "destination_airport_name": item.destination_airport_name,
        "destination_city": item.destination_city,
        "destination_state": item.destination_state,
        "departure_date": item.departure_date.isoformat(),
        "departure_at": item.departure_at.isoformat(),
        "arrival_at": item.arrival_at.isoformat(),
        "airline_code": item.airline_code,
        "airline_name": item.airline_name,
        "flight_number": item.flight_number,
        "cabin_class": item.cabin_class,
        "stops": item.stops,
        "refundable": item.refundable,
        "baggage_summary": item.baggage_summary,
        "fare_brand": item.fare_brand,
        "currency": item.currency,
        "total_amount": str(item.total_amount) if item.total_amount is not None else None,
        "offer_expires_at": item.offer_expires_at.isoformat() if item.offer_expires_at else None,
        "source_label": item.source_label,
    }


def _distinct_values(queryset: QuerySet[FlightOffer], field_name: str) -> list[str]:
    return sorted(
        value
        for value in queryset.order_by().values_list(field_name, flat=True).distinct()
        if value not in {None, ""}
    )


def _normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item not in {None, ""}]
    return [value] if value not in {None, ""} else []


def _parse_date(value: Any) -> date | None:
    if value in {None, ""}:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _parse_int(value: Any, *, field_name: str, minimum: int, maximum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"`{field_name}` must be an integer.") from exc
    if number < minimum:
        raise ValueError(f"`{field_name}` must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"`{field_name}` must be at most {maximum}.")
    return number
