from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request

from apps.agents.langchain_tools import invoke_temporal_resolver
from apps.events.filter_tools import (
    get_all_event_types,
    get_available_movie_cast_members,
    get_available_movie_certifications,
    get_available_movie_content_origins,
    get_available_movie_directors,
    get_available_movie_formats,
    get_available_movie_franchises,
    get_available_movie_genres,
    get_available_movie_languages,
    get_available_movie_locations,
    get_available_movie_titles,
    get_available_movie_venues,
    get_available_sport_away_teams,
    get_available_sport_competition_stages,
    get_available_sport_featured_athletes,
    get_available_sport_format_labels,
    get_available_sport_home_teams,
    get_available_sport_locations,
    get_available_sport_match_numbers,
    get_available_sport_organizers,
    get_available_sport_participant_names,
    get_available_sport_season_labels,
    get_available_sport_teams,
    get_available_sport_tournaments,
    get_available_sport_types,
    get_available_sport_venues,
)
from apps.events.resolver_utils import build_temporal_response_payload
from apps.events.services import parse_request_filters, search_movie_events, search_sport_events


events_api = Blueprint("events_api", __name__, url_prefix="/api/events")


@events_api.post("/movies/search/")
def movie_search_view():
    try:
        filters, limit, offset = parse_request_filters(request.get_data())
    except Exception as exc:
        return jsonify({"error": f"Invalid movie search payload: {exc}"}), 400

    result = search_movie_events(filters, limit=limit, offset=offset)
    return jsonify(result.to_dict())


@events_api.post("/sports/search/")
def sport_search_view():
    try:
        filters, limit, offset = parse_request_filters(request.get_data())
    except Exception as exc:
        return jsonify({"error": f"Invalid sport search payload: {exc}"}), 400

    result = search_sport_events(filters, limit=limit, offset=offset)
    return jsonify(result.to_dict())


@events_api.get("/tools/event-types/")
def event_types_view():
    values = get_all_event_types()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/locations/")
def movie_locations_view():
    values = get_available_movie_locations()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/languages/")
def movie_languages_view():
    values = get_available_movie_languages()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/genres/")
def movie_genres_view():
    values = get_available_movie_genres()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/cast-members/")
def movie_cast_members_view():
    values = get_available_movie_cast_members()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/directors/")
def movie_directors_view():
    values = get_available_movie_directors()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/certifications/")
def movie_certifications_view():
    values = get_available_movie_certifications()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/titles/")
def movie_titles_view():
    values = get_available_movie_titles()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/venues/")
def movie_venues_view():
    values = get_available_movie_venues()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/formats/")
def movie_formats_view():
    values = get_available_movie_formats()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/franchises/")
def movie_franchises_view():
    values = get_available_movie_franchises()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/movies/content-origins/")
def movie_content_origins_view():
    values = get_available_movie_content_origins()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/locations/")
def sport_locations_view():
    values = get_available_sport_locations()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/types/")
def sport_types_view():
    values = get_available_sport_types()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/tournaments/")
def sport_tournaments_view():
    values = get_available_sport_tournaments()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/season-labels/")
def sport_season_labels_view():
    values = get_available_sport_season_labels()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/competition-stages/")
def sport_competition_stages_view():
    values = get_available_sport_competition_stages()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/format-labels/")
def sport_format_labels_view():
    values = get_available_sport_format_labels()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/home-teams/")
def sport_home_teams_view():
    values = get_available_sport_home_teams()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/away-teams/")
def sport_away_teams_view():
    values = get_available_sport_away_teams()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/teams/")
def sport_teams_view():
    values = get_available_sport_teams()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/participant-names/")
def sport_participant_names_view():
    values = get_available_sport_participant_names()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/venues/")
def sport_venues_view():
    values = get_available_sport_venues()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/featured-athletes/")
def sport_featured_athletes_view():
    values = get_available_sport_featured_athletes()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/organizers/")
def sport_organizers_view():
    values = get_available_sport_organizers()
    return jsonify({"count": len(values), "values": values})


@events_api.get("/tools/sports/match-numbers/")
def sport_match_numbers_view():
    values = get_available_sport_match_numbers()
    return jsonify({"count": len(values), "values": values})


@events_api.post("/tools/temporal/normalize/")
def temporal_normalization_view():
    try:
        filters, _limit, _offset = parse_request_filters(request.get_data())
    except Exception as exc:
        return jsonify({"error": f"Invalid temporal payload: {exc}"}), 400

    text = filters.get("text")
    reference_date = filters.get("reference_date")
    if not text:
        return jsonify({"error": "Temporal normalization requires a text field."}), 400

    normalized_resolution = invoke_temporal_resolver(
        text,
        reference_date=(reference_date or date.today().isoformat()),
    )
    normalized = build_temporal_response_payload(
        normalized_resolution.active_filters_partial,
        reference_date=None if not reference_date else date.fromisoformat(reference_date),
    )
    normalized["status"] = normalized_resolution.status
    normalized["message"] = normalized_resolution.message
    normalized["candidates"] = normalized_resolution.candidates
    return jsonify(normalized)
