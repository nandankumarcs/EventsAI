from django.urls import path

from apps.events.views import movie_search_view, sport_search_view

app_name = "events"

urlpatterns = [
    path("movies/search/", movie_search_view, name="movie-search"),
    path("sports/search/", sport_search_view, name="sport-search"),
]
