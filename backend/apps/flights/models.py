from django.db import models

from apps.chats.models import ChatThread


class FlightOffer(models.Model):
    listing_code = models.CharField(max_length=64, unique=True)
    provider = models.CharField(max_length=64, db_index=True)
    provider_offer_id = models.CharField(max_length=128, blank=True)
    source_label = models.CharField(max_length=64, blank=True)
    origin_iata = models.CharField(max_length=8, db_index=True)
    origin_airport_name = models.CharField(max_length=255, blank=True)
    origin_city = models.CharField(max_length=120, db_index=True)
    origin_state = models.CharField(max_length=120, blank=True)
    destination_iata = models.CharField(max_length=8, db_index=True)
    destination_airport_name = models.CharField(max_length=255, blank=True)
    destination_city = models.CharField(max_length=120, db_index=True)
    destination_state = models.CharField(max_length=120, blank=True)
    departure_date = models.DateField(db_index=True)
    departure_at = models.DateTimeField(db_index=True)
    arrival_at = models.DateTimeField(db_index=True)
    airline_code = models.CharField(max_length=16, blank=True)
    airline_name = models.CharField(max_length=255, db_index=True)
    flight_number = models.CharField(max_length=32, db_index=True)
    cabin_class = models.CharField(max_length=64, blank=True)
    stops = models.PositiveSmallIntegerField(default=0)
    refundable = models.BooleanField(default=False)
    baggage_summary = models.CharField(max_length=255, blank=True)
    fare_brand = models.CharField(max_length=120, blank=True)
    currency = models.CharField(max_length=8, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "flight_offers"
        ordering = ["departure_date", "departure_at", "origin_city", "destination_city"]
        indexes = [
            models.Index(fields=["origin_city", "destination_city", "departure_date"], name="flight_route_date_idx"),
            models.Index(fields=["origin_iata", "destination_iata", "departure_date"], name="flight_iata_date_idx"),
            models.Index(fields=["airline_name"], name="flight_airline_idx"),
            models.Index(fields=["departure_at"], name="flight_departure_at_idx"),
            models.Index(fields=["is_published"], name="flight_published_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_offer_id"],
                name="flight_provider_offer_unique",
                condition=~models.Q(provider_offer_id=""),
            )
        ]

    def __str__(self) -> str:
        return f"{self.origin_city} -> {self.destination_city} ({self.flight_number})"


class FlightBooking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        SIMULATED = "simulated", "Simulated"

    thread = models.ForeignKey(
        ChatThread,
        on_delete=models.SET_NULL,
        related_name="flight_bookings",
        null=True,
        blank=True,
    )
    booking_reference = models.CharField(max_length=32, unique=True)
    status = models.CharField(max_length=24, choices=Status, default=Status.SIMULATED)
    listing_code = models.CharField(max_length=64, db_index=True)
    offer = models.ForeignKey(
        FlightOffer,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )
    route = models.CharField(max_length=255)
    origin_city = models.CharField(max_length=120)
    origin_iata = models.CharField(max_length=8)
    destination_city = models.CharField(max_length=120)
    destination_iata = models.CharField(max_length=8)
    departure_at = models.DateTimeField()
    arrival_at = models.DateTimeField()
    departure_date = models.DateField()
    airline_name = models.CharField(max_length=255)
    flight_number = models.CharField(max_length=32)
    cabin_class = models.CharField(max_length=64, blank=True)
    stops = models.PositiveSmallIntegerField(default=0)
    currency = models.CharField(max_length=8, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    passenger_name = models.CharField(max_length=255, blank=True)
    passenger_email = models.EmailField(blank=True)
    passenger_contact_number = models.CharField(max_length=32, blank=True)
    confirmed_at = models.DateTimeField(auto_now_add=True)
    filter_snapshot = models.JSONField(default=dict, blank=True)
    offer_snapshot = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "flight_bookings"
        ordering = ["-confirmed_at"]
        indexes = [
            models.Index(fields=["thread"], name="flight_booking_thread_idx"),
            models.Index(fields=["listing_code", "-confirmed_at"], name="flight_booking_listing_idx"),
        ]

    def __str__(self) -> str:
        return self.booking_reference
