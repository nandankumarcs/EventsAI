import json

from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.events.filter_tools import (
    get_all_event_types,
    get_available_movie_genres,
    get_available_movie_languages,
    get_available_movie_locations,
    get_available_sport_locations,
    get_available_sport_types,
)
from apps.events.models import MovieEvent, SportEvent
from apps.events.resolver_utils import (
    extract_catalog_mentions,
    normalize_temporal_expression,
    resolve_location_values,
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

    def test_temporal_normalization_handles_multiple_days_and_around_time(self):
        normalized = normalize_temporal_expression(
            "I want to watch a cricket match this sunday or monday in delhi at around 7pm",
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

    def test_movie_locations_endpoint_returns_values(self):
        response = self.client.get("/api/events/tools/movies/locations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["values"], ["New Delhi"])

    def test_temporal_normalization_endpoint_returns_payload(self):
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
