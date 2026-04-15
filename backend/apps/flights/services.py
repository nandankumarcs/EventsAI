from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from flask_app.db import get_session
from flask_app.orm.models import FlightOffer

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
    session = get_session()
    stmt = (
        select(FlightOffer)
        .where(FlightOffer.is_published.is_(True))
        .order_by(
            FlightOffer.departure_date,
            FlightOffer.departure_at,
            FlightOffer.origin_city,
            FlightOffer.destination_city,
        )
    )
    stmt = _apply_flight_filters(stmt, filters)
    return _build_result(session, stmt, filters, limit, offset)


def get_available_origin_cities() -> list[str]:
    session = get_session()
    return _distinct_values(session, "origin_city")


def get_available_destination_cities() -> list[str]:
    session = get_session()
    return _distinct_values(session, "destination_city")


def get_available_airlines() -> list[str]:
    session = get_session()
    return _distinct_values(session, "airline_name")


def get_available_cabin_classes() -> list[str]:
    session = get_session()
    return _distinct_values(session, "cabin_class")


def _build_result(
    session: Session,
    stmt,
    filters: dict[str, Any],
    limit: int,
    offset: int,
) -> FlightSearchResult:
    normalized_limit = max(1, min(limit, MAX_LIMIT))
    normalized_offset = max(0, offset)
    count = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    page = (
        session.execute(stmt.offset(normalized_offset).limit(normalized_limit))
        .scalars()
        .all()
    )
    return FlightSearchResult(
        count=int(count),
        limit=normalized_limit,
        offset=normalized_offset,
        filters=filters,
        results=[_serialize_flight_offer(item) for item in page],
    )


def _apply_flight_filters(stmt, filters: dict[str, Any]):
    stmt = _filter_in(stmt, FlightOffer.listing_code, filters.get("listing_codes"))
    stmt = _filter_in(stmt, FlightOffer.origin_city, filters.get("origin_cities"))
    stmt = _filter_in(stmt, FlightOffer.destination_city, filters.get("destination_cities"))
    stmt = _filter_in(stmt, FlightOffer.origin_iata, filters.get("origin_iatas"))
    stmt = _filter_in(stmt, FlightOffer.destination_iata, filters.get("destination_iatas"))
    stmt = _filter_in(stmt, FlightOffer.airline_name, filters.get("airlines"))
    stmt = _filter_in(stmt, FlightOffer.cabin_class, filters.get("cabin_classes"))
    stmt = _filter_in(stmt, FlightOffer.stops, filters.get("stops"))
    stmt = _filter_date_in(stmt, FlightOffer.departure_date, filters.get("departure_dates"))
    stmt = _filter_date_range(stmt, FlightOffer.departure_date, filters.get("departure_date_from"), filters.get("departure_date_to"))
    stmt = _filter_numeric_range(stmt, FlightOffer.total_amount, filters.get("price_min"), filters.get("price_max"))

    if filters.get("refundable_only"):
        stmt = stmt.where(FlightOffer.refundable.is_(True))

    search_text = filters.get("search_text")
    if search_text:
        tokens = [part.strip() for part in str(search_text).split() if part.strip()]
        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                or_(
                    FlightOffer.origin_city.ilike(pattern),
                    FlightOffer.destination_city.ilike(pattern),
                    FlightOffer.origin_airport_name.ilike(pattern),
                    FlightOffer.destination_airport_name.ilike(pattern),
                    FlightOffer.airline_name.ilike(pattern),
                    FlightOffer.flight_number.ilike(pattern),
                )
            )

    return stmt


def _filter_in(stmt, column, values: Any):
    normalized_values = _normalize_list(values)
    if not normalized_values:
        return stmt
    return stmt.where(column.in_(normalized_values))


def _filter_date_in(stmt, column, values: Any):
    normalized_values = [_parse_date(value) for value in _normalize_list(values)]
    normalized_values = [value for value in normalized_values if value]
    if not normalized_values:
        return stmt
    return stmt.where(column.in_(normalized_values))


def _filter_date_range(
    stmt,
    column,
    start_value: Any,
    end_value: Any,
):
    start_date = _parse_date(start_value)
    end_date = _parse_date(end_value)
    if start_date:
        stmt = stmt.where(column >= start_date)
    if end_date:
        stmt = stmt.where(column <= end_date)
    return stmt


def _filter_numeric_range(
    stmt,
    column,
    minimum: Any,
    maximum: Any,
):
    normalized_min = _parse_decimal(minimum)
    normalized_max = _parse_decimal(maximum)
    if normalized_min is not None:
        stmt = stmt.where(column >= normalized_min)
    if normalized_max is not None:
        stmt = stmt.where(column <= normalized_max)
    return stmt


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


def _distinct_values(session: Session, field_name: str) -> list[str]:
    column = getattr(FlightOffer, field_name)
    stmt = (
        select(column)
        .where(FlightOffer.is_published.is_(True))
        .where(column.is_not(None))
        .distinct()
        .order_by(column)
    )
    values = session.execute(stmt).scalars().all()
    return sorted([value for value in values if value not in {None, ""}])


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
