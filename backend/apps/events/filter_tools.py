from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import JSON, cast, func, select
from sqlalchemy.orm import Session

from apps.core.ttl_cache import cache
from flask_app.db import get_session
from flask_app.orm.models import MovieEvent, SportEvent


def get_all_event_types() -> list[str]:
    def _load() -> list[str]:
        event_types: list[str] = []
        session = get_session()
        if session.execute(
            select(func.count()).select_from(select(MovieEvent.id).where(MovieEvent.is_published.is_(True)).subquery())
        ).scalar_one() > 0:
            event_types.append("movies")
        if session.execute(
            select(func.count()).select_from(select(SportEvent.id).where(SportEvent.is_published.is_(True)).subquery())
        ).scalar_one() > 0:
            event_types.append("sports")
        return event_types

    return cache.get_or_set("catalog:event_types", _load, ttl_seconds=86400)


def get_available_movie_locations() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_locations",
        lambda: _distinct_values(get_session(), MovieEvent, "city"),
        ttl_seconds=86400,
    )


def get_available_sport_locations() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_locations",
        lambda: _distinct_values(get_session(), SportEvent, "city"),
        ttl_seconds=86400,
    )


def get_available_movie_languages() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_languages",
        lambda: _distinct_json_values(get_session(), MovieEvent, "languages"),
        ttl_seconds=86400,
    )


def get_available_movie_genres() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_genres",
        lambda: _distinct_json_values(get_session(), MovieEvent, "genres"),
        ttl_seconds=86400,
    )


def get_available_movie_cast_members() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_cast_members",
        lambda: _distinct_json_values(get_session(), MovieEvent, "cast"),
        ttl_seconds=86400,
    )


def get_available_movie_directors() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_directors",
        lambda: _distinct_json_values(get_session(), MovieEvent, "directors"),
        ttl_seconds=86400,
    )


def get_available_movie_certifications() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_certifications",
        lambda: _distinct_values(get_session(), MovieEvent, "certification"),
        ttl_seconds=86400,
    )


def get_available_movie_titles() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_titles",
        lambda: _distinct_values(get_session(), MovieEvent, "title"),
        ttl_seconds=86400,
    )


def get_available_movie_venues() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_venues",
        lambda: _distinct_values(get_session(), MovieEvent, "venue_name"),
        ttl_seconds=86400,
    )


def get_available_movie_formats() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_formats",
        lambda: _distinct_json_values(get_session(), MovieEvent, "formats"),
        ttl_seconds=86400,
    )


def get_available_movie_franchises() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_franchises",
        lambda: _distinct_values(get_session(), MovieEvent, "franchise"),
        ttl_seconds=86400,
    )


def get_available_movie_content_origins() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_content_origins",
        lambda: _distinct_values(get_session(), MovieEvent, "content_origin"),
        ttl_seconds=86400,
    )


def get_available_sport_types() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_types",
        lambda: _distinct_values(get_session(), SportEvent, "sport_type"),
        ttl_seconds=86400,
    )


def get_available_sport_tournaments() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_tournaments",
        lambda: _distinct_values(get_session(), SportEvent, "tournament_name"),
        ttl_seconds=86400,
    )


def get_available_sport_season_labels() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_season_labels",
        lambda: _distinct_values(get_session(), SportEvent, "season_label"),
        ttl_seconds=86400,
    )


def get_available_sport_competition_stages() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_competition_stages",
        lambda: _distinct_values(get_session(), SportEvent, "competition_stage"),
        ttl_seconds=86400,
    )


def get_available_sport_format_labels() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_format_labels",
        lambda: _distinct_values(get_session(), SportEvent, "format_label"),
        ttl_seconds=86400,
    )


def get_available_sport_home_teams() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_home_teams",
        lambda: _distinct_values(get_session(), SportEvent, "home_team"),
        ttl_seconds=86400,
    )


def get_available_sport_away_teams() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_away_teams",
        lambda: _distinct_values(get_session(), SportEvent, "away_team"),
        ttl_seconds=86400,
    )


def get_available_sport_teams() -> list[str]:
    home_teams = get_available_sport_home_teams()
    away_teams = get_available_sport_away_teams()
    return sorted({*home_teams, *away_teams})


def get_available_sport_participant_names() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_participant_names",
        lambda: _distinct_json_values(get_session(), SportEvent, "participant_names"),
        ttl_seconds=86400,
    )


def get_available_sport_venues() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_venues",
        lambda: _distinct_values(get_session(), SportEvent, "venue_name"),
        ttl_seconds=86400,
    )


def get_available_sport_featured_athletes() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_featured_athletes",
        lambda: _distinct_json_values(get_session(), SportEvent, "featured_athletes"),
        ttl_seconds=86400,
    )


def get_available_sport_organizers() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_organizers",
        lambda: _distinct_values(get_session(), SportEvent, "organizer"),
        ttl_seconds=86400,
    )


def get_available_sport_match_numbers() -> list[int]:
    return cache.get_or_set(
        "catalog:sport_match_numbers",
        lambda: sorted(
            {
                value
                for value in get_session().execute(
                    select(SportEvent.match_number)
                    .where(SportEvent.is_published.is_(True))
                    .where(SportEvent.match_number.is_not(None))
                    .distinct()
                ).scalars().all()
                if value not in (None, "")
            }
        ),
        ttl_seconds=86400,
    )


def _distinct_values(session: Session, model, field_name: str) -> list[str]:
    column = getattr(model, field_name)
    values = session.execute(
        select(column)
        .where(model.is_published.is_(True))
        .where(column.is_not(None))
        .distinct()
        .order_by(column)
    ).scalars().all()
    return sorted([value for value in values if value not in {None, ""}])


def _distinct_json_values(session: Session, model, field_name: str) -> list[str]:
    column = getattr(model, field_name)
    values: set[str] = set()
    rows = session.execute(
        select(column).where(model.is_published.is_(True))
    ).scalars().all()
    for row in rows:
        if not row:
            continue
        for item in row:
            if item:
                values.add(str(item).strip())
    return sorted([value for value in values if value])


def _flatten_strings(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, Iterable):
        return {item for item in value if isinstance(item, str)}
    return set()
