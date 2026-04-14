from django.urls import path

from apps.flights.views import (
    flight_airlines_view,
    flight_cabin_classes_view,
    flight_destinations_view,
    flight_origins_view,
    flight_search_view,
)

app_name = "flights"

urlpatterns = [
    path("search/", flight_search_view, name="search"),
    path("tools/origins/", flight_origins_view, name="origins"),
    path("tools/destinations/", flight_destinations_view, name="destinations"),
    path("tools/airlines/", flight_airlines_view, name="airlines"),
    path("tools/cabin-classes/", flight_cabin_classes_view, name="cabin-classes"),
]

