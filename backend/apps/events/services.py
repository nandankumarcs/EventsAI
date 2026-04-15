from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Time, cast, func, or_, select
from sqlalchemy.orm import Session

from flask_app.db import get_session
from flask_app.orm.models import MovieEvent, SportEvent

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
    session = get_session()
    stmt = (
        select(MovieEvent)
        .where(MovieEvent.is_published.is_(True))
        .order_by(MovieEvent.event_date, MovieEvent.start_at, MovieEvent.title)
    )
    stmt = _apply_common_filters(stmt, filters, model="movie")
    stmt = _apply_movie_filters(stmt, filters)
    return _build_result(session, stmt, filters, limit, offset, _serialize_movie_event)


def search_sport_events(
    filters: dict[str, Any] | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> SearchResult:
    filters = filters or {}
    session = get_session()
    stmt = (
        select(SportEvent)
        .where(SportEvent.is_published.is_(True))
        .order_by(SportEvent.event_date, SportEvent.start_at, SportEvent.sport_type, SportEvent.tournament_name)
    )
    stmt = _apply_common_filters(stmt, filters, model="sport")
    stmt = _apply_sport_filters(stmt, filters)
    return _build_result(session, stmt, filters, limit, offset, _serialize_sport_event)


def diversify_sport_results(results: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or len(results) <= 1:
        return results[:limit]

    selected: list[dict[str, Any]] = []
    used_listing_codes: set[str] = set()
    seen_sport_types: set[str] = set()

    for item in results:
        sport_type = item.get("sport_type")
        if not sport_type or sport_type in seen_sport_types:
            continue
        selected.append(item)
        used_listing_codes.add(item["listing_code"])
        seen_sport_types.add(sport_type)
        if len(selected) == limit:
            return selected

    for item in results:
        if item["listing_code"] in used_listing_codes:
            continue
        selected.append(item)
        if len(selected) == limit:
            break

    return selected[:limit]


def _build_result(
    session: Session,
    stmt,
    filters: dict[str, Any],
    limit: int,
    offset: int,
    serializer,
) -> SearchResult:
    normalized_limit = max(1, min(limit, MAX_LIMIT))
    normalized_offset = max(0, offset)
    count = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    page = (
        session.execute(stmt.offset(normalized_offset).limit(normalized_limit)).scalars().all()
    )
    return SearchResult(
        count=int(count),
        limit=normalized_limit,
        offset=normalized_offset,
        filters=filters,
        results=[serializer(item) for item in page],
    )


def _apply_common_filters(stmt, filters: dict[str, Any], *, model: str):
    entity = MovieEvent if model == "movie" else SportEvent
    stmt = _filter_in(stmt, getattr(entity, "listing_code"), filters.get("listing_codes"))
    stmt = _filter_in(stmt, getattr(entity, "city"), filters.get("cities"))
    stmt = _filter_in(stmt, getattr(entity, "state"), filters.get("states"))
    stmt = _filter_in(stmt, getattr(entity, "venue_name"), filters.get("venue_names"))
    stmt = _filter_date_in(stmt, getattr(entity, "event_date"), filters.get("event_dates"))
    stmt = _filter_date_range(stmt, getattr(entity, "event_date"), filters.get("date_from"), filters.get("date_to"))
    stmt = _filter_clock_range(stmt, getattr(entity, "start_at"), filters.get("start_time_from"), filters.get("start_time_to"))
    stmt = _filter_numeric_range(stmt, getattr(entity, "max_price"), getattr(entity, "min_price"), filters.get("price_min"), filters.get("price_max"))
    stmt = _filter_json_any(stmt, getattr(entity, "languages"), filters.get("languages"))
    stmt = _filter_json_any(stmt, getattr(entity, "tags"), filters.get("tags"))
    stmt = _filter_search_text(stmt, entity, filters.get("search_text"))
    return stmt


def _apply_movie_filters(stmt, filters: dict[str, Any]):
    stmt = _filter_in(stmt, MovieEvent.title, filters.get("titles"))
    stmt = _filter_in(stmt, MovieEvent.certification, filters.get("certifications"))
    stmt = _filter_in(stmt, MovieEvent.franchise, filters.get("franchises"))
    stmt = _filter_in(stmt, MovieEvent.content_origin, filters.get("content_origins"))
    stmt = _filter_json_any(stmt, MovieEvent.genres, filters.get("genres"))
    stmt = _filter_json_any(stmt, MovieEvent.cast, filters.get("cast_members"))
    stmt = _filter_json_any(stmt, MovieEvent.directors, filters.get("directors"))
    stmt = _filter_json_any(stmt, MovieEvent.formats, filters.get("formats"))
    stmt = _filter_numeric_range(stmt, MovieEvent.runtime_minutes, MovieEvent.runtime_minutes, filters.get("runtime_min"), filters.get("runtime_max"))
    stmt = _filter_date_range(stmt, MovieEvent.release_date, filters.get("release_date_from"), filters.get("release_date_to"))
    return stmt


def _apply_sport_filters(stmt, filters: dict[str, Any]):
    stmt = _filter_in(stmt, SportEvent.sport_type, filters.get("sport_types"))
    stmt = _filter_in(stmt, SportEvent.tournament_name, filters.get("tournament_names"))
    stmt = _filter_in(stmt, SportEvent.season_label, filters.get("season_labels"))
    stmt = _filter_in(stmt, SportEvent.competition_stage, filters.get("competition_stages"))
    stmt = _filter_in(stmt, SportEvent.format_label, filters.get("format_labels"))
    stmt = _filter_in(stmt, SportEvent.home_team, filters.get("home_teams"))
    stmt = _filter_in(stmt, SportEvent.away_team, filters.get("away_teams"))
    stmt = _filter_team_any(stmt, filters.get("teams"))
    stmt = _filter_json_any(stmt, SportEvent.participant_names, filters.get("participant_names"))
    stmt = _filter_json_any(stmt, SportEvent.featured_athletes, filters.get("featured_athletes"))
    stmt = _filter_in(stmt, SportEvent.organizer, filters.get("organizers"))
    stmt = _filter_in(stmt, SportEvent.match_number, filters.get("match_numbers"))
    return stmt


def _filter_in(stmt, column, values: Any):
    normalized_values = _normalize_list(values)
    if not normalized_values:
        return stmt
    return stmt.where(column.in_(normalized_values))


def _filter_json_any(stmt, column, values: Any):
    normalized_values = _normalize_list(values)
    if not normalized_values:
        return stmt

    # For PostgreSQL JSON containment, use @> operator
    # Both sides need to be JSONB type
    clauses = []
    for value in normalized_values:
        # Create a JSONB array with the single value
        json_array = func.jsonb_build_array(value)
        clauses.append(column.op('@>')(json_array))
    return stmt.where(or_(*clauses))


def _filter_team_any(stmt, values: Any):
    normalized_values = _normalize_list(values)
    if not normalized_values:
        return stmt
    return stmt.where(or_(SportEvent.home_team.in_(normalized_values), SportEvent.away_team.in_(normalized_values)))


def _filter_search_text(stmt, entity, search_text: Any):
    if not search_text:
        return stmt

    tokens = [token.strip() for token in str(search_text).split() if token.strip()]
    for token in tokens:
        pattern = f"%{token}%"
        stmt = stmt.where(
            or_(
                entity.title.ilike(pattern),
                entity.city.ilike(pattern),
                entity.venue_name.ilike(pattern),
                entity.venue_area.ilike(pattern),
            )
        )
    return stmt


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


def _filter_clock_range(stmt, datetime_column, start_value: Any, end_value: Any):
    start_time = _parse_time(start_value)
    end_time = _parse_time(end_value)

    time_expr = cast(datetime_column, Time)
    if start_time:
        stmt = stmt.where(time_expr >= start_time)
    if end_time:
        stmt = stmt.where(time_expr <= end_time)
    return stmt


def _filter_numeric_range(stmt, min_column, max_column, minimum: Any, maximum: Any):
    min_value = _parse_number(minimum)
    max_value = _parse_number(maximum)
    if min_value is not None:
        stmt = stmt.where(min_column >= min_value)
    if max_value is not None:
        stmt = stmt.where(max_column <= max_value)
    return stmt


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
