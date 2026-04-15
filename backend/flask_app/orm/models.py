from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flask_app.orm.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    last_message_preview: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.position",
    )
    filter_state: Mapped["ThreadFilter"] = relationship(back_populates="thread", uselist=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("thread_id", "position", name="unique_message_position_per_thread"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    thread_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    thread: Mapped[ChatThread] = relationship(back_populates="messages")


class ThreadFilter(Base):
    __tablename__ = "thread_filters"

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    thread_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    active_filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    latest_result_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    pending_booking: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    resolver_trace: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped[ChatThread] = relationship(back_populates="filter_state")


class MovieEvent(Base):
    __tablename__ = "movie_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    venue_name: Mapped[str] = mapped_column(String(255), nullable=False)
    venue_area: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    venue_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    languages: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    min_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    source_label: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    release_date: Mapped[date | None] = mapped_column(Date)
    runtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    certification: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    genres: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    cast: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    directors: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    formats: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    franchise: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    synopsis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    viewer_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    content_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="")


class SportEvent(Base):
    __tablename__ = "sport_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    venue_name: Mapped[str] = mapped_column(String(255), nullable=False)
    venue_area: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    venue_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    languages: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    min_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    source_label: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sport_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tournament_name: Mapped[str] = mapped_column(String(255), nullable=False)
    season_label: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    competition_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    format_label: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    home_team: Mapped[str] = mapped_column(String(120), nullable=False)
    away_team: Mapped[str] = mapped_column(String(120), nullable=False)
    participant_names: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    featured_athletes: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    organizer: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    gate_open_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    match_number: Mapped[int | None] = mapped_column(Integer)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    thread_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("chat_threads.id"))
    booking_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="simulated")
    movie_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("movie_events.id"))
    sport_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sport_events.id"))
    event_title: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    customer_email: Mapped[str] = mapped_column(String(254), nullable=False, default="")
    customer_contact_number: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    venue_name: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    filter_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    event_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class FlightOffer(Base):
    __tablename__ = "flight_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_offer_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    source_label: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    origin_iata: Mapped[str] = mapped_column(String(8), nullable=False)
    origin_airport_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    origin_city: Mapped[str] = mapped_column(String(120), nullable=False)
    origin_state: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    destination_iata: Mapped[str] = mapped_column(String(8), nullable=False)
    destination_airport_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    destination_city: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_state: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    airline_code: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    airline_name: Mapped[str] = mapped_column(String(255), nullable=False)
    flight_number: Mapped[str] = mapped_column(String(32), nullable=False)
    cabin_class: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    stops: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refundable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    baggage_summary: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    fare_brand: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FlightBooking(Base):
    __tablename__ = "flight_bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("chat_threads.id"))
    booking_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="simulated")
    listing_code: Mapped[str] = mapped_column(String(64), nullable=False)
    offer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("flight_offers.id"))
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    origin_city: Mapped[str] = mapped_column(String(120), nullable=False)
    origin_iata: Mapped[str] = mapped_column(String(8), nullable=False)
    destination_city: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_iata: Mapped[str] = mapped_column(String(8), nullable=False)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    airline_name: Mapped[str] = mapped_column(String(255), nullable=False)
    flight_number: Mapped[str] = mapped_column(String(32), nullable=False)
    cabin_class: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    stops: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    passenger_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    passenger_email: Mapped[str] = mapped_column(String(254), nullable=False, default="")
    passenger_contact_number: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    filter_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    offer_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
