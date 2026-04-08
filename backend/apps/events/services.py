from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.db.models import Q, QuerySet

from apps.events.models import MovieEvent, SportEvent

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass
class SearchResult:
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


def search_movie_events(
    filters: dict[str, Any] | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> SearchResult:
    filters = filters or {}
    queryset = MovieEvent.objects.filter(is_published=True).order_by("event_date", "start_at", "title")
    queryset = _apply_common_filters(queryset, filters)
    queryset = _apply_movie_filters(queryset, filters)
    return _build_result(queryset, filters, limit, offset, _serialize_movie_event)


def search_sport_events(
    filters: dict[str, Any] | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> SearchResult:
    filters = filters or {}
    queryset = SportEvent.objects.filter(is_published=True).order_by(
        "event_date",
        "start_at",
        "sport_type",
        "tournament_name",
    )
    queryset = _apply_common_filters(queryset, filters)
    queryset = _apply_sport_filters(queryset, filters)
    return _build_result(queryset, filters, limit, offset, _serialize_sport_event)


def _build_result(
    queryset: QuerySet,
    filters: dict[str, Any],
    limit: int,
    offset: int,
    serializer,
) -> SearchResult:
    normalized_limit = max(1, min(limit, MAX_LIMIT))
    normalized_offset = max(0, offset)
    page = list(queryset[normalized_offset : normalized_offset + normalized_limit])
    return SearchResult(
        count=queryset.count(),
        limit=normalized_limit,
        offset=normalized_offset,
        filters=filters,
        results=[serializer(item) for item in page],
    )


def _apply_common_filters(queryset: QuerySet, filters: dict[str, Any]) -> QuerySet:
    queryset = _filter_in(queryset, "listing_code", filters.get("listing_codes"))
    queryset = _filter_in(queryset, "city", filters.get("cities"))
    queryset = _filter_in(queryset, "state", filters.get("states"))
    queryset = _filter_in(queryset, "venue_name", filters.get("venue_names"))
    queryset = _filter_date_in(queryset, "event_date", filters.get("event_dates"))
    queryset = _filter_date_range(
        queryset,
        "event_date",
        filters.get("date_from"),
        filters.get("date_to"),
    )
    queryset = _filter_clock_range(
        queryset,
        "start_at",
        filters.get("start_time_from"),
        filters.get("start_time_to"),
    )
    queryset = _filter_numeric_range(
        queryset,
        min_field="max_price",
        max_field="min_price",
        minimum=filters.get("price_min"),
        maximum=filters.get("price_max"),
    )
    queryset = _filter_json_any(queryset, "languages", filters.get("languages"))
    queryset = _filter_json_any(queryset, "tags", filters.get("tags"))
    queryset = _filter_search_text(queryset, filters.get("search_text"))
    return queryset


def _apply_movie_filters(queryset: QuerySet, filters: dict[str, Any]) -> QuerySet:
    queryset = _filter_in(queryset, "title", filters.get("titles"))
    queryset = _filter_in(queryset, "certification", filters.get("certifications"))
    queryset = _filter_in(queryset, "franchise", filters.get("franchises"))
    queryset = _filter_in(queryset, "content_origin", filters.get("content_origins"))
    queryset = _filter_json_any(queryset, "genres", filters.get("genres"))
    queryset = _filter_json_any(queryset, "cast", filters.get("cast_members"))
    queryset = _filter_json_any(queryset, "directors", filters.get("directors"))
    queryset = _filter_json_any(queryset, "formats", filters.get("formats"))
    queryset = _filter_numeric_range(
        queryset,
        min_field="runtime_minutes",
        max_field="runtime_minutes",
        minimum=filters.get("runtime_min"),
        maximum=filters.get("runtime_max"),
    )
    queryset = _filter_date_range(
        queryset,
        "release_date",
        filters.get("release_date_from"),
        filters.get("release_date_to"),
    )
    return queryset


def _apply_sport_filters(queryset: QuerySet, filters: dict[str, Any]) -> QuerySet:
    queryset = _filter_in(queryset, "sport_type", filters.get("sport_types"))
    queryset = _filter_in(queryset, "tournament_name", filters.get("tournament_names"))
    queryset = _filter_in(queryset, "season_label", filters.get("season_labels"))
    queryset = _filter_in(queryset, "competition_stage", filters.get("competition_stages"))
    queryset = _filter_in(queryset, "format_label", filters.get("format_labels"))
    queryset = _filter_in(queryset, "home_team", filters.get("home_teams"))
    queryset = _filter_in(queryset, "away_team", filters.get("away_teams"))
    queryset = _filter_team_any(queryset, filters.get("teams"))
    queryset = _filter_json_any(queryset, "participant_names", filters.get("participant_names"))
    queryset = _filter_json_any(queryset, "featured_athletes", filters.get("featured_athletes"))
    queryset = _filter_in(queryset, "organizer", filters.get("organizers"))
    queryset = _filter_in(queryset, "match_number", filters.get("match_numbers"))
    return queryset


def _filter_in(queryset: QuerySet, field_name: str, values: Any) -> QuerySet:
    normalized_values = _normalize_list(values)
    if not normalized_values:
        return queryset
    return queryset.filter(**{f"{field_name}__in": normalized_values})


def _filter_json_any(queryset: QuerySet, field_name: str, values: Any) -> QuerySet:
    normalized_values = _normalize_list(values)
    if not normalized_values:
        return queryset

    query = Q()
    for value in normalized_values:
        query |= Q(**{f"{field_name}__contains": [value]})
    return queryset.filter(query)


def _filter_team_any(queryset: QuerySet, values: Any) -> QuerySet:
    normalized_values = _normalize_list(values)
    if not normalized_values:
        return queryset
    return queryset.filter(Q(home_team__in=normalized_values) | Q(away_team__in=normalized_values))


def _filter_search_text(queryset: QuerySet, search_text: Any) -> QuerySet:
    if not search_text:
        return queryset

    tokens = [token.strip() for token in str(search_text).split() if token.strip()]
    for token in tokens:
        queryset = queryset.filter(
            Q(title__icontains=token)
            | Q(city__icontains=token)
            | Q(venue_name__icontains=token)
            | Q(venue_area__icontains=token)
        )
    return queryset


def _filter_date_in(queryset: QuerySet, field_name: str, values: Any) -> QuerySet:
    normalized_values = [_parse_date(value) for value in _normalize_list(values)]
    normalized_values = [value for value in normalized_values if value]
    if not normalized_values:
        return queryset
    return queryset.filter(**{f"{field_name}__in": normalized_values})


def _filter_date_range(
    queryset: QuerySet,
    field_name: str,
    start_value: Any,
    end_value: Any,
) -> QuerySet:
    start_date = _parse_date(start_value)
    end_date = _parse_date(end_value)

    if start_date:
        queryset = queryset.filter(**{f"{field_name}__gte": start_date})
    if end_date:
        queryset = queryset.filter(**{f"{field_name}__lte": end_date})
    return queryset


def _filter_clock_range(
    queryset: QuerySet,
    field_name: str,
    start_value: Any,
    end_value: Any,
) -> QuerySet:
    start_time = _parse_time(start_value)
    end_time = _parse_time(end_value)

    if start_time:
        queryset = queryset.filter(**{f"{field_name}__time__gte": start_time})
    if end_time:
        queryset = queryset.filter(**{f"{field_name}__time__lte": end_time})
    return queryset


def _filter_numeric_range(
    queryset: QuerySet,
    *,
    min_field: str,
    max_field: str,
    minimum: Any,
    maximum: Any,
) -> QuerySet:
    min_value = _parse_number(minimum)
    max_value = _parse_number(maximum)

    if min_value is not None:
        queryset = queryset.filter(**{f"{min_field}__gte": min_value})
    if max_value is not None:
        queryset = queryset.filter(**{f"{max_field}__lte": max_value})
    return queryset


def _normalize_list(values: Any) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, list):
        return [value for value in values if value not in ("", None)]
    return [values]


def _parse_date(value: Any) -> date | None:
    if value in ("", None):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


def _parse_time(value: Any) -> time | None:
    if value in ("", None):
        return None
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def _parse_number(value: Any) -> Decimal | int | None:
    if value in ("", None):
        return None
    if isinstance(value, (int, Decimal)):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    raw_value = str(value)
    return Decimal(raw_value) if "." in raw_value else int(raw_value)


def parse_request_filters(payload: bytes) -> tuple[dict[str, Any], int, int]:
    if not payload:
        return {}, DEFAULT_LIMIT, 0

    data = json.loads(payload.decode("utf-8"))
    filters = data.get("filters", {}) or {}
    limit = int(data.get("limit", DEFAULT_LIMIT))
    offset = int(data.get("offset", 0))
    return filters, limit, offset


def _serialize_movie_event(event: MovieEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "listing_code": event.listing_code,
        "title": event.title,
        "event_date": event.event_date.isoformat(),
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat() if event.end_at else None,
        "city": event.city,
        "state": event.state,
        "venue_name": event.venue_name,
        "venue_area": event.venue_area,
        "languages": event.languages,
        "min_price": event.min_price,
        "max_price": event.max_price,
        "tags": event.tags,
        "release_date": event.release_date.isoformat() if event.release_date else None,
        "runtime_minutes": event.runtime_minutes,
        "certification": event.certification,
        "genres": event.genres,
        "cast": event.cast,
        "directors": event.directors,
        "formats": event.formats,
        "franchise": event.franchise,
        "viewer_rating": str(event.viewer_rating) if event.viewer_rating is not None else None,
        "source_label": event.source_label,
        "content_origin": event.content_origin,
    }


def _serialize_sport_event(event: SportEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "listing_code": event.listing_code,
        "title": event.title,
        "event_date": event.event_date.isoformat(),
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat() if event.end_at else None,
        "city": event.city,
        "state": event.state,
        "venue_name": event.venue_name,
        "venue_area": event.venue_area,
        "languages": event.languages,
        "min_price": event.min_price,
        "max_price": event.max_price,
        "tags": event.tags,
        "sport_type": event.sport_type,
        "tournament_name": event.tournament_name,
        "season_label": event.season_label,
        "competition_stage": event.competition_stage,
        "format_label": event.format_label,
        "home_team": event.home_team,
        "away_team": event.away_team,
        "participant_names": event.participant_names,
        "featured_athletes": event.featured_athletes,
        "organizer": event.organizer,
        "gate_open_at": event.gate_open_at.isoformat() if event.gate_open_at else None,
        "match_number": event.match_number,
        "source_label": event.source_label,
    }
