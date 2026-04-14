from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from apps.agents.langchain_tools import get_chat_model
from apps.flights.schemas import FlightBookingTurnResolution, FlightFilterResolution
from apps.flights.services import (
    get_available_airlines,
    get_available_cabin_classes,
    get_available_destination_cities,
    get_available_origin_cities,
)


def resolve_flight_turn_filters(*, current_filters: dict, user_message: str, reference_date: str) -> FlightFilterResolution:
    llm = get_chat_model(resolver=True)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You resolve flight search filters from the latest user turn.\n"
                "Use only the schema.\n"
                "You must return exact canonical values from the provided catalogs.\n"
                "Do not return synonyms or variants when a canonical value exists in catalog.\n"
                "Example: if user says Delhi and catalog has New Delhi, return New Delhi.\n"
                "Example: if user says Bangalore and catalog has Bengaluru, return Bengaluru.\n"
                "Example: if user says Madras and catalog has Chennai, return Chennai.\n"
                "When user broadens a filter (like all cities, any airline), use clear_fields and leave that filter list empty.\n"
                "If user message is unrelated to flight search/booking, return status no_input with a short redirect message.\n"
                "Do not invent airports, cities, airlines, or cabin classes outside the provided catalogs.\n"
                "If a value is not available in catalog, return no_match and include available candidates when helpful.\n",
            ),
            (
                "user",
                "reference_date: {reference_date}\n"
                "current_filters: {current_filters}\n"
                "origin_city_catalog: {origin_city_catalog}\n"
                "destination_city_catalog: {destination_city_catalog}\n"
                "airline_catalog: {airline_catalog}\n"
                "cabin_class_catalog: {cabin_class_catalog}\n"
                "user_message: {user_message}",
            ),
        ]
    )
    chain = prompt | llm.with_structured_output(FlightFilterResolution)
    return chain.invoke(
        {
            "reference_date": reference_date,
            "current_filters": current_filters,
            "origin_city_catalog": get_available_origin_cities(),
            "destination_city_catalog": get_available_destination_cities(),
            "airline_catalog": get_available_airlines(),
            "cabin_class_catalog": get_available_cabin_classes(),
            "user_message": user_message,
        }
    )


def resolve_flight_booking_turn(
    *,
    user_message: str,
    pending_booking: dict,
    latest_result_context: dict,
    missing_fields: list[str],
) -> FlightBookingTurnResolution:
    llm = get_chat_model(resolver=True)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You resolve flight booking actions from the latest user turn.\n"
                "Use only the response schema.\n"
                "Supported actions:\n"
                "- selection_pending: user selects or changes selected flight\n"
                "- booking_cleared: user explicitly asks to clear/cancel current selected flight\n"
                "- awaiting_user_info: user provides passenger info or asks booking progress while info missing\n"
                "- booking_confirmed: user confirms booking and all required info is already available\n"
                "- ambiguous or no_match: selection/reference is unclear or unavailable\n"
                "- none: no booking action in this turn\n"
                "Rules:\n"
                "1) listing_code must be chosen only from latest_result_context.results.\n"
                "2) If a flight is already selected, do not clear it unless user explicitly asks to clear/cancel/remove/change to no selection.\n"
                "3) While a flight is selected, off-topic questions should return action none with a short soft redirect message.\n"
                "4) If missing_fields is non-empty and user confirms booking, return awaiting_user_info and request the next required field.\n"
                "5) If user provides a passenger value, set requested_field and captured_value exactly.\n"
                "6) If pending_booking.awaiting_field is present, requested_field must be exactly that same field.\n"
                "7) Do not remap a provided value to a different field when awaiting_field is present.\n"
                "8) Never invent listing codes or passenger values.\n"
                "9) When selection is ambiguous across multiple results, return action ambiguous with candidates.\n",
            ),
            (
                "user",
                "pending_booking: {pending_booking}\n"
                "missing_fields: {missing_fields}\n"
                "latest_result_context: {latest_result_context}\n"
                "user_message: {user_message}",
            ),
        ]
    )
    chain = prompt | llm.with_structured_output(FlightBookingTurnResolution)
    return chain.invoke(
        {
            "pending_booking": pending_booking,
            "missing_fields": missing_fields,
            "latest_result_context": latest_result_context,
            "user_message": user_message,
        }
    )
