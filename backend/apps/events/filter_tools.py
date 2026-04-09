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


def get_available_movie_cast_members() -> list[str]:
    return _distinct_json_values(MovieEvent.objects.filter(is_published=True), "cast")


def get_available_movie_directors() -> list[str]:
    return _distinct_json_values(MovieEvent.objects.filter(is_published=True), "directors")


def get_available_movie_certifications() -> list[str]:
    return _distinct_values(MovieEvent.objects.filter(is_published=True), "certification")


def get_available_movie_titles() -> list[str]:
    return _distinct_values(MovieEvent.objects.filter(is_published=True), "title")


def get_available_movie_venues() -> list[str]:
    return _distinct_values(MovieEvent.objects.filter(is_published=True), "venue_name")


def get_available_movie_formats() -> list[str]:
    return _distinct_json_values(MovieEvent.objects.filter(is_published=True), "formats")


def get_available_movie_franchises() -> list[str]:
    return _distinct_values(MovieEvent.objects.filter(is_published=True), "franchise")


def get_available_movie_content_origins() -> list[str]:
    return _distinct_values(MovieEvent.objects.filter(is_published=True), "content_origin")


def get_available_sport_types() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "sport_type")


def get_available_sport_tournaments() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "tournament_name")


def get_available_sport_season_labels() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "season_label")


def get_available_sport_competition_stages() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "competition_stage")


def get_available_sport_format_labels() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "format_label")


def get_available_sport_home_teams() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "home_team")


def get_available_sport_away_teams() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "away_team")


def get_available_sport_teams() -> list[str]:
    home_teams = get_available_sport_home_teams()
    away_teams = get_available_sport_away_teams()
    return sorted({*home_teams, *away_teams})


def get_available_sport_participant_names() -> list[str]:
    return _distinct_json_values(SportEvent.objects.filter(is_published=True), "participant_names")


def get_available_sport_venues() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "venue_name")


def get_available_sport_featured_athletes() -> list[str]:
    return _distinct_json_values(SportEvent.objects.filter(is_published=True), "featured_athletes")


def get_available_sport_organizers() -> list[str]:
    return _distinct_values(SportEvent.objects.filter(is_published=True), "organizer")


def get_available_sport_match_numbers() -> list[int]:
    values = SportEvent.objects.filter(is_published=True).order_by().values_list("match_number", flat=True).distinct()
    return sorted({value for value in values if value is not None})


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
