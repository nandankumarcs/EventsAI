from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FlightFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    origin_cities: list[str] = Field(default_factory=list)
    destination_cities: list[str] = Field(default_factory=list)
    departure_dates: list[str] = Field(default_factory=list)
    departure_date_from: str | None = None
    departure_date_to: str | None = None
    airlines: list[str] = Field(default_factory=list)
    cabin_classes: list[str] = Field(default_factory=list)
    stops: list[int] = Field(default_factory=list)
    price_min: str | None = None
    price_max: str | None = None
    search_text: str | None = None


class FlightFilterResolution(BaseModel):
    status: Literal["resolved", "no_input", "ambiguous", "no_match"] = "no_input"
    message: str = ""
    active_filters_partial: FlightFilters = Field(default_factory=FlightFilters)
    clear_fields: list[str] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)
    confidence: float | None = None


class FlightSelectedOffer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_code: str = ""
    title: str = ""
    origin_city: str = ""
    destination_city: str = ""
    airline_name: str = ""
    flight_number: str = ""
    departure_date: str = ""
    start_at: str = ""
    cabin_class: str = ""
    stops: int | None = None
    total_amount: str | None = None
    currency: str | None = None
    position: int | None = None


class FlightBookingSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    thread_id: str | None = None
    booking_reference: str = ""
    status: str = ""
    listing_code: str = ""
    route: str = ""
    departure_at: str = ""
    airline_name: str = ""
    flight_number: str = ""
    passenger_name: str = ""
    passenger_email: str = ""
    passenger_contact_number: str = ""
    confirmed_at: str = ""


class FlightBookingTurnResolution(BaseModel):
    action: Literal[
        "none",
        "selection_pending",
        "awaiting_user_info",
        "booking_confirmed",
        "booking_cleared",
        "ambiguous",
        "no_match",
    ] = "none"
    message: str = ""
    listing_code: str = ""
    requested_field: str = ""
    captured_value: str = ""
    selected_offer: FlightSelectedOffer = Field(default_factory=FlightSelectedOffer)
    booking: FlightBookingSummaryPayload = Field(default_factory=FlightBookingSummaryPayload)
    candidates: list[str] = Field(default_factory=list)
