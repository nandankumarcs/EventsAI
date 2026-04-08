import json
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.bookings.models import Booking
from apps.chats.models import ChatMessage, ChatThread, ThreadFilter
from apps.events.models import MovieEvent


class BookingApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        start_at = timezone.make_aware(datetime(2026, 4, 12, 19, 0))
        cls.movie_event = MovieEvent.objects.create(
            listing_code="MOV-B-001",
            title="Stree 2",
            event_date=date(2026, 4, 12),
            start_at=start_at,
            end_at=start_at + timedelta(minutes=147),
            city="Mumbai",
            state="Maharashtra",
            venue_name="Maison PVR",
            venue_area="BKC",
            venue_address="Mumbai",
            languages=["Hindi"],
            min_price=250,
            max_price=420,
            tags=["comedy", "horror"],
            release_date=date(2024, 8, 15),
            runtime_minutes=147,
            certification="UA",
            genres=["Comedy", "Horror"],
            cast=["Rajkummar Rao", "Shraddha Kapoor"],
            directors=["Amar Kaushik"],
            formats=["2D"],
            franchise="Maddock Horror Comedy Universe",
            source_label="real",
            content_origin="real",
        )

    def test_booking_confirm_creates_booking_and_marks_thread_booked(self):
        thread = ChatThread.objects.create(title="Book Stree 2")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["movies"], "cities": ["Mumbai"]},
        )
        ChatMessage.objects.create(
            thread=thread,
            position=1,
            role=ChatMessage.Role.USER,
            content="Book Stree 2 in Mumbai",
        )

        response = self.client.post(
            "/api/bookings/confirm/",
            data=json.dumps({"thread_id": str(thread.id), "listing_code": self.movie_event.listing_code}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get()
        thread.refresh_from_db()
        self.assertEqual(thread.status, ChatThread.Status.BOOKED)
        self.assertEqual(booking.event_title, "Stree 2")
        self.assertEqual(booking.filter_snapshot["cities"], ["Mumbai"])
        self.assertEqual(thread.messages.count(), 2)
        self.assertIn("Booking confirmed", thread.messages.order_by("-position").first().content)

    def test_booking_list_returns_saved_bookings(self):
        thread = ChatThread.objects.create(title="Booked thread", status=ChatThread.Status.BOOKED)
        Booking.objects.create(
            thread=thread,
            booking_reference="ATD-TEST123",
            event_type=Booking.EventType.MOVIE,
            status=Booking.Status.CONFIRMED,
            movie_event=self.movie_event,
            event_title=self.movie_event.title,
            city=self.movie_event.city,
            venue_name=self.movie_event.venue_name,
            starts_at=self.movie_event.start_at,
            filter_snapshot={"event_types": ["movies"]},
            event_snapshot={"listing_code": self.movie_event.listing_code, "title": self.movie_event.title},
        )

        response = self.client.get("/api/bookings/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["bookings"][0]["event_title"], "Stree 2")

    def test_booking_confirm_is_idempotent_for_same_thread_and_listing(self):
        thread = ChatThread.objects.create(title="Book Stree 2")

        first_response = self.client.post(
            "/api/bookings/confirm/",
            data=json.dumps({"thread_id": str(thread.id), "listing_code": self.movie_event.listing_code}),
            content_type="application/json",
        )
        second_response = self.client.post(
            "/api/bookings/confirm/",
            data=json.dumps({"thread_id": str(thread.id), "listing_code": self.movie_event.listing_code}),
            content_type="application/json",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertTrue(second_response.json()["already_confirmed"])

    def test_booking_confirm_rejects_new_listing_for_booked_thread(self):
        thread = ChatThread.objects.create(title="Booked thread", status=ChatThread.Status.BOOKED)

        response = self.client.post(
            "/api/bookings/confirm/",
            data=json.dumps({"thread_id": str(thread.id), "listing_code": self.movie_event.listing_code}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already has a confirmed booking", response.json()["error"])
