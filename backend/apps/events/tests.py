import json

from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.events.filter_tools import (
    get_all_event_types,
    get_available_movie_cast_members,
    get_available_movie_certifications,
    get_available_movie_directors,
    get_available_movie_formats,
    get_available_movie_genres,
    get_available_movie_languages,
    get_available_movie_locations,
    get_available_sport_format_labels,
    get_available_sport_locations,
    get_available_sport_organizers,
    get_available_sport_season_labels,
    get_available_sport_types,
)
from apps.events.models import MovieEvent, SportEvent
from apps.events.resolver_utils import (
    build_calendar_date,
    build_date_range,
    build_temporal_response_payload,
    build_time_window,
    extract_catalog_mentions,
    get_named_time_bucket,
    get_temporal_reference,
    normalize_clock_time,
    resolve_location_values,
    resolve_weekday_date,
    shift_iso_date,
)
from apps.events.services import search_movie_events, search_sport_events


class EventSearchServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        movie_start = timezone.make_aware(datetime(2026, 4, 20, 19, 30))
        sport_start = timezone.make_aware(datetime(2026, 4, 20, 19, 30))

        MovieEvent.objects.bulk_create(
            [
                MovieEvent(
                    listing_code="MOV-T-001",
                    title="Alpha",
                    event_date=movie_start.date(),
                    start_at=movie_start,
                    end_at=movie_start + timedelta(minutes=150),
                    city="New Delhi",
                    state="Delhi",
                    venue_name="PVR Directors Cut",
                    venue_area="Vasant Kunj",
                    venue_address="New Delhi",
                    languages=["Hindi", "English"],
                    min_price=250,
                    max_price=600,
                    tags=["premium", "spy"],
                    release_date=date(2026, 4, 17),
                    runtime_minutes=148,
                    certification="UA",
                    genres=["Action", "Spy Thriller"],
                    cast=["Alia Bhatt", "Sharvari Wagh"],
                    directors=["Shiv Rawail"],
                    formats=["IMAX 2D"],
                    franchise="YRF Spy Universe",
                    source_label="real",
                    content_origin="real",
                ),
                MovieEvent(
                    listing_code="MOV-T-002",
                    title="Delhi Dreams",
                    event_date=movie_start.date(),
                    start_at=movie_start.replace(hour=16, minute=0),
                    end_at=movie_start.replace(hour=18, minute=4),
                    city="Mumbai",
                    state="Maharashtra",
                    venue_name="Maison PVR",
                    venue_area="BKC",
                    venue_address="Mumbai",
                    languages=["Hindi"],
                    min_price=180,
                    max_price=420,
                    tags=["romance", "weekday"],
                    release_date=date(2026, 6, 5),
                    runtime_minutes=124,
                    certification="U",
                    genres=["Drama", "Romance"],
                    cast=["Triptii Dimri"],
                    directors=["Akarsh Khurana"],
                    formats=["2D"],
                    franchise="",
                    source_label="synthetic",
                    content_origin="synthetic",
                ),
            ]
        )

        SportEvent.objects.bulk_create(
            [
                SportEvent(
                    listing_code="SPT-T-001",
                    title="Delhi Capitals vs Chennai Super Kings",
                    event_date=sport_start.date(),
                    start_at=sport_start,
                    end_at=sport_start + timedelta(hours=4),
                    city="New Delhi",
                    state="Delhi",
                    venue_name="Arun Jaitley Stadium",
                    venue_area="Bahadur Shah Zafar Marg",
                    venue_address="New Delhi",
                    languages=["Hindi", "English"],
                    min_price=499,
                    max_price=2400,
                    tags=["cricket", "ipl"],
                    source_label="real",
                    sport_type="Cricket",
                    tournament_name="Indian Premier League 2026",
                    season_label="IPL 2026",
                    competition_stage="League",
                    format_label="T20",
                    home_team="Delhi Capitals",
                    away_team="Chennai Super Kings",
                    participant_names=["Delhi Capitals", "Chennai Super Kings"],
                    featured_athletes=["KL Rahul", "Ruturaj Gaikwad"],
                    organizer="BCCI",
                    gate_open_at=sport_start - timedelta(hours=2),
                    match_number=18,
                ),
                SportEvent(
                    listing_code="SPT-T-002",
                    title="Mumbai City FC vs FC Goa",
                    event_date=sport_start.date() + timedelta(days=2),
                    start_at=sport_start.replace(day=22, hour=20),
                    end_at=sport_start.replace(day=22, hour=22),
                    city="Mumbai",
                    state="Maharashtra",
                    venue_name="Mumbai Football Arena",
                    venue_area="Andheri",
                    venue_address="Mumbai",
                    languages=["English"],
                    min_price=399,
                    max_price=1899,
                    tags=["football", "club-football"],
                    source_label="synthetic",
                    sport_type="Football",
                    tournament_name="Indian Super Cup 2026",
                    season_label="2026",
                    competition_stage="League",
                    format_label="90-minute match",
                    home_team="Mumbai City FC",
                    away_team="FC Goa",
                    participant_names=["Mumbai City FC", "FC Goa"],
                    featured_athletes=["Lallianzuala Chhangte", "Brison Fernandes"],
                    organizer="AIFF",
                    gate_open_at=sport_start.replace(day=22, hour=18, minute=30),
                    match_number=5,
                ),
            ]
        )

    def test_movie_search_filters_by_city(self):
        result = search_movie_events({"cities": ["New Delhi"]})
        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["title"], "Alpha")

    def test_movie_search_compound_filters(self):
        result = search_movie_events(
            {
                "cities": ["New Delhi"],
                "languages": ["Hindi"],
                "genres": ["Action"],
                "formats": ["IMAX 2D"],
            }
        )
        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["listing_code"], "MOV-T-001")

    def test_movie_search_supports_director_and_certification_filters(self):
        result = search_movie_events(
            {
                "directors": ["Shiv Rawail"],
                "certifications": ["UA"],
            }
        )
        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["title"], "Alpha")

    def test_movie_search_returns_empty_result(self):
        result = search_movie_events({"cities": ["Chennai"], "genres": ["Comedy"]})
        self.assertEqual(result.count, 0)
        self.assertEqual(result.results, [])

    def test_sport_search_filters_by_sport_type_and_city(self):
        result = search_sport_events({"sport_types": ["Cricket"], "cities": ["New Delhi"]})
        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["listing_code"], "SPT-T-001")

    def test_sport_search_team_filter_matches_home_or_away(self):
        result = search_sport_events({"teams": ["FC Goa"]})
        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["sport_type"], "Football")

    def test_sport_search_supports_season_and_organizer_filters(self):
        result = search_sport_events(
            {
                "season_labels": ["IPL 2026"],
                "organizers": ["BCCI"],
            }
        )
        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["listing_code"], "SPT-T-001")

    def test_sport_search_respects_time_range(self):
        result = search_sport_events({"start_time_from": "19:00", "start_time_to": "20:30"})
        self.assertEqual(result.count, 2)

    def test_movie_search_endpoint_returns_results(self):
        response = self.client.post(
            "/api/events/movies/search/",
            data='{"filters":{"cities":["New Delhi"],"genres":["Action"]},"limit":10,"offset":0}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["listing_code"], "MOV-T-001")


class EventFilterToolTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        movie_start = timezone.make_aware(datetime(2026, 4, 20, 19, 30))
        sport_start = timezone.make_aware(datetime(2026, 4, 20, 19, 30))

        MovieEvent.objects.create(
            listing_code="MOV-F-001",
            title="Alpha",
            event_date=movie_start.date(),
            start_at=movie_start,
            end_at=movie_start + timedelta(minutes=150),
            city="New Delhi",
            state="Delhi",
            venue_name="PVR Directors Cut",
            venue_area="Vasant Kunj",
            venue_address="New Delhi",
            languages=["Hindi", "English"],
            min_price=250,
            max_price=600,
            tags=["premium", "spy"],
            release_date=date(2026, 4, 17),
            runtime_minutes=148,
            certification="UA",
            genres=["Action", "Spy Thriller"],
            cast=["Alia Bhatt", "Sharvari Wagh"],
            directors=["Shiv Rawail"],
            formats=["IMAX 2D"],
            franchise="YRF Spy Universe",
            source_label="real",
            content_origin="real",
        )

        SportEvent.objects.create(
            listing_code="SPT-F-001",
            title="Delhi Capitals vs Chennai Super Kings",
            event_date=sport_start.date(),
            start_at=sport_start,
            end_at=sport_start + timedelta(hours=4),
            city="New Delhi",
            state="Delhi",
            venue_name="Arun Jaitley Stadium",
            venue_area="Bahadur Shah Zafar Marg",
            venue_address="New Delhi",
            languages=["Hindi", "English"],
            min_price=499,
            max_price=2400,
            tags=["cricket", "ipl"],
            source_label="real",
            sport_type="Cricket",
            tournament_name="Indian Premier League 2026",
            season_label="IPL 2026",
            competition_stage="League",
            format_label="T20",
            home_team="Delhi Capitals",
            away_team="Chennai Super Kings",
            participant_names=["Delhi Capitals", "Chennai Super Kings"],
            featured_athletes=["KL Rahul", "Ruturaj Gaikwad"],
            organizer="BCCI",
            gate_open_at=sport_start - timedelta(hours=2),
            match_number=18,
        )

    def test_filter_tools_return_distinct_values(self):
        self.assertEqual(get_all_event_types(), ["movies", "sports"])
        self.assertEqual(get_available_movie_locations(), ["New Delhi"])
        self.assertEqual(get_available_sport_locations(), ["New Delhi"])
        self.assertEqual(get_available_sport_types(), ["Cricket"])
        self.assertEqual(get_available_movie_languages(), ["English", "Hindi"])
        self.assertEqual(get_available_movie_genres(), ["Action", "Spy Thriller"])
        self.assertEqual(get_available_movie_cast_members(), ["Alia Bhatt", "Sharvari Wagh"])
        self.assertEqual(get_available_movie_directors(), ["Shiv Rawail"])
        self.assertEqual(get_available_movie_certifications(), ["UA"])
        self.assertEqual(get_available_movie_formats(), ["IMAX 2D"])
        self.assertEqual(get_available_sport_season_labels(), ["IPL 2026"])
        self.assertEqual(get_available_sport_format_labels(), ["T20"])
        self.assertEqual(get_available_sport_organizers(), ["BCCI"])

    def test_location_resolution_maps_aliases(self):
        result = resolve_location_values(["Delhi"], ["New Delhi", "Mumbai"])
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved_values, ["New Delhi"])

    def test_location_resolution_returns_no_match(self):
        result = resolve_location_values(["Paris"], ["New Delhi", "Mumbai"])
        self.assertEqual(result.status, "no_match")
        self.assertEqual(result.resolved_values, [])

    def test_extract_catalog_mentions_handles_location_aliases_inside_sentence(self):
        result = extract_catalog_mentions(
            filter_key="cities",
            text="I want a cricket match in Delhi this Sunday",
            available_values=["New Delhi", "Mumbai"],
            aliases={"delhi": "New Delhi"},
        )
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved_values, ["New Delhi"])

    def test_temporal_reference_tool_returns_expected_week_boundaries(self):
        reference = get_temporal_reference(reference_date="2026-04-09")

        self.assertEqual(reference["reference_date"], "2026-04-09")
        self.assertEqual(reference["current_week_start"], "2026-04-06")
        self.assertEqual(reference["current_week_end"], "2026-04-12")
        self.assertEqual(reference["next_week_start"], "2026-04-13")
        self.assertEqual(reference["next_week_end"], "2026-04-19")

    def test_resolve_weekday_date_supports_this_week_and_upcoming(self):
        self.assertEqual(
            resolve_weekday_date(reference_date="2026-04-09", weekday_name="sunday", scope="this_week"),
            "2026-04-12",
        )
        self.assertEqual(
            resolve_weekday_date(reference_date="2026-04-09", weekday_name="monday", scope="upcoming"),
            "2026-04-13",
        )

    def test_date_builder_tools_support_open_and_bounded_ranges(self):
        april_thirteenth = build_calendar_date(year=2026, month=4, day=13)
        april_fourteenth = shift_iso_date(date_value=april_thirteenth, days=1)

        self.assertEqual(april_thirteenth, "2026-04-13")
        self.assertEqual(april_fourteenth, "2026-04-14")
        self.assertEqual(build_date_range(start_date=april_fourteenth, end_date=None), {"date_from": "2026-04-14", "date_to": None})
        self.assertEqual(
            build_date_range(start_date="2026-04-13", end_date="2026-04-19"),
            {"date_from": "2026-04-13", "date_to": "2026-04-19"},
        )

    def test_time_tools_build_window_and_named_bucket(self):
        normalized_time = normalize_clock_time(time_text="7pm")
        exact_window = build_time_window(anchor_time=normalized_time["normalized_time"])
        evening_bucket = get_named_time_bucket(label="evening")

        self.assertEqual(normalized_time["normalized_time"], "19:00:00")
        self.assertEqual(exact_window["start"], "18:00:00")
        self.assertEqual(exact_window["end"], "20:00:00")
        self.assertEqual(exact_window["anchor_time"], "19:00:00")
        self.assertEqual(evening_bucket["anchor_time"], "19:00:00")
        self.assertEqual(evening_bucket["start"], "18:00:00")
        self.assertEqual(evening_bucket["end"], "21:00:00")

    def test_temporal_response_payload_formats_exact_dates(self):
        normalized = build_temporal_response_payload(
            {
                "event_dates": ["2026-04-12", "2026-04-13"],
                "start_time_from": "18:00:00",
                "start_time_to": "20:00:00",
            },
            reference_date=date(2026, 4, 9),
        )

        self.assertEqual(normalized["dates"], ["2026-04-12", "2026-04-13"])
        self.assertEqual(normalized["anchor_time"], "19:00:00")
        self.assertEqual(normalized["time_range"]["start"], "18:00:00")
        self.assertEqual(normalized["time_range"]["end"], "20:00:00")
        self.assertEqual(
            normalized["resolved_datetimes"],
            ["2026-04-12T19:00:00+05:30", "2026-04-13T19:00:00+05:30"],
        )
        self.assertIsNone(normalized["date_from"])
        self.assertIsNone(normalized["date_to"])

    def test_temporal_response_payload_formats_open_ended_date_range(self):
        normalized = build_temporal_response_payload(
            {
                "date_from": "2026-04-13",
                "start_time_from": "18:00:00",
                "start_time_to": "20:00:00",
            },
            reference_date=date(2026, 4, 9),
        )

        self.assertEqual(normalized["dates"], [])
        self.assertEqual(normalized["date_from"], "2026-04-13")
        self.assertIsNone(normalized["date_to"])

    def test_movie_locations_endpoint_returns_values(self):
        response = self.client.get("/api/events/tools/movies/locations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["values"], ["New Delhi"])

    def test_movie_directors_endpoint_returns_values(self):
        response = self.client.get("/api/events/tools/movies/directors/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["values"], ["Shiv Rawail"])

    def test_sport_format_labels_endpoint_returns_values(self):
        response = self.client.get("/api/events/tools/sports/format-labels/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["values"], ["T20"])

    def test_temporal_normalization_endpoint_returns_payload(self):
        with patch("apps.events.views.invoke_temporal_resolver") as invoke_temporal_resolver_mock:
            invoke_temporal_resolver_mock.return_value.active_filters_partial = {
                "event_dates": ["2026-04-12"],
                "start_time_from": "18:00:00",
                "start_time_to": "20:00:00",
            }
            invoke_temporal_resolver_mock.return_value.status = "resolved"
            invoke_temporal_resolver_mock.return_value.message = "Resolved temporal filters."
            invoke_temporal_resolver_mock.return_value.candidates = []

            response = self.client.post(
                "/api/events/tools/temporal/normalize/",
                data=json.dumps(
                    {
                        "filters": {
                            "text": "this sunday around 7pm",
                            "reference_date": "2026-04-09",
                        }
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["dates"], ["2026-04-12"])
        self.assertIsNone(payload["date_from"])
        self.assertIsNone(payload["date_to"])
