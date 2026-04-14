from django.contrib import admin

from apps.flights.models import FlightOffer


@admin.register(FlightOffer)
class FlightOfferAdmin(admin.ModelAdmin):
    list_display = (
        "listing_code",
        "origin_city",
        "destination_city",
        "departure_date",
        "airline_name",
        "flight_number",
        "provider",
        "is_published",
    )
    search_fields = (
        "listing_code",
        "origin_city",
        "destination_city",
        "airline_name",
        "flight_number",
    )
    list_filter = ("provider", "airline_name", "departure_date", "is_published")

