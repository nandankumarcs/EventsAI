from __future__ import annotations

from collections.abc import Iterable

from django.db.models import QuerySet

from apps.events.models import MovieEvent, SportEvent


def get_all_event_types() -> list[str]:
    event_types: list[str] = []
    if MovieEvent.objects.filter(is_published=True).exists():
        event_types.append("movies")
    if SportEvent.objects.filter(is_published=True).exists():
        event_types.append("sports")
    return event_types


def get_available_movie_locations() -> list[str]:
    return _distinct_values(MovieEvent.objects.filter(is_published=True), "city")


def get_available_sport_locations() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "city")


def get_available_movie_languages() -> list[str]:
    return _distinct_json_values(MovieEvent.objects.filter(is_published=True), "languages")


def get_available_movie_genres() -> list[str]:
    return _distinct_json_values(MovieEvent.objects.filter(is_published=True), "genres")


def get_available_movie_titles() -> list[str]:
    return _distinct_values(MovieEvent.objects.filter(is_published=True), "title")


def get_available_movie_venues() -> list[str]:
    return _distinct_values(MovieEvent.objects.filter(is_published=True), "venue_name")


def get_available_movie_formats() -> list[str]:
    return _distinct_json_values(MovieEvent.objects.filter(is_published=True), "formats")


def get_available_sport_types() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "sport_type")


def get_available_sport_tournaments() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "tournament_name")


def get_available_sport_teams() -> list[str]:
    home_teams = _distinct_values(SportEvent.objects.filter(is_published=True), "home_team")
    away_teams = _distinct_values(SportEvent.objects.filter(is_published=True), "away_team")
    return sorted({*home_teams, *away_teams})


def get_available_sport_venues() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "venue_name")


def get_available_sport_featured_athletes() -> list[str]:
    return _distinct_json_values(SportEvent.objects.filter(is_published=True), "featured_athletes")


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
