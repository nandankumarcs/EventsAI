from django.db import models
from django.utils import timezone

from apps.chats.models import ChatThread
from apps.core.models import UUIDTimeStampedModel
from apps.events.models import MovieEvent, SportEvent


class Booking(UUIDTimeStampedModel):
    class EventType(models.TextChoices):
        MOVIE = "movie", "Movie"
        SPORT = "sport", "Sport"

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        SIMULATED = "simulated", "Simulated"

    thread = models.ForeignKey(
        ChatThread,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )
    booking_reference = models.CharField(max_length=32, unique=True)
    event_type = models.CharField(max_length=24, choices=EventType)
    status = models.CharField(max_length=24, choices=Status, default=Status.SIMULATED)
    movie_event = models.ForeignKey(
        MovieEvent,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )
    sport_event = models.ForeignKey(
        SportEvent,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )
    event_title = models.CharField(max_length=255)
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_contact_number = models.CharField(max_length=32, blank=True)
    city = models.CharField(max_length=120)
    venue_name = models.CharField(max_length=255)
    starts_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(default=timezone.now)
    filter_snapshot = models.JSONField(default=dict, blank=True)
    event_snapshot = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "bookings"
        ordering = ["-confirmed_at"]
        indexes = [
            models.Index(fields=["event_type", "-confirmed_at"], name="booking_type_recent_idx"),
            models.Index(fields=["thread"], name="booking_thread_idx"),
        ]

    def __str__(self) -> str:
        return self.booking_reference
