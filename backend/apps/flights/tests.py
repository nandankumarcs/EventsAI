import json

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.flights.chat_services import process_flight_chat_turn
from apps.flights.models import FlightBooking, FlightOffer
from apps.flights.schemas import FlightBookingTurnResolution, FlightFilterResolution, FlightFilters
from apps.flights.services import search_flight_offers
from scripts.flights.seed_offers import (
    build_listing_code,
    fetch_aviationstack_rows,
    normalize_aviationstack_schedule,
    persist_rows,
)


class FlightSearchServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        FlightOffer.objects.bulk_create(
            [
                FlightOffer(
                    listing_code="FLT-T-001",
                    provider="aviationstack",
                    provider_offer_id="AV-001",
                    source_label="seed",
                    origin_iata="DEL",
                    origin_airport_name="Indira Gandhi International Airport",
                    origin_city="New Delhi",
                    origin_state="Delhi",
                    destination_iata="BOM",
                    destination_airport_name="Chhatrapati Shivaji Maharaj International Airport",
                    destination_city="Mumbai",
                    destination_state="Maharashtra",
                    departure_date=datetime(2026, 5, 10).date(),
                    departure_at=timezone.make_aware(datetime(2026, 5, 10, 9, 30)),
                    arrival_at=timezone.make_aware(datetime(2026, 5, 10, 11, 45)),
                    airline_code="AI",
                    airline_name="Air India",
                    flight_number="AI 101",
                    cabin_class="Economy",
                    stops=0,
                    refundable=True,
                    baggage_summary="15kg check-in",
                    fare_brand="Flex",
                    currency="INR",
                    total_amount=Decimal("6450.00"),
                ),
                FlightOffer(
                    listing_code="FLT-T-002",
                    provider="aviationstack",
                    provider_offer_id="AV-002",
                    source_label="seed",
                    origin_iata="DEL",
                    origin_airport_name="Indira Gandhi International Airport",
                    origin_city="New Delhi",
                    origin_state="Delhi",
                    destination_iata="BLR",
                    destination_airport_name="Kempegowda International Airport",
                    destination_city="Bengaluru",
                    destination_state="Karnataka",
                    departure_date=datetime(2026, 5, 10).date(),
                    departure_at=timezone.make_aware(datetime(2026, 5, 10, 14, 0)),
                    arrival_at=timezone.make_aware(datetime(2026, 5, 10, 16, 40)),
                    airline_code="UK",
                    airline_name="Vistara",
                    flight_number="UK 815",
                    cabin_class="Premium Economy",
                    stops=0,
                    refundable=False,
                    baggage_summary="20kg check-in",
                    fare_brand="Value",
                    currency="INR",
                    total_amount=Decimal("8120.00"),
                ),
            ]
        )

    def test_search_flight_offers_filters_by_route(self):
        result = search_flight_offers({"origin_cities": ["New Delhi"], "destination_cities": ["Mumbai"]})
        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["listing_code"], "FLT-T-001")

    def test_search_flight_offers_filters_by_airline_and_price(self):
        result = search_flight_offers({"airlines": ["Air India"], "price_max": "7000"})
        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["flight_number"], "AI 101")


class FlightApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        FlightOffer.objects.create(
            listing_code="FLT-A-001",
            provider="aviationstack",
            provider_offer_id="AV-A-001",
            source_label="seed",
            origin_iata="DEL",
            origin_airport_name="Indira Gandhi International Airport",
            origin_city="New Delhi",
            origin_state="Delhi",
            destination_iata="BOM",
            destination_airport_name="Chhatrapati Shivaji Maharaj International Airport",
            destination_city="Mumbai",
            destination_state="Maharashtra",
            departure_date=datetime(2026, 5, 10).date(),
            departure_at=timezone.make_aware(datetime(2026, 5, 10, 9, 30)),
            arrival_at=timezone.make_aware(datetime(2026, 5, 10, 11, 45)),
            airline_code="AI",
            airline_name="Air India",
            flight_number="AI 101",
            cabin_class="Economy",
            stops=0,
            refundable=True,
            baggage_summary="15kg check-in",
            fare_brand="Flex",
            currency="INR",
            total_amount=Decimal("6450.00"),
        )

    def test_flight_search_endpoint_returns_results(self):
        response = self.client.post(
            "/api/flights/search/",
            data=json.dumps({"filters": {"origin_cities": ["New Delhi"]}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["listing_code"], "FLT-A-001")

    def test_flight_tool_endpoints_return_catalog_values(self):
        response = self.client.get("/api/flights/tools/origins/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["values"], ["New Delhi"])

    @patch("apps.flights.chat_services.resolve_flight_turn_filters")
    def test_flight_chat_turn_returns_flight_results(self, mock_resolver):
        thread_response = self.client.post(
            "/api/chats/threads/",
            data=json.dumps({"title": "Flight thread", "mode": "flights"}),
            content_type="application/json",
        )
        thread_id = thread_response.json()["thread"]["id"]

        mock_resolver.return_value = FlightFilterResolution(
            status="resolved",
            message="",
            active_filters_partial=FlightFilters(origin_cities=["New Delhi"], destination_cities=["Mumbai"]),
        )

        payload = process_flight_chat_turn(
            user_message="Show me flights from Delhi to Mumbai",
            thread_id=thread_id,
        )

        self.assertEqual(payload["thread"]["mode"], "flights")
        self.assertEqual(payload["search_domains"], ["flights"])
        self.assertIn("flights", payload["results_by_domain"])
        self.assertEqual(payload["active_filters"]["origin_cities"], ["New Delhi"])
        self.assertEqual(payload["active_filters"]["destination_cities"], ["Mumbai"])

    @patch("apps.flights.chat_services.resolve_flight_booking_turn")
    @patch("apps.flights.chat_services.resolve_flight_turn_filters")
    def test_flight_chat_turn_selection_then_user_info_then_confirmation(
        self,
        mock_filter_resolver,
        mock_booking_resolver,
    ):
        thread_response = self.client.post(
            "/api/chats/threads/",
            data=json.dumps({"title": "Flight booking", "mode": "flights"}),
            content_type="application/json",
        )
        thread_id = thread_response.json()["thread"]["id"]

        mock_filter_resolver.return_value = FlightFilterResolution(
            status="resolved",
            message="",
            active_filters_partial=FlightFilters(origin_cities=["New Delhi"], destination_cities=["Mumbai"]),
        )
        first_turn = process_flight_chat_turn(
            user_message="show flights from delhi to mumbai",
            thread_id=thread_id,
        )
        self.assertEqual(first_turn["search_domains"], ["flights"])
        listing_code = first_turn["results_by_domain"]["flights"]["results"][0]["listing_code"]

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="selection_pending",
            listing_code=listing_code,
            message="Selected. Reply yes to confirm or share passenger details.",
        )
        second_turn = process_flight_chat_turn(
            user_message="book the first one",
            thread_id=thread_id,
        )
        self.assertEqual(second_turn["assistant_message"]["metadata"]["booking_action"], "selection_pending")
        self.assertEqual(second_turn["search_domains"], [])
        self.assertEqual(second_turn["pending_booking"]["listing_code"], listing_code)

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="booking_confirmed",
            message="confirm this",
        )
        third_turn = process_flight_chat_turn(user_message="yes confirm", thread_id=thread_id)
        self.assertEqual(third_turn["assistant_message"]["metadata"]["booking_action"], "awaiting_user_info")
        self.assertEqual(third_turn["pending_booking"]["awaiting_field"], "name")

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="awaiting_user_info",
            requested_field="name",
            captured_value="Nandan Kumar",
        )
        fourth_turn = process_flight_chat_turn(user_message="my name is Nandan Kumar", thread_id=thread_id)
        self.assertEqual(fourth_turn["pending_booking"]["awaiting_field"], "email")

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="awaiting_user_info",
            requested_field="email",
            captured_value="nandan@example.com",
        )
        fifth_turn = process_flight_chat_turn(user_message="nandan@example.com", thread_id=thread_id)
        self.assertEqual(fifth_turn["pending_booking"]["awaiting_field"], "contact_number")

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="awaiting_user_info",
            requested_field="contact_number",
            captured_value="+919876543210",
        )
        final_turn = process_flight_chat_turn(user_message="+919876543210", thread_id=thread_id)
        self.assertEqual(final_turn["assistant_message"]["metadata"]["booking_action"], "booking_confirmed")
        self.assertEqual(final_turn["thread"]["status"], "booked")
        self.assertEqual(FlightBooking.objects.count(), 1)

    @patch("apps.flights.chat_services.resolve_flight_booking_turn")
    @patch("apps.flights.chat_services.resolve_flight_turn_filters")
    def test_pending_selection_is_kept_when_booking_resolver_returns_none(
        self,
        mock_filter_resolver,
        mock_booking_resolver,
    ):
        thread_response = self.client.post(
            "/api/chats/threads/",
            data=json.dumps({"title": "Flight booking", "mode": "flights"}),
            content_type="application/json",
        )
        thread_id = thread_response.json()["thread"]["id"]

        mock_filter_resolver.return_value = FlightFilterResolution(
            status="resolved",
            active_filters_partial=FlightFilters(origin_cities=["New Delhi"], destination_cities=["Mumbai"]),
        )
        first_turn = process_flight_chat_turn(
            user_message="show flights from delhi to mumbai",
            thread_id=thread_id,
        )
        listing_code = first_turn["results_by_domain"]["flights"]["results"][0]["listing_code"]

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="selection_pending",
            listing_code=listing_code,
        )
        process_flight_chat_turn(user_message="pick this", thread_id=thread_id)

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="none",
            message="Let us continue with the selected flight. Please share passenger full name.",
        )
        turn = process_flight_chat_turn(user_message="write a poem", thread_id=thread_id)
        self.assertEqual(turn["assistant_message"]["metadata"]["booking_action"], "none")
        self.assertEqual(turn["pending_booking"]["listing_code"], listing_code)
        self.assertEqual(turn["search_domains"], [])

    @patch("apps.flights.chat_services.resolve_flight_booking_turn")
    @patch("apps.flights.chat_services.resolve_flight_turn_filters")
    def test_awaiting_field_takes_priority_over_model_requested_field(
        self,
        mock_filter_resolver,
        mock_booking_resolver,
    ):
        thread_response = self.client.post(
            "/api/chats/threads/",
            data=json.dumps({"title": "Flight booking", "mode": "flights"}),
            content_type="application/json",
        )
        thread_id = thread_response.json()["thread"]["id"]

        mock_filter_resolver.return_value = FlightFilterResolution(
            status="resolved",
            active_filters_partial=FlightFilters(origin_cities=["New Delhi"], destination_cities=["Mumbai"]),
        )
        first_turn = process_flight_chat_turn(
            user_message="show flights from delhi to mumbai",
            thread_id=thread_id,
        )
        listing_code = first_turn["results_by_domain"]["flights"]["results"][0]["listing_code"]

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="selection_pending",
            listing_code=listing_code,
        )
        process_flight_chat_turn(user_message="book this", thread_id=thread_id)

        mock_booking_resolver.return_value = FlightBookingTurnResolution(action="booking_confirmed")
        process_flight_chat_turn(user_message="yes", thread_id=thread_id)

        mock_booking_resolver.return_value = FlightBookingTurnResolution(
            action="awaiting_user_info",
            requested_field="email",
            captured_value="Nandan Kumar",
        )
        turn = process_flight_chat_turn(user_message="Nandan Kumar", thread_id=thread_id)
        self.assertEqual(turn["pending_booking"]["customer_info"]["name"], "Nandan Kumar")
        self.assertEqual(turn["pending_booking"]["awaiting_field"], "email")


