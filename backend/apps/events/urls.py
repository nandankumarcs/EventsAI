from django.urls import path

from apps.events.views import (
    event_types_view,
    movie_genres_view,
    movie_languages_view,
    movie_locations_view,
    movie_search_view,
    movie_titles_view,
    movie_venues_view,
    sport_featured_athletes_view,
    sport_locations_view,
    sport_search_view,
    sport_teams_view,
    sport_tournaments_view,
    sport_types_view,
    sport_venues_view,
    temporal_normalization_view,
)

app_name = "events"

urlpatterns = [
    path("movies/search/", movie_search_view, name="movie-search"),
    path("sports/search/", sport_search_view, name="sport-search"),
    path("tools/event-types/", event_types_view, name="event-types"),
    path("tools/movies/locations/", movie_locations_view, name="movie-locations"),
    path("tools/movies/languages/", movie_languages_view, name="movie-languages"),
    path("tools/movies/genres/", movie_genres_view, name="movie-genres"),
    path("tools/movies/titles/", movie_titles_view, name="movie-titles"),
    path("tools/movies/venues/", movie_venues_view, name="movie-venues"),
    path("tools/sports/locations/", sport_locations_view, name="sport-locations"),
    path("tools/sports/types/", sport_types_view, name="sport-types"),
    path("tools/sports/tournaments/", sport_tournaments_view, name="sport-tournaments"),
    path("tools/sports/teams/", sport_teams_view, name="sport-teams"),
    path("tools/sports/venues/", sport_venues_view, name="sport-venues"),
    path("tools/sports/featured-athletes/", sport_featured_athletes_view, name="sport-featured-athletes"),
    path("tools/temporal/normalize/", temporal_normalization_view, name="temporal-normalize"),
]
