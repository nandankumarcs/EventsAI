from __future__ import annotations

from collections.abc import Iterable

from django.db.models import QuerySet

from apps.core.ttl_cache import cache
from apps.events.models import MovieEvent, SportEvent


def get_all_event_types() -> list[str]:
    def _load() -> list[str]:
        event_types: list[str] = []
        if MovieEvent.objects.filter(is_published=True).exists():
            event_types.append("movies")
        if SportEvent.objects.filter(is_published=True).exists():
            event_types.append("sports")
        return event_types

    return cache.get_or_set("catalog:event_types", _load, ttl_seconds=86400)


def get_available_movie_locations() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_locations",
        lambda: _distinct_values(MovieEvent.objects.filter(is_published=True), "city"),
        ttl_seconds=86400,
    )


def get_available_sport_locations() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_locations",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "city"),
        ttl_seconds=86400,
    )


def get_available_movie_languages() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_languages",
        lambda: _distinct_json_values(MovieEvent.objects.filter(is_published=True), "languages"),
        ttl_seconds=86400,
    )


def get_available_movie_genres() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_genres",
        lambda: _distinct_json_values(MovieEvent.objects.filter(is_published=True), "genres"),
        ttl_seconds=86400,
    )


def get_available_movie_cast_members() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_cast_members",
        lambda: _distinct_json_values(MovieEvent.objects.filter(is_published=True), "cast"),
        ttl_seconds=86400,
    )


def get_available_movie_directors() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_directors",
        lambda: _distinct_json_values(MovieEvent.objects.filter(is_published=True), "directors"),
        ttl_seconds=86400,
    )


def get_available_movie_certifications() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_certifications",
        lambda: _distinct_values(MovieEvent.objects.filter(is_published=True), "certification"),
        ttl_seconds=86400,
    )


def get_available_movie_titles() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_titles",
        lambda: _distinct_values(MovieEvent.objects.filter(is_published=True), "title"),
        ttl_seconds=86400,
    )


def get_available_movie_venues() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_venues",
        lambda: _distinct_values(MovieEvent.objects.filter(is_published=True), "venue_name"),
        ttl_seconds=86400,
    )


def get_available_movie_formats() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_formats",
        lambda: _distinct_json_values(MovieEvent.objects.filter(is_published=True), "formats"),
        ttl_seconds=86400,
    )


def get_available_movie_franchises() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_franchises",
        lambda: _distinct_values(MovieEvent.objects.filter(is_published=True), "franchise"),
        ttl_seconds=86400,
    )


def get_available_movie_content_origins() -> list[str]:
    return cache.get_or_set(
        "catalog:movie_content_origins",
        lambda: _distinct_values(MovieEvent.objects.filter(is_published=True), "content_origin"),
        ttl_seconds=86400,
    )


def get_available_sport_types() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_types",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "sport_type"),
        ttl_seconds=86400,
    )


def get_available_sport_tournaments() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_tournaments",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "tournament_name"),
        ttl_seconds=86400,
    )


def get_available_sport_season_labels() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_season_labels",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "season_label"),
        ttl_seconds=86400,
    )


def get_available_sport_competition_stages() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_competition_stages",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "competition_stage"),
        ttl_seconds=86400,
    )


def get_available_sport_format_labels() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_format_labels",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "format_label"),
        ttl_seconds=86400,
    )


def get_available_sport_home_teams() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_home_teams",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "home_team"),
        ttl_seconds=86400,
    )


def get_available_sport_away_teams() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_away_teams",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "away_team"),
        ttl_seconds=86400,
    )


def get_available_sport_teams() -> list[str]:
    home_teams = get_available_sport_home_teams()
    away_teams = get_available_sport_away_teams()
    return sorted({*home_teams, *away_teams})


def get_available_sport_participant_names() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_participant_names",
        lambda: _distinct_json_values(SportEvent.objects.filter(is_published=True), "participant_names"),
        ttl_seconds=86400,
    )


def get_available_sport_venues() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_venues",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "venue_name"),
        ttl_seconds=86400,
    )


def get_available_sport_featured_athletes() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_featured_athletes",
        lambda: _distinct_json_values(SportEvent.objects.filter(is_published=True), "featured_athletes"),
        ttl_seconds=86400,
    )


def get_available_sport_organizers() -> list[str]:
    return cache.get_or_set(
        "catalog:sport_organizers",
        lambda: _distinct_values(SportEvent.objects.filter(is_published=True), "organizer"),
        ttl_seconds=86400,
    )


def get_available_sport_match_numbers() -> list[int]:
    return cache.get_or_set(
        "catalog:sport_match_numbers",
        lambda: sorted(
            {
                value
                for value in SportEvent.objects.filter(is_published=True)
                .order_by()
                .values_list("match_number", flat=True)
                .distinct()
                if value is not None
            }
        ),
        ttl_seconds=86400,
    )


def _distinct_values(queryset: QuerySet, field_name: str) -> list[str]:
    values = queryset.order_by().values_list(field_name, flat=True).distinct()
    return sorted({value for value in values if value})


def _distinct_json_values(queryset: QuerySet, field_name: str) -> list[str]:
    values: set[str] = set()
    for row in queryset.values_list(field_name, flat=True):
        values.update(_flatten_strings(row))
    return sorted(values)


def _flatten_strings(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, Iterable):
        return {item for item in value if isinstance(item, str)}
    return set()