class FlightSeedScriptTests(TestCase):
    def test_normalize_aviationstack_schedule_keeps_india_domestic_rows(self):
        payload = {
            "data": [
                {
                    "departure": {"iataCode": "DEL", "scheduledTime": "09:30"},
                    "arrival": {"iataCode": "BOM", "scheduledTime": "11:45"},
                    "airline": {"name": "Air India", "iataCode": "AI"},
                    "flight": {"number": "101", "iataNumber": "AI101"},
                },
                {
                    "departure": {"iataCode": "DEL", "scheduledTime": "15:20"},
                    "arrival": {"iataCode": "DXB", "scheduledTime": "17:55"},
                    "airline": {"name": "Air India", "iataCode": "AI"},
                    "flight": {"number": "915", "iataNumber": "AI915"},
                },
            ]
        }

        rows = normalize_aviationstack_schedule(
            payload,
            target_date=datetime(2026, 5, 10).date(),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].origin_city, "New Delhi")
        self.assertEqual(rows[0].destination_city, "Mumbai")
        self.assertEqual(rows[0].flight_number, "101")
        self.assertEqual(rows[0].listing_code, build_listing_code(rows[0].provider_offer_id))

    @patch("scripts.flights.seed_offers.fetch_aviationstack_schedule")
    def test_persist_rows_upserts_seeded_flights(self, mock_fetch):
        mock_fetch.return_value = {
            "data": [
                {
                    "departure": {"iataCode": "DEL", "scheduledTime": "09:30"},
                    "arrival": {"iataCode": "BOM", "scheduledTime": "11:45"},
                    "airline": {"name": "Air India", "iataCode": "AI"},
                    "flight": {"number": "101", "iataNumber": "AI101"},
                }
            ]
        }

        rows = normalize_aviationstack_schedule(
            mock_fetch.return_value,
            target_date=datetime(2026, 5, 10).date(),
        )

        created, updated, unpublished = persist_rows(rows, mark_stale_unpublished=False)
        self.assertEqual((created, updated, unpublished), (1, 0, 0))
        offer = FlightOffer.objects.get()
        self.assertEqual(offer.provider, "aviationstack")
        self.assertEqual(offer.origin_city, "New Delhi")
        self.assertEqual(offer.destination_city, "Mumbai")
        self.assertEqual(offer.airline_name, "Air India")

    @patch("scripts.flights.seed_offers.fetch_aviationstack_schedule")
    def test_fetch_aviationstack_rows_batches_origin_codes_in_single_request(self, mock_fetch):
        mock_fetch.return_value = {
            "data": [
                {
                    "departure": {"iataCode": "DEL", "scheduledTime": "09:30"},
                    "arrival": {"iataCode": "BOM", "scheduledTime": "11:45"},
                    "airline": {"name": "Air India", "iataCode": "AI"},
                    "flight": {"number": "101", "iataNumber": "AI101"},
                }
            ]
        }

        rows = fetch_aviationstack_rows(
            session=None,
            access_key="test-key",
            start_date=datetime(2026, 5, 10).date(),
            days=1,
            origin_codes=["DEL", "BOM", "BLR"],
            sleep_seconds=0,
            max_retries=0,
        )

        self.assertEqual(len(rows), 1)
        mock_fetch.assert_called_once()
        self.assertEqual(mock_fetch.call_args.kwargs["airport_iatas"], "DEL,BOM,BLR")

    def test_normalize_aviationstack_schedule_skips_unexpected_item_types(self):
        rows = normalize_aviationstack_schedule(
            {"data": ["unexpected", 123, {"departure": {"iataCode": "DEL", "scheduledTime": "09:30"}, "arrival": {"iataCode": "BOM", "scheduledTime": "11:45"}, "airline": {"name": "Air India", "iataCode": "AI"}, "flight": {"number": "101", "iataNumber": "AI101"}}]},
            target_date=datetime(2026, 5, 10).date(),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].destination_city, "Mumbai")
